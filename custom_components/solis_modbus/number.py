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
    controller: ModbusController = hass.data[DOMAIN][CONTROLLER][config_entry.data.get("host")]
    # We only want this platform to be set up via discovery.
    _LOGGER.info("Options %s", len(config_entry.options))

    inverter_type = config_entry.data.get("type", "hybrid")

    if inverter_type == 'string':
        return False

    platform_config = config_entry.data or {}
    if len(config_entry.options) > 0:
        platform_config = config_entry.options

    _LOGGER.info(f"Solis platform_config: {platform_config}")

    sensors = []
    for sensor_group in controller.sensor_groups:
        for sensor in sensor_group.sensors:
            if sensor.name != "reserve" and sensor.editable:
                sensors.append(SolisNumberEntity(hass, sensor))

    async_add_devices(sensors, True)
    return True


class SolisNumberEntity(RestoreSensor, NumberEntity):
    """Representation of a Number entity."""

    def __init__(self, hass, sensor: SolisBaseSensor):
        """Initialize the Number entity."""
        self._hass = hass
        self._register = sensor.registrars  # Multi-register support
        self._multiplier = sensor.multiplier

        self._device_class = sensor.device_class
        self._unit_of_measurement  = sensor.unit_of_measurement
        self._attr_device_class = sensor.device_class
        self._attr_state_class = sensor.state_class
        self._attr_native_unit_of_measurement = sensor.unit_of_measurement

        # Unique ID based on all registers
        self._attr_unique_id = sensor.unique_id
        self._attr_has_entity_name = True
        self._attr_name = sensor.name
        self._attr_native_value = sensor.default
        self._attr_available = False
        self.is_added_to_hass = False
        self._attr_mode = NumberMode.AUTO
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
        updated_controller = str(event.data.get(CONTROLLER))

        if updated_controller != self.base_sensor.controller.host:
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
            self.base_sensor.controller.async_write_holding_register(self._register[0], register_value)
        )

        if len(self._register) == 1:
            cache_save(self.hass, self._register[0], value)

        self._attr_native_value = value
        self.schedule_update_ha_state()