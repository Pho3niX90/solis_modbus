"""

This is a docstring placeholder.

This is where we will describe what this module does

"""
import asyncio
import logging
from datetime import timedelta
from typing import List

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import RestoreSensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, MANUFACTURER, \
    VALUES, NUMBER_ENTITIES, REGISTER, VALUE
from custom_components.solis_modbus.helpers import cache_save
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    """Set up the number platform."""
    modbus_controller: ModbusController = hass.data[DOMAIN][CONTROLLER][config_entry.data.get("host")]
    # We only want this platform to be set up via discovery.
    _LOGGER.info("Options %s", len(config_entry.options))

    inverter_type = config_entry.data.get("type", "hybrid")

    if inverter_type == 'string':
        return False

    platform_config = config_entry.data or {}
    if len(config_entry.options) > 0:
        platform_config = config_entry.options

    _LOGGER.info(f"Solis platform_config: {platform_config}")

    # fmt: off

    numberEntities: List[SolisNumberEntity] = []

    if inverter_type in ["string", "grid"]:
        from .sensor_data.string_sensors import string_sensors as sensors
    elif inverter_type == "hybrid-waveshare":
        from .sensor_data.hybrid_waveshare_sensors import hybrid_waveshare as sensors
    else:
        from .sensor_data.hybrid_sensors import hybrid_sensors as sensors

    for sensor_group in sensors:
        for entity_definition in sensor_group['entities']:
            entity_register = int(entity_definition['register'][0])
            if entity_definition.get('editable', False) and entity_definition['register'][0].startswith('4'):
                entity_multiplier = float(entity_definition['multiplier'])
                numberEntities.append(SolisNumberEntity(hass, modbus_controller,
                                                        {"name": entity_definition['name'], "register": entity_register,
                                                         "multiplier": 1 / entity_multiplier if entity_multiplier != 0 else 1,
                                                         "min_val": entity_definition.get("min"),
                                                         "max_val": entity_definition.get("max"),
                                                         "default": entity_definition.get("default"),
                                                         "step": 1 if (entity_definition['multiplier'] == 1 or
                                                                       entity_definition[
                                                                           'multiplier'] == 0) else entity_multiplier,
                                                         "unit_of_measurement": entity_definition[
                                                             'unit_of_measurement'], "enabled": True}))

    hass.data[DOMAIN][NUMBER_ENTITIES] = numberEntities
    async_add_devices(numberEntities, True)

    @callback
    def update(now):
        """Update Modbus data periodically."""
        for controller in hass.data[DOMAIN][CONTROLLER].values():
            _LOGGER.info(f"calling number update for {len(hass.data[DOMAIN][NUMBER_ENTITIES])} groups")
            hass.create_task(get_modbus_updates(hass, controller))

    async def get_modbus_updates(thass: HomeAssistant, controller: ModbusController):
        if not controller.connected():
            await controller.connect()

        await asyncio.gather(
            *[asyncio.to_thread(entity.update) for entity in thass.data[DOMAIN][NUMBER_ENTITIES]]
        )

    async_track_time_interval(hass, update, timedelta(seconds=modbus_controller.poll_interval * 3))

    return True


class SolisNumberEntity(RestoreSensor, NumberEntity):
    """Representation of a Number entity."""

    def __init__(self, hass, modbus_controller, sensor: SolisBaseSensor):
        """Initialize the Number entity."""
        self._hass = hass
        self._modbus_controller: ModbusController = modbus_controller
        self._register = sensor.registrars  # Multi-register support
        self._multiplier = sensor.multiplier

        # Unique ID based on all registers
        self._attr_unique_id = "{}_{}_{}".format(DOMAIN, self._modbus_controller.host, self._register)
        self._attr_has_entity_name = True
        self._attr_name = sensor.name
        self._attr_native_value = sensor.default
        self._attr_available = False
        self.is_added_to_hass = False
        self._attr_device_class = sensor.device_class
        self._attr_mode = NumberMode.AUTO
        self._attr_native_unit_of_measurement = sensor.unit_of_measurement
        self._attr_native_min_value = sensor.min_value
        self._attr_native_max_value = sensor.max_value
        self._attr_native_step = sensor.step
        self._attr_should_poll = False
        self._attr_entity_registry_enabled_default = sensor.enabled
        self.base_sensor = sensor

        # 🔹 Track received register values before updating
        self._received_values = {}

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to HA."""
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

        self.is_added_to_hass = True

        # 🔥 Register event listener for real-time updates
        self._hass.bus.async_listen(DOMAIN, self.handle_modbus_update)

    @callback
    def handle_modbus_update(self, event):
        """Callback function that updates sensor when new register data is available."""
        updated_register = int(event.data.get(REGISTER))
        updated_value = int(event.data.get(VALUE))
        updated_controller = int(event.data.get(CONTROLLER))

        if updated_controller != self._modbus_controller.host:
            return # meant for a different sensor/inverter combo

        # If this register belongs to the sensor, store it temporarily
        if updated_register in self._register:
            self._received_values[updated_register] = updated_value

            new_value = self.base_sensor.get_value

            # Clear received values after update
            self._received_values.clear()

            # Update state if valid value exists
            if new_value is not None:
                self._attr_native_value = round(new_value / self._multiplier)
                self.schedule_update_ha_state()

    def set_native_value(self, value):
        """Update the current value."""
        if self._attr_native_value == value:
            return

        # 🔹 Handle multi-register writing
        if len(self._register) == 1:
            register_value = round(value * self._multiplier)
        elif len(self._register) == 2:
            # Convert the value into two 16-bit registers
            int_value = round(value * self._multiplier)
            register_value = [(int_value >> 16) & 0xFFFF, int_value & 0xFFFF]
        else:
            _LOGGER.warning("More than 2 registers not yet supported for writing.")
            return

        # Write to Modbus controller
        self.hass.create_task(
            self._modbus_controller.async_write_holding_register(self._register[0], register_value)
        )

        if len(self._register) == 1:
            cache_save(self.hass, self._register[0], value)

        self._attr_native_value = value
        self.schedule_update_ha_state()