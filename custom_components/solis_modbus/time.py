"""

This is a docstring placeholder.

This is where we will describe what this module does

"""
import logging
from datetime import time
from datetime import timedelta
from typing import List

from homeassistant.components.number import NumberMode
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, VERSION, POLL_INTERVAL_SECONDS, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    """Set up the time platform."""
    modbus_controller = hass.data[DOMAIN][CONTROLLER]
    # We only want this platform to be set up via discovery.
    _LOGGER.info("Options %s", len(config_entry.options))

    platform_config = config_entry.data or {}
    if len(config_entry.options) > 0:
        platform_config = config_entry.options

    _LOGGER.info(f"Solis platform_config: {platform_config}")

    # fmt: off

    timeEntities: List[SolisTimeEntity] = []

    timeent = [
        {"type": "STE", "name": "Solis Time-Charging Charge Start (Slot 1)", "register": 43143, "enabled": True},
        {"type": "STE", "name": "Solis Time-Charging Charge End (Slot 1)", "register": 43145, "enabled": True},
        {"type": "STE", "name": "Solis Time-Charging Discharge Start (Slot 1)", "register": 43147, "enabled": True},
        {"type": "STE", "name": "Solis Time-Charging Discharge End (Slot 1)", "register": 43149, "enabled": True},

        {"type": "STE", "name": "Solis Time-Charging Charge Start (Slot 2)", "register": 43153, "enabled": True},
        {"type": "STE", "name": "Solis Time-Charging Charge End (Slot 2)", "register": 43155, "enabled": True},
        {"type": "STE", "name": "Solis Time-Charging Discharge Start (Slot 2)", "register": 43157, "enabled": True},
        {"type": "STE", "name": "Solis Time-Charging Discharge End (Slot 2)", "register": 43159, "enabled": True},

        {"type": "STE", "name": "Solis Time-Charging Charge Start (Slot 3)", "register": 43163, "enabled": True},
        {"type": "STE", "name": "Solis Time-Charging Charge End (Slot 3)", "register": 43165, "enabled": True},
        {"type": "STE", "name": "Solis Time-Charging Discharge Start (Slot 3)", "register": 43167, "enabled": True},
        {"type": "STE", "name": "Solis Time-Charging Discharge End (Slot 3)", "register": 43169, "enabled": True},
    ]

    for entity_definition in timeent:
        type = entity_definition["type"]
        if type == "STE":
            timeEntities.append(SolisTimeEntity(hass, modbus_controller, entity_definition))
    hass.data[DOMAIN]['time_entities'] = timeEntities
    async_add_devices(timeEntities, True)

    @callback
    def async_update(now):
        """Update Modbus data periodically."""
        for entity in hass.data[DOMAIN]["time_entities"]:
            entity.update()
        # Schedule the update function to run every X seconds

    async_track_time_interval(hass, async_update, timedelta(seconds=POLL_INTERVAL_SECONDS * 5))

    return True

    # fmt: on


class SolisTimeEntity(TimeEntity):
    """Representation of a Time entity."""

    def __init__(self, hass, modbus_controller, entity_definition):
        """Initialize the Time entity."""
        #
        # Visible Instance Attributes Outside Class
        self._hass = hass
        self._modbus_controller = modbus_controller
        self._register = entity_definition["register"]

        # Hidden Inherited Instance Attributes
        self._attr_unique_id = "{}_{}_{}".format(DOMAIN, self._modbus_controller.host, self._register)
        self._attr_name = entity_definition["name"]
        self._attr_native_value = entity_definition.get("default", None)
        self._attr_assumed_state = entity_definition.get("assumed", False)
        self._attr_available = False
        self._attr_device_class = entity_definition.get("device_class", None)
        self._attr_icon = entity_definition.get("icon", None)
        self._attr_mode = entity_definition.get("mode", NumberMode.AUTO)
        self._attr_should_poll = False
        self._attr_entity_registry_enabled_default = entity_definition.get("enabled", False)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _LOGGER.debug(f"async_added_to_hass {self._attr_name},  {self.entity_id},  {self.unique_id}")

    def update(self):
        """Update Modbus data periodically."""
        controller = self._hass.data[DOMAIN][CONTROLLER]
        self._attr_available = True

        hour = self._hass.data[DOMAIN]['values'][str(self._register)]
        minute = self._hass.data[DOMAIN]['values'][str(self._register + 1)]

        if hour == 0 or minute == 0:
            new_vals = controller.read_holding_register(self._register, count=2)
            hour = new_vals[0]
            minute = new_vals[1]

        _LOGGER.debug(f'Update time entity with hour = {hour}, minute = {minute}')

        self._attr_native_value = time(hour=hour, minute=minute)
        # self.async_write_ha_state()

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
        _LOGGER.debug(f'set_native_value : register = {self._register}, value = {value}')

    async def async_set_value(self, value: time) -> None:
        """Set the time."""
        _LOGGER.debug(f'async_set_value : register = {self._register}, value = {value}')
        self._modbus_controller.write_holding_registers(self._register, [value.hour, value.minute])
        self._attr_native_value = value
        self.async_write_ha_state()
