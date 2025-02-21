import logging

from homeassistant.core import HomeAssistant

from typing import List
from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.solis_modbus.const import DOMAIN, MANUFACTURER

from custom_components.solis_modbus.const import REGISTER, VALUE, CONTROLLER
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

class SolisSensor(RestoreSensor, SensorEntity):
    """Representation of a Modbus sensor."""

    def __init__(self, hass: HomeAssistant, sensor: SolisBaseSensor):
        self._hass = hass
        self.base_sensor = sensor

        self._attr_name = sensor.name
        self._attr_has_entity_name = True
        self._attr_unique_id = sensor.unique_id

        self._register: List[int] = sensor.registrars

        self._device_class = sensor.device_class
        self._unit_of_measurement  = sensor.unit_of_measurement
        self._attr_device_class = sensor.device_class
        self._attr_state_class = sensor.state_class
        self._attr_native_unit_of_measurement = sensor.unit_of_measurement
        self._attr_available = not sensor.hidden

        self.is_added_to_hass = False
        self._state = None
        self._received_values = {}

    async def async_added_to_hass(self) -> None:
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

        if updated_controller != self.base_sensor.controller.host:
            return # meant for a different sensor/inverter combo

        if updated_register in self._register:
            self._received_values[updated_register] = updated_value

            # If we haven't received all registers yet, wait
            if not all(reg in self._received_values for reg in self._register):
                _LOGGER.debug(f"not all values received yet = {self._received_values}")
                return

            values = [self._received_values[reg] for reg in self._register]

            if None in values:
                problematic_regs = {reg: self._received_values.get(reg) for reg in self._register if self._received_values.get(reg) is None}
                if problematic_regs:
                    _LOGGER.debug(f"⚠️ Problematic values received in registrars: {problematic_regs}, skipping update")
                    return

            new_value = self.base_sensor.convert_value([self._received_values[reg] for reg in self._register])

            # Clear received values after update
            self._received_values.clear()

            # Update state if valid value exists
            if new_value is not None:
                self._attr_native_value = new_value
                self.schedule_update_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.base_sensor.controller.host)},
            manufacturer=MANUFACTURER,
            model=self.base_sensor.controller.model,
            name=f"{MANUFACTURER} {self.base_sensor.controller.model}",
            sw_version=self.base_sensor.controller.sw_version,
        )