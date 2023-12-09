import logging
from datetime import timedelta
from typing import List, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus.const import POLL_INTERVAL_SECONDS, DOMAIN, CONTROLLER, VERSION, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    modbus_controller = hass.data[DOMAIN][CONTROLLER]

    switch_sensors = [
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
            ]
        }
    ]

    switchEntities: List[SolisBinaryEntity] = []

    for main_entity in switch_sensors:
        for child_entity in main_entity['entities']:
            type = child_entity["type"]
            if type == "SBS":
                child_entity['read_register'] = main_entity['read_register']
                child_entity['write_register'] = main_entity['write_register']
                switchEntities.append(SolisBinaryEntity(hass, modbus_controller, child_entity))

    hass.data[DOMAIN]['switch_entities'] = switchEntities
    async_add_devices(switchEntities, True)

    @callback
    def async_update(now):
        """Update Modbus data periodically."""
        # for entity in hass.data[DOMAIN]["switch_entities"]:
        #    entity.update()
        # Schedule the update function to run every X seconds

    async_track_time_interval(hass, async_update, timedelta(seconds=POLL_INTERVAL_SECONDS * 5))

    return True


class SolisBinaryEntity(SwitchEntity):

    def __init__(self, hass, modbus_controller, entity_definition):
        self._hass = hass
        self._modbus_controller = modbus_controller
        self._read_register: int = entity_definition["read_register"]
        self._write_register: int = entity_definition["write_register"]
        self._bit_position = entity_definition["bit_position"]
        self._attr_unique_id = "{}_{}_{}_{}".format(DOMAIN, self._modbus_controller.host, self._read_register,
                                                    self._bit_position)
        self._attr_name = entity_definition["name"]
        self._attr_available = False
        self._attr_is_on = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _LOGGER.debug(f"async_added_to_hass {self._attr_name}")

    def update(self):
        """Update Modbus data periodically."""
        value: int = self._hass.data[DOMAIN]['values'][str(self._read_register)]

        initial_state = self._attr_is_on
        if not self._attr_available:
            self._attr_available = True
        self._attr_is_on = get_bool(value, self._bit_position)

        if initial_state != self._attr_is_on:
            _LOGGER.debug(
                f'state change for {self._read_register}-{self._bit_position} from {initial_state} to {self._attr_is_on}')
        return self._attr_is_on

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._attr_is_on

    def turn_on(self, **kwargs: Any) -> None:
        _LOGGER.debug(f"{self._read_register}-{self._bit_position} turn on called ")
        self.set_register_bit(True)

    def turn_off(self, **kwargs: Any) -> None:
        _LOGGER.debug(f"{self._read_register}-{self._bit_position} turn off called ")
        self.set_register_bit(False)

    def set_register_bit(self, value):
        """Set or clear a specific bit in the Modbus register."""
        controller = self._hass.data[DOMAIN][CONTROLLER]
        current_register_value: int = self._hass.data[DOMAIN]['values'][str(self._read_register)]
        new_register_value: int = set_bit(current_register_value, self._bit_position, value)

        _LOGGER.debug(
            f"Attempting bit {self._bit_position} to {value} in register {self._read_register}. New value for register {new_register_value}")
        # we only want to write when values has changed. After, we read the register again to make sure it applied.
        if current_register_value != new_register_value:
            controller.write_holding_register(self._write_register, new_register_value)
            self._hass.data[DOMAIN]['values'][str(self._read_register)] = new_register_value

        self._attr_is_on = value

        self._attr_available = True

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
