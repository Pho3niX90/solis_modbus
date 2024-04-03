"""

This is a docstring placeholder.

This is where we will describe what this module does

"""
import asyncio
import logging
from datetime import timedelta
from typing import List

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent, PERCENTAGE, UnitOfPower, )
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, VERSION, POLL_INTERVAL_SECONDS, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    """Set up the number platform."""
    modbus_controller = hass.data[DOMAIN][CONTROLLER]
    # We only want this platform to be set up via discovery.
    _LOGGER.info("Options %s", len(config_entry.options))

    platform_config = config_entry.data or {}
    if len(config_entry.options) > 0:
        platform_config = config_entry.options

    _LOGGER.info(f"Solis platform_config: {platform_config}")

    # fmt: off

    numberEntities: List[SolisNumberEntity] = []

    numbers = [
        {"type": "SNE", "name": "Solis Time-Charging Charge Current", "register": 43141,
         "default": 50.0, "multiplier": 10,
         "min_val": 0, "max_val": 135, "step": 0.1, "device_class": SensorDeviceClass.CURRENT,
         "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "enabled": True},
        {"type": "SNE", "name": "Solis Time-Charging Discharge Current", "register": 43142,
         "default": 50.0, "multiplier": 10,
         "min_val": 0, "max_val": 135, "step": 0.1, "device_class": SensorDeviceClass.CURRENT,
         "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "enabled": True},
        {"type": "SNE", "name": "Solis Backup SOC", "register": 43024,
         "default": 80.0, "multiplier": 1,
         "min_val": 0, "max_val": 100, "step": 1,
         "unit_of_measurement": PERCENTAGE, "enabled": True},
        {"type": "SNE", "name": "Solis Battery Force-charge Power Limitation", "register": 43027,
         "default": 3000.0, "multiplier": 0.1,
         "min_val": 0, "max_val": 6000, "step": 1,
         "unit_of_measurement": UnitOfPower.WATT, "enabled": True},

        {"type": "SNE", "name": "Solis Overcharge SOC", "register": 43010,
         "default": 90, "multiplier": 1,
         "min_val": 70, "max_val": 100, "step": 1,
         "unit_of_measurement": PERCENTAGE, "enabled": True},
        {"type": "SNE", "name": "Solis Overdischarge SOC", "register": 43011,
         "default": 20, "multiplier": 1,
         "min_val": 5, "max_val": 40, "step": 1,
         "unit_of_measurement": PERCENTAGE, "enabled": True},
        {"type": "SNE", "name": "Solis Force Charge SOC", "register": 43018,
         "default": 10, "multiplier": 1,
         "min_val": 0, "max_val": 100, "step": 1,
         "unit_of_measurement": PERCENTAGE, "enabled": True},
    ]

    for entity_definition in numbers:
        type = entity_definition["type"]
        if type == "SNE":
            numberEntities.append(SolisNumberEntity(hass, modbus_controller, entity_definition))
    hass.data[DOMAIN]['number_entities'] = numberEntities
    async_add_devices(numberEntities, True)

    @callback
    def update(now):
        """Update Modbus data periodically."""
        _LOGGER.info(f"calling number update for {len(hass.data[DOMAIN]['number_entities'])} groups")
        asyncio.gather(
            *[asyncio.to_thread(entity.update) for entity in hass.data[DOMAIN]["number_entities"]]
        )
        # Schedule the update function to run every X seconds

    async_track_time_interval(hass, update, timedelta(seconds=POLL_INTERVAL_SECONDS * 3))

    return True

    # fmt: on


class SolisNumberEntity(NumberEntity):
    """Representation of a Number entity."""

    def __init__(self, hass, modbus_controller, entity_definition):
        """Initialize the Number entity."""
        #
        # Visible Instance Attributes Outside Class
        self._hass = hass
        self._modbus_controller = modbus_controller
        self._register = entity_definition["register"]
        self._multiplier = entity_definition["multiplier"]

        # Hidden Inherited Instance Attributes
        self._attr_unique_id = "{}_{}_{}".format(DOMAIN, self._modbus_controller.host, self._register)
        self._attr_name = entity_definition["name"]
        self._attr_native_value = entity_definition.get("default", None)
        self._attr_assumed_state = entity_definition.get("assumed", False)
        self._attr_available = False
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
        _LOGGER.debug(f"async_added_to_hass {self._attr_name},  {self.entity_id},  {self.unique_id}")

    def update(self):
        """Update Modbus data periodically."""
        controller = self._hass.data[DOMAIN][CONTROLLER]
        self._attr_available = True

        value: float = self._hass.data[DOMAIN]['values'][str(self._register)]

        if value == 0:
            _LOGGER.debug(f'got 0 for register {self._register}, forcing update')
            value = controller.read_holding_register(self._register)[0]

        _LOGGER.debug(f'Update number entity with value = {value / self._multiplier}')

        self._attr_native_value = round(value / self._multiplier)

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._hass.data[DOMAIN][CONTROLLER].host)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"{MANUFACTURER} {MODEL}",
            sw_version=VERSION,
        )

    def set_native_value(self, value):
        """Update the current value."""
        if self._attr_native_value == value:
            return

        self._modbus_controller.write_holding_register(self._register, round(value * self._multiplier))
        self._attr_native_value = value
        self.schedule_update_ha_state()
