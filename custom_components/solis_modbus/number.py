"""

This is a docstring placeholder.

This is where we will describe what this module does

"""
import logging
from datetime import timedelta
from typing import List

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent, PERCENTAGE,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    VERSION, CONTROLLER, POLL_INTERVAL_SECONDS,
)

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
        {"type": "SNE", "name": "Solis Inverter Time-Charging Charge Current", "register": 43141,
         "default": 50.0, "multiplier": 10,
         "min_val": 0, "max_val": 100, "step": 0.1, "device_class": SensorDeviceClass.CURRENT,
         "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "enabled": True},
        {"type": "SNE", "name": "Solis Inverter Time-Charging Discharge Current", "register": 43142,
         "default": 50.0, "multiplier": 10,
         "min_val": 0, "max_val": 100, "step": 0.1, "device_class": SensorDeviceClass.CURRENT,
         "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "enabled": True},
        {"type": "SNE", "name": "Solis Inverter Backup SOC", "register": 43024,
         "default": 80.0, "multiplier": 1,
         "min_val": 0, "max_val": 100, "step": 1,
         "unit_of_measurement": PERCENTAGE, "enabled": True},
        # {"type": "SNE", "name": "Solis Inverter Storage Control Switch Value", "register": 43110,
        #  "default": 80.0, "multiplier": 1,
        #  "min_val": 0, "max_val": 100, "step": 1,
        #  "unit_of_measurement": PERCENTAGE, "enabled": True},
    ]

    for entity_definition in numbers:
        type = entity_definition["type"]
        if type == "SNE":
            numberEntities.append(SolisNumberEntity(hass, modbus_controller, entity_definition))
    hass.data[DOMAIN]['number_entities'] = numberEntities
    async_add_devices(numberEntities, True)

    @callback
    def async_update(now):
        """Update Modbus data periodically."""
        for entity in hass.data[DOMAIN]["number_entities"]:
            entity.update()
        # Schedule the update function to run every X seconds

    async_track_time_interval(hass, async_update, timedelta(seconds=POLL_INTERVAL_SECONDS * 5))

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

        _LOGGER.debug(f'Update number entity with value = {value  / self._multiplier}')

        self._attr_native_value = value / self._multiplier

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._hass.data[DOMAIN][CONTROLLER].host)},
            manufacturer="Solis",
            model="Solis S6",
            name="Solis S6",
            sw_version=VERSION,
        )

    def set_native_value(self, value):
        """Update the current value."""
        if self._attr_native_value == value:
            return

        _LOGGER.warning(
            f'Writing value to holding register = {self._register}, value = {value}, value modified = {value * self._multiplier}')
        self._modbus_controller.write_holding_register(self._register, round(value * self._multiplier))
        self._attr_native_value = value
        self.schedule_update_ha_state()
