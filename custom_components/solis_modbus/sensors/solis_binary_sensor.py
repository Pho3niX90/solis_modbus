import logging
from typing import Any

from homeassistant.helpers.restore_state import RestoreEntity
from sqlalchemy.orm.sync import update

from custom_components.solis_modbus.helpers import cache_get, cache_save
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components.switch import SwitchEntity
from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, MANUFACTURER, REGISTER, VALUE
from custom_components.solis_modbus import ModbusController

_LOGGER = logging.getLogger(__name__)

class SolisBinaryEntity(RestoreEntity, SwitchEntity):

    def __init__(self, hass, modbus_controller, entity_definition):
        self._hass = hass
        self._modbus_controller: ModbusController = modbus_controller
        self._register: int = entity_definition.get("register", entity_definition.get("read_register")) + entity_definition.get("offset", 0)
        write_register = entity_definition.get("write_register", None)
        self._write_register: int = self._register if write_register is None else write_register + entity_definition.get("offset", 0)
        self._bit_position = entity_definition.get("bit_position", None)
        self._conflicts_with = entity_definition.get("conflicts_with", None)
        self._requires = entity_definition.get("requires", None)
        self._requires_any = entity_definition.get("requires_any", None)
        self._on_value = entity_definition.get("on_value", None)
        self._off_value = entity_definition.get("off_value", None)
        self._attr_unique_id = "{}_{}_{}_{}".format(DOMAIN, modbus_controller.identification if modbus_controller.identification is not None else modbus_controller.host, self._register,
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
        updated_controller = str(event.data.get(CONTROLLER))

        if updated_controller != self._modbus_controller.host:
            return # meant for a different sensor/inverter combo

        if updated_register == self._register:
            updated_value = int(event.data.get(VALUE))

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
            _LOGGER.debug(f"switch {self.unique_id} set to {self._attr_is_on}, value = {updated_value}")

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

    def set_register_bit(self, value: bool):
        """Set or clear a specific bit in the Modbus register, enforcing dependencies and conflicts."""
        controller = self._modbus_controller
        current_register_value: int = cache_get(self._hass, self._register)

        new_register_value = current_register_value

        if self._bit_position is not None:
            if value is True:
                # Clear conflicting bits
                if self._conflicts_with:
                    for cbit in self._conflicts_with:
                        new_register_value = set_bit(new_register_value, cbit, False)

                # Set required bits
                if self._requires:
                    for rbit in self._requires:
                        new_register_value = set_bit(new_register_value, rbit, True)

                # Set any of the allowed parents if needed (custom logic)
                if self._requires_any:
                    if not any(get_bit_bool(current_register_value, r) for r in self._requires_any):
                        # fallback to enabling the first one
                        new_register_value = set_bit(new_register_value, self._requires_any[0], True)

            # Set or clear target bit
            new_register_value = set_bit(new_register_value, self._bit_position, value)

        else:
            # Whole-register style bitless toggle
            if value is True and self._on_value is not None:
                new_register_value = self._on_value
            elif value is False and self._off_value is not None:
                new_register_value = self._off_value
            else:
                new_register_value = int(value)

        _LOGGER.debug(
            f"Attempting bit {self._bit_position} to {value} in register {self._register}. New value for register {new_register_value}"
        )

        if current_register_value != new_register_value and controller.connected():
            target_register = self._write_register
            self._hass.create_task(controller.async_write_holding_register(target_register, new_register_value))
            cache_save(self._hass, target_register, new_register_value)

        self._attr_is_on = value
        self._attr_available = True

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, "{}_{}_{}".format(self._modbus_controller.host, self._modbus_controller.slave, self._modbus_controller.identification))},
            manufacturer=MANUFACTURER,
            model=self._modbus_controller.model,
            name=f"{MANUFACTURER} {self._modbus_controller.model}{self._modbus_controller.device_identification}",
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
