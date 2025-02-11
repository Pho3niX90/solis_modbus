"""

This is a docstring placeholder.

This is where we will describe what this module does

"""
import asyncio
import logging
from datetime import timedelta
from typing import List

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import SensorDeviceClass, RestoreSensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent, PERCENTAGE, UnitOfPower)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, MANUFACTURER, \
    VALUES, NUMBER_ENTITIES

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
        from .data.string_sensors import string_sensors as sensors
    elif inverter_type == "hybrid-waveshare":
        from .data.hybrid_waveshare_sensors import hybrid_waveshare as sensors
    else:
        from .data.hybrid_sensors import hybrid_sensors as sensors

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

    # fmt: on


class SolisNumberEntity(RestoreSensor, NumberEntity):
    """Representation of a Number entity."""

    def __init__(self, hass, modbus_controller, entity_definition):
        """Initialize the Number entity."""
        #
        # Visible Instance Attributes Outside Class
        self._hass = hass
        self._modbus_controller: ModbusController = modbus_controller
        self._register = entity_definition["register"]
        self._multiplier = entity_definition["multiplier"]

        # Hidden Inherited Instance Attributes
        self._attr_unique_id = "{}_{}_{}".format(DOMAIN, self._modbus_controller.host, self._register)
        self._attr_has_entity_name = True
        self._attr_name = entity_definition["name"]
        self._attr_native_value = entity_definition.get("default", None)
        self._attr_assumed_state = entity_definition.get("assumed", False)
        self._attr_available = False
        self.is_added_to_hass = False
        self._attr_device_class = entity_definition.get("device_class", None)
        self._attr_icon = entity_definition.get("icon", None)
        self._attr_mode = entity_definition.get("mode", NumberMode.AUTO)
        self._attr_native_unit_of_measurement = entity_definition.get("unit_of_measurement", None)
        self._attr_native_min_value = entity_definition.get("min_val", None)
        self._attr_native_max_value = entity_definition.get("max_val", None)
        self._attr_native_step = entity_definition.get("step", 1.0)
        self._attr_should_poll = False
        self._attr_entity_registry_enabled_default = entity_definition.get("enabled", False)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value
        self.is_added_to_hass = True

    def update(self):
        """Update Modbus data periodically."""
        if not self.hass:  # Ensure hass is assigned
            return
        self._attr_available = True

        value: float = self._hass.data[DOMAIN][VALUES][str(self._register)]
        self._hass.create_task(self.update_values(value))

        try:
            self.schedule_update_ha_state()
        except Exception as e:
            _LOGGER.debug(f"Failed to schedule update: {e}")


    async def update_values(self, value):
        if value == 0 and self._modbus_controller.connected():
            register_value = await self._modbus_controller.async_read_holding_register(self._register)
            value = register_value[0] if register_value else value

        self._attr_native_value = round(value / self._multiplier)

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._modbus_controller.host)},
            manufacturer=MANUFACTURER,
            model=self._modbus_controller.model,
            name=f"{MANUFACTURER} {self._modbus_controller.model}",
            sw_version=self._modbus_controller.sw_version,
        )

    def set_native_value(self, value):
        """Update the current value."""
        if self._attr_native_value == value:
            return

        self.hass.create_task(
            self._modbus_controller.async_write_holding_register(self._register, round(value * self._multiplier)))
        self._attr_native_value = value
        self.schedule_update_ha_state()
