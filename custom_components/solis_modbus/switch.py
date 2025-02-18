import logging
from datetime import timedelta
from typing import List, Any

from homeassistant.components.sensor import RestoreSensor
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, MANUFACTURER, \
    VALUES, ENTITIES, SWITCH_ENTITIES, REGISTER, VALUE
from custom_components.solis_modbus.helpers import cache_get, cache_save

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    modbus_controller: ModbusController = hass.data[DOMAIN][CONTROLLER][config_entry.data.get("host")]

    inverter_type = config_entry.data.get("type", "hybrid")

    if inverter_type == 'string':
        return False

    switch_sensors = [
        {
            "register": 5,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Modbus Enabled"},
            ]
        },
        {
            "register": 43110,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Self-Use Mode", "work_mode": (0,6,11)},
                {"type": "SBS", "bit_position": 1, "name": "Solis Time Of Use Mode"},
                {"type": "SBS", "bit_position": 2, "name": "Solis OFF-Grid Mode"},
                {"type": "SBS", "bit_position": 3, "name": "Solis Battery Wakeup Switch"},
                {"type": "SBS", "bit_position": 4, "name": "Solis Reserve Battery Mode", "work_mode": (4,11)},
                {"type": "SBS", "bit_position": 5, "name": "Solis Allow Grid To Charge The Battery"},
                {"type": "SBS", "bit_position": 6, "name": "Solis Feed In Priority Mode", "work_mode": (0,6,11)},
                {"type": "SBS", "bit_position": 7, "name": "Solis Batt OVC"},
                {"type": "SBS", "bit_position": 8, "name": "Solis Battery Forcecharge Peakshaving"},
                {"type": "SBS", "bit_position": 9, "name": "Solis Battery current correction"},
                {"type": "SBS", "bit_position": 10, "name": "Solis Battery healing mode"},
                {"type": "SBS", "bit_position": 11, "name": "Solis Peak-shaving Mode", "work_mode": (0,4,6,11)},
            ]
        },{
            "register": 43365,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Generator connection position"},
                {"type": "SBS", "bit_position": 1, "name": "Solis With Generator"},
                {"type": "SBS", "bit_position": 2, "name": "Solis Generator enable signal"},
                {"type": "SBS", "bit_position": 3, "name": "Solis AC Coupling Position (off = GEN port, on = Backup port)"},
                {"type": "SBS", "bit_position": 4, "name": "Solis Generator access location"},
            ]
        },{
            "register": 43815,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Generator charging period 1 switch"},
                {"type": "SBS", "bit_position": 1, "name": "Solis Generator charging period 2 switch"},
                {"type": "SBS", "bit_position": 2, "name": "Solis Generator charging period 3 switch"},
                {"type": "SBS", "bit_position": 3, "name": "Solis Generator charging period 4 switch"},
                {"type": "SBS", "bit_position": 4, "name": "Solis Generator charging period 5 switch"},
                {"type": "SBS", "bit_position": 5, "name": "Solis Generator charging period 6 switch"},
            ]
        },{
            "register": 43340,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "Solis Generator Input Mode (off = Manual, on = Auto)"},
                {"type": "SBS", "bit_position": 1, "name": "Solis Generator Charge Enable"},
            ]
        },{
            "register": 43483,
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
        }, {
            "register": 43249,
            "entities": [
                {"type": "SBS", "bit_position": 0, "name": "MPPT Parallel Function"},
                {"type": "SBS", "bit_position": 1, "name": "IgFollow"},
                {"type": "SBS", "bit_position": 2, "name": "Relay Protection"},
                {"type": "SBS", "bit_position": 3, "name": "I-Leak Protection"},
                {"type": "SBS", "bit_position": 4, "name": "PV ISO Protection"},
                {"type": "SBS", "bit_position": 5, "name": "Grid-Interference Protection"},
                {"type": "SBS", "bit_position": 6, "name": "The DC component of the grid current protection switch"},
                {"type": "SBS", "bit_position": 7, "name": "Const Voltage Mode Enable Const Voltage"},
            ]
        }, {
            "register": 43135,
            "entities": [
                {"type": "SBS", "name": "Solis RC Force Battery Discharge", "on_value": 1},
                {"type": "SBS", "name": "Solis RC Force Battery Charge",  "on_value": 2}
            ]
        }, {
            "register": 43707,
            "entities": [
                {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 1", "bit_position": 0},
                {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 2", "bit_position": 1},
                {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 3", "bit_position": 2},
                {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 4", "bit_position": 3},
                {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 5", "bit_position": 4},
                {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 6", "bit_position": 5},
                {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 1", "bit_position": 6},
                {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 2", "bit_position": 7},
                {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 3", "bit_position": 8},
                {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 4", "bit_position": 9},
                {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 5", "bit_position": 10},
                {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 6", "bit_position": 11},
            ]
        }
    ]

    switchEntities: List[SolisBinaryEntity] = []

    for main_entity in switch_sensors:
        for child_entity in main_entity[ENTITIES]:
            type = child_entity["type"]
            if type == "SBS":
                child_entity['register'] = main_entity['register']
                switchEntities.append(SolisBinaryEntity(hass, modbus_controller, child_entity))

    hass.data[DOMAIN][SWITCH_ENTITIES] = switchEntities
    async_add_devices(switchEntities, True)

    return True


class SolisBinaryEntity(RestoreSensor, SwitchEntity):

    def __init__(self, hass, modbus_controller, entity_definition):
        self._hass = hass
        self._modbus_controller: ModbusController = modbus_controller
        self._register: int = entity_definition["register"]
        self._bit_position = entity_definition.get("bit_position", None)
        self._work_mode = entity_definition.get("work_mode", None)
        self._on_value = entity_definition.get("on_value", None)
        self._attr_unique_id = "{}_{}_{}_{}".format(DOMAIN, self._modbus_controller.host, self._register,
                                                    self._on_value if self._on_value is not None else self._bit_position)
        self._attr_name = entity_definition["name"]
        self._attr_has_entity_name = True
        self._attr_available = False
        self._attr_is_on = None
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

        if updated_controller != self._modbus_controller.host:
            return # meant for a different sensor/inverter combo

        # If this register belongs to the sensor, store it temporarily
        if updated_register == self._register:
            self._received_values[updated_register] = updated_value

            if self._register == 5:
                self._attr_is_on = self._modbus_controller.enabled
                self._attr_available = True
                return self._attr_is_on

            value = updated_value
            if value is None:
                value = cache_get(self._hass, self._register)

            if value is not None:
                self._attr_available = True
                if self._bit_position is not None:
                    self._attr_is_on = get_bool(value, self._bit_position)
                if self._on_value is not None:
                    self._attr_is_on = value == self._on_value

    def update(self):
        """Update Modbus data periodically."""
        return self._attr_is_on

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._attr_is_on

    def turn_on(self, **kwargs: Any) -> None:
        _LOGGER.debug(f"{self._register}-{self._bit_position} turn on called ")
        if self._register == 5:
            self._modbus_controller.enable_connection()
        else:
            self.set_register_bit(True)

    def turn_off(self, **kwargs: Any) -> None:
        _LOGGER.debug(f"{self._register}-{self._bit_position} turn off called ")
        if self._register == 5:
            self._modbus_controller.disable_connection()
        else:
            self.set_register_bit(False)

    def set_register_bit(self, value):
        """Set or clear a specific bit in the Modbus register."""
        controller = self._modbus_controller
        current_register_value: int = cache_get(self._hass, self._register)

        if self._bit_position is not None:
            if value is True and self._work_mode is not None:
                for wbit in self._work_mode:
                    current_register_value = set_bit(current_register_value, wbit, False)
            new_register_value: int = set_bit(current_register_value, self._bit_position, value)

        else:
            new_register_value: int = value

        _LOGGER.debug(
            f"Attempting bit {self._bit_position} to {value} in register {self._register}. New value for register {new_register_value}")
        # we only want to write when values has changed. After, we read the register again to make sure it applied.
        if current_register_value != new_register_value and controller.connected():
            self._hass.create_task(controller.async_write_holding_register(self._register, new_register_value))
            cache_save(self._hass, self._register, new_register_value)

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
