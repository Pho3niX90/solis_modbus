import logging
from typing import Any

from custom_components.solis_modbus.helpers import cache_get, cache_save
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components.switch import SwitchEntity
from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, MANUFACTURER, REGISTER, VALUE
from custom_components.solis_modbus import ModbusController

_LOGGER = logging.getLogger(__name__)

class SolisBinaryEntity(SwitchEntity):

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
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to HA."""
        await super().async_added_to_hass()

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
            if self._bit_position is not None:
                _LOGGER.debug(f"Sensor update received, register = {updated_register}, value = {updated_value}, get_bit_bool = {get_bit_bool(updated_value, self._bit_position)}")
            else:
                _LOGGER.debug(f"Sensor update received, register = {updated_register}, value = {updated_value}, on_value = {self._on_value}, is_on = {self._on_value == updated_value}, ")

            if self._register == 5:
                self._attr_is_on = self._modbus_controller.enabled
                self._attr_available = True
                return self._attr_is_on

            value = updated_value

            if value is None:
                value = cache_get(self._hass, self._register)

            self._attr_available = True
            if self._bit_position is not None:
                self._attr_is_on = get_bit_bool(value, self._bit_position)
            if self._on_value is not None:
                self._attr_is_on = value == self._on_value
            _LOGGER.debug(f"switch {self.unique_id} set to {self._attr_is_on}")

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
            new_register_value: int = self._on_value if value is True else value

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


def get_bit_bool(modbus_value, bit_position):
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
