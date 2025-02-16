from homeassistant.core import HomeAssistant

from custom_components.solis_modbus import ModbusController, CONTROLLER
from typing import List
from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.const import DOMAIN

from custom_components.solis_modbus.const import REGISTER, VALUE
from custom_components.solis_modbus.helpers import get_controller
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

from homeassistant.core import callback

class SolisSensor(RestoreSensor, SensorEntity):
    """Representation of a Modbus sensor."""

    def __init__(self, hass: HomeAssistant, sensor: SolisBaseSensor):
        self._hass = hass
        self._modbus_controller: ModbusController = get_controller(hass, sensor.controller_host)

        self._attr_name = sensor.name
        self._attr_has_entity_name = True
        self._attr_unique_id = sensor.unique_id

        self._register: List[int] = sensor.registrars
        self._unit_of_measurement = sensor.unit_of_measurement
        self._device_class = sensor.device_class

        self.is_added_to_hass = False
        self._state = None
        self.base_sensor = sensor
        self._received_values = {}

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to HA."""
        await super().async_added_to_hass()
        sensor_data = await self.async_get_last_sensor_data()
        if sensor_data.native_value is not None:
            self._attr_native_value = sensor_data.native_value

        self.is_added_to_hass = True

        # 🔥 Register event listener for real-time updates
        self._hass.bus.async_listen(DOMAIN, self.handle_modbus_update)

    @callback
    def handle_modbus_update(self, event):
        """Callback function that updates sensor when new register data is available."""
        updated_register = int(event.data.get(REGISTER))
        updated_value = int(event.data.get(VALUE))
        updated_controller = int(event.data.get(CONTROLLER))

        if updated_controller != self._modbus_controller.host:
            return # meant for a different sensor/inverter combo

        # Only process if this register belongs to the sensor
        if updated_register in self._register:
            # Store received register value temporarily
            self._received_values[updated_register] = updated_value

            # If we haven't received all registers yet, wait
            if not all(reg in self._received_values for reg in self._register):
                return  # Wait until all registers are received

            new_value = self.base_sensor.get_value

            # Clear received values after update
            self._received_values.clear()

            # Update state if valid value exists
            if new_value is not None:
                self._attr_native_value = new_value
                self.schedule_update_ha_state()



    @property
    def native_value(self):
        """Retrieve sensor value from cache."""
        return self.base_sensor.get_value()

