import logging
from datetime import timedelta
from typing import List, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, MANUFACTURER, \
    VALUES, ENTITIES, SWITCH_ENTITIES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    modbus_controller: ModbusController = hass.data[DOMAIN][CONTROLLER][config_entry.data.get("host")]

    inverter_type = config_entry.data.get("type", "hybrid")

    if inverter_type == 'string':
        return False

    switch_sensors = [
        {
            "read_register": 5, 'write_register': 5,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Modbus Enabled"},
            ]
        },
        {
            "read_register": 33132, 'write_register': 43110,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Self-Use Mode"},
                {"type": "SBS", "bit_position": 1, "name": "Solis Time Of Use Mode"},
                {"type": "SBS", "bit_position": 2, "name": "Solis OFF-Grid Mode"},
                {"type": "SBS", "bit_position": 3, "name": "Solis Battery Wakeup Switch"},
                {"type": "SBS", "bit_position": 4, "name": "Solis Reserve Battery Mode"},
                {"type": "SBS", "bit_position": 5, "name": "Solis Allow Grid To Charge The Battery"},
                {"type": "SBS", "bit_position": 6, "name": "Solis Feed In Priority Mode"},
                {"type": "SBS", "bit_position": 7, "name": "Solis Batt OVC"},
                {"type": "SBS", "bit_position": 8, "name": "Solis Battery Forcecharge Peakshaving"},
                {"type": "SBS", "bit_position": 9, "name": "Solis Battery current correction"},
                {"type": "SBS", "bit_position": 10, "name": "Solis Battery healing mode"},
                {"type": "SBS", "bit_position": 11, "name": "Solis Peak-shaving mode"},
            ]
        },{
            "read_register": 43365, "write_register": 43365,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Generator connection position"},
                {"type": "SBS", "bit_position": 1, "name": "Solis With Generator"},
                {"type": "SBS", "bit_position": 2, "name": "Solis Generator enable signal"},
                {"type": "SBS", "bit_position": 3, "name": "Solis AC Coupling Position (off = GEN port, on = Backup port)"},
                {"type": "SBS", "bit_position": 4, "name": "Solis Generator access location"},
            ]
        },{
            "read_register": 43815, "write_register": 43815,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Generator charging period 1 switch"},
                {"type": "SBS", "bit_position": 1, "name": "Solis Generator charging period 2 switch"},
                {"type": "SBS", "bit_position": 2, "name": "Solis Generator charging period 3 switch"},
                {"type": "SBS", "bit_position": 3, "name": "Solis Generator charging period 4 switch"},
                {"type": "SBS", "bit_position": 4, "name": "Solis Generator charging period 5 switch"},
                {"type": "SBS", "bit_position": 5, "name": "Solis Generator charging period 6 switch"},
            ]
        },{
            "read_register": 43340, "write_register": 43340,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Generator Input Mode (off = Manual, on = Auto)"},
                {"type": "SBS", "bit_position": 1, "name": "Solis Generator Charge Enable"},
            ]
        },{
            "read_register": 43483, "write_register": 43483,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Dual Backup Enable"},
                {"type": "SBS", "bit_position": 1, "name": "Solis AC Coupling Enable"},
                {"type": "SBS", "bit_position": 2, "name": "Solis Smart load port grid-connected forced output"},
                {"type": "SBS", "bit_position": 3, "name": "Solis Allow export switch under self-generation and self-use"},
                {"type": "SBS", "bit_position": 4, "name": "Solis Backup2Load manual/automatic switch (off = Manual, on = Automatic"},
                {"type": "SBS", "bit_position": 5, "name": "Solis Backup2Load manual enable"},
                {"type": "SBS", "bit_position": 6, "name": "Solis Smart load port stops output when off-grid"},
                {"type": "SBS", "bit_position": 7, "name": "Solis Grid Peak-shaving power enable"},
            ]
        },{
            "read_register": 43135, "write_register": 43135,
            "entities": [
                {"type": "SBS", "on_value": 1, "name": "Solis RC Force Battery Charge/discharge"},
            ]
        }
    ]

    switchEntities: List[SolisBinaryEntity] = []

    for main_entity in switch_sensors:
        for child_entity in main_entity[ENTITIES]:
            type = child_entity["type"]
            if type == "SBS":
                child_entity['read_register'] = main_entity['read_register']
                child_entity['write_register'] = main_entity['write_register']
                switchEntities.append(SolisBinaryEntity(hass, modbus_controller, child_entity))

    hass.data[DOMAIN][SWITCH_ENTITIES] = switchEntities
    async_add_devices(switchEntities, True)

    @callback
    def async_update(now):
        """Update Modbus data periodically."""
        # for entity in hass.data[DOMAIN]["switch_entities"]:
        #    entity.update()
        # Schedule the update function to run every X seconds

    async_track_time_interval(hass, async_update, timedelta(seconds=modbus_controller.poll_interval * 2))

    return True


class SolisBinaryEntity(SwitchEntity):

    def __init__(self, hass, modbus_controller, entity_definition):
        self._hass = hass
        self._modbus_controller: ModbusController = modbus_controller
        self._read_register: int = entity_definition["read_register"]
        self._write_register: int = entity_definition["write_register"]
        self._bit_position = entity_definition.get("bit_position", None)
        self._on_value = entity_definition.get("on_value", None)
        self._attr_unique_id = "{}_{}_{}_{}".format(DOMAIN, self._modbus_controller.host, self._read_register,
                                                    self._bit_position)
        self._attr_name = entity_definition["name"]
        self._attr_has_entity_name = True
        self._attr_available = False
        self._attr_is_on = None

    def update(self):
        """Update Modbus data periodically."""

        if self._read_register == 5:
            self._attr_is_on = self._modbus_controller.enabled
            if not self._attr_available:
                self._attr_available = True
            return self._attr_is_on

        value: int = self._hass.data[DOMAIN][VALUES].get(str(self._read_register), None)

        if value is not None:
            initial_state = self._attr_is_on
            if not self._attr_available:
                self._attr_available = True
            if self._bit_position is not None:
                self._attr_is_on = get_bool(value, self._bit_position)
            if self._on_value is not None:
                self._attr_is_on = value == self._on_value
        return self._attr_is_on

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._attr_is_on

    def turn_on(self, **kwargs: Any) -> None:
        _LOGGER.debug(f"{self._read_register}-{self._bit_position} turn on called ")
        if self._read_register == 5:
            self._modbus_controller.enabled = True
            self._modbus_controller.connect()
        else:
            self.set_register_bit(True)

    def turn_off(self, **kwargs: Any) -> None:
        _LOGGER.debug(f"{self._read_register}-{self._bit_position} turn off called ")
        if self._read_register == 5:
            self._modbus_controller.enabled = False
            self._modbus_controller.disconnect()
        else:
            self.set_register_bit(False)

    def set_register_bit(self, value):
        """Set or clear a specific bit in the Modbus register."""
        controller = self._modbus_controller
        current_register_value: int = self._hass.data[DOMAIN][VALUES][str(self._read_register)]

        if self._bit_position is not None:
            new_register_value: int = set_bit(current_register_value, self._bit_position, value)
        else:
            new_register_value: int = value

        _LOGGER.debug(
            f"Attempting bit {self._bit_position} to {value} in register {self._read_register}. New value for register {new_register_value}")
        # we only want to write when values has changed. After, we read the register again to make sure it applied.
        if current_register_value != new_register_value and controller.connected():
            self._hass.create_task(controller.async_write_holding_register(self._write_register, new_register_value))
            self._hass.data[DOMAIN][VALUES][str(self._read_register)] = new_register_value

        self._attr_is_on = value

        self._attr_available = True

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


def set_bit(value, bit_position, new_bit_value):
    """Set or clear a specific bit in an integer value."""
    mask = 1 << bit_position
    value &= ~mask  # Clear the bit
    if new_bit_value:
        value |= mask  # Set the bit
    return round(value)


def get_bool(modbus_value, bit_position):
    """
    Decode Modbus value to boolean state for the specified bit position.

    Parameters:
    - modbus_value: The Modbus value to decode.
    - bit_position: The position of the bit to extract (0-based).

    Returns:
    - True if the bit is ON, False if the bit is OFF.
    """
    # Check if the bit is ON by shifting 1 to the specified position and performing bitwise AND
    return (modbus_value >> bit_position) & 1 == 1
