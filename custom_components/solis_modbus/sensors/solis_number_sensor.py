import logging
from typing import List

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.template import is_number

from custom_components.solis_modbus.const import REGISTER, DOMAIN, VALUE, CONTROLLER, MANUFACTURER
from custom_components.solis_modbus.helpers import cache_get
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

_LOGGER = logging.getLogger(__name__)


class SolisNumberEntity(RestoreNumber, NumberEntity):
    """Representation of a Number entity."""

    def __init__(self, hass, sensor: SolisBaseSensor):
        self._hass = hass
        self.base_sensor = sensor

        self._attr_name = sensor.name
        self._attr_has_entity_name = True
        self._attr_unique_id = sensor.unique_id

        self._register: List[int] = sensor.registrars
        _LOGGER.debug(f"read_register = {sensor.registrars} | write_register {sensor.write_register}")
        self._write_register: int = sensor.write_register if sensor.write_register is not None else self._register[0] if len(self._register) == 1 else None

        self._device_class = sensor.device_class
        self._unit_of_measurement = sensor.unit_of_measurement
        self._attr_device_class = sensor.device_class
        self._attr_state_class = sensor.state_class
        self._attr_native_unit_of_measurement = sensor.unit_of_measurement
        self._attr_available = not sensor.hidden

        self._received_values = {}

        self._multiplier = sensor.multiplier

        # Unique ID based on all registers
        self._attr_native_value = sensor.default
        self._attr_mode = NumberMode.AUTO
        self._attr_native_min_value = sensor.min_value
        self._attr_native_max_value = sensor.max_value

        self._attr_native_step = sensor.step
        self._attr_step = sensor.step
        self._attr_should_poll = False
        self._attr_entity_registry_enabled_default = sensor.enabled

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_number_data()
        if state:
            self._attr_native_value = state.native_value
            self.adjust_min_max_step(state.native_min_value, state.native_max_value, state.native_step)

        # 🔥 Register event listener for real-time updates
        self._hass.bus.async_listen(DOMAIN, self.handle_modbus_update)

    def adjust_min_max_step(self, min_wanted: float | None, max_wanted: float | None, step_wanted: float | None):
        # float(43016) & equalization(43017) voltages, and rated capacity(43019)
        if 43016 in self._register or 43017 in self._register or 43019 in self._register:
            installed_battery = cache_get(self.hass, 43009)

            if is_number(installed_battery):
                # only supported with a user defined battery
                if installed_battery != 2 and not self.registry_entry.disabled:
                    self.registry_entry.disabled = True
                else:
                    self.registry_entry.disabled = False

        if self._attr_native_min_value != min_wanted and min_wanted is not None:
            self._attr_native_min_value = min_wanted
        if self._attr_native_step != step_wanted and step_wanted is not None:
            self._attr_native_step = step_wanted

    @callback
    def handle_modbus_update(self, event):
        """Callback function that updates sensor when new register data is available."""
        updated_register = int(event.data.get(REGISTER))
        updated_controller = str(event.data.get(CONTROLLER))

        if updated_controller != self.base_sensor.controller.host:
            return  # meant for a different sensor/inverter combo

        if updated_register in self._register:
            updated_value = int(event.data.get(VALUE))

            self._received_values[updated_register] = updated_value

            # Wait until all registers have been received
            if not all(reg in self._received_values for reg in self._register):
                _LOGGER.debug(f"not all values received yet = {self._received_values}")
                return

            new_value = self.base_sensor.convert_value([updated_value])

            # Clear received values after update
            self._received_values.clear()

            # Update state if valid value exists
            if new_value is not None:
                self._attr_native_value = new_value
                self.schedule_update_ha_state()

    def set_native_value(self, value):
        """Update the current value."""
        if self._attr_native_value == value:
            return

        # 🔹 Handle multi-register writing
        if self._write_register is None:
            return

        register_value = round(value / self._multiplier)

        # Write to Modbus controller
        self.hass.create_task(
            self.base_sensor.controller.async_write_holding_register(self._write_register, int(register_value))
        )

        self._attr_native_value = value
        self.schedule_update_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, "{}_{}_{}".format(self.base_sensor.controller.host, self.base_sensor.controller.slave, self.base_sensor.controller.identification))},
            manufacturer=MANUFACTURER,
            model=self.base_sensor.controller.model,
            name=f"{MANUFACTURER} {self.base_sensor.controller.model}{self.base_sensor.controller.device_identification}",
            sw_version=self.base_sensor.controller.sw_version,
        )
