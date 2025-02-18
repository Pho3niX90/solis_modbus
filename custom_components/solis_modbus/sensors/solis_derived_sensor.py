import decimal
import fractions
import logging
import numbers
from typing import List

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.solis_modbus.const import DOMAIN, MANUFACTURER, REGISTER, VALUE, CONTROLLER
from custom_components.solis_modbus.helpers import get_value, decode_inverter_model
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor
from custom_components.solis_modbus.status_mapping import STATUS_MAPPING

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

class SolisDerivedSensor(RestoreSensor, SensorEntity):
    """Representation of a Modbus derived/calculated sensor."""

    def __init__(self, hass, sensor: SolisBaseSensor):
        self._hass = hass if hass else sensor.hass
        self._attr_name = sensor.name
        self._attr_has_entity_name = True
        self._attr_unique_id = sensor.unique_id
        self.base_sensor = sensor

        self._device_class = sensor.device_class
        self._unit_of_measurement  = sensor.unit_of_measurement
        self._attr_device_class = sensor.device_class
        self._attr_state_class = sensor.state_class
        self._attr_native_unit_of_measurement = sensor.unit_of_measurement

        self._register: List[int] = sensor.registrars
        self._state = None

        # Visible Instance Attributes Outside Class
        self.is_added_to_hass = False
        self._multiplier = sensor.multiplier
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

        # Only process if this register belongs to the sensor
        if updated_register in self._register:
            # Store received register value temporarily
            self._received_values[updated_register] = updated_value

            # If we haven't received all registers yet, wait
            if not all(reg in self._received_values for reg in self._register):
                _LOGGER.debug(f"not all values received yet = {self._received_values}")
                return  # Wait until all registers are received

            new_value = self.base_sensor.get_value

            ## start

            if 33095 in self._register:
                new_value = round(get_value(self))
                new_value = STATUS_MAPPING.get(new_value, "Unknown")

            if 33049 in self._register or 33051 in self._register or 33053 in self._register or 33055 in self._register:
                r1_value = self._received_values[self._register[0]] * self._multiplier
                r2_value = self._received_values[self._register[1]] * self._multiplier
                new_value = round(r1_value * r2_value)

            if 33135 in self._register and len(self._register) == 4:
                registers = self._register.copy()
                self._register = registers[:2]

                p_value = get_value(self)
                d_w_value = registers[3]
                d_value = self._received_values[registers[2]]

                self._register = registers

                if str(d_value) == str(d_w_value):
                    new_value = round(p_value * 10)
                else:
                    new_value = 0

            # set after
            if 35000 in self._register:
                protocol_version, model_description = decode_inverter_model(new_value)
                self.base_sensor.controller._sw_version = protocol_version
                self.base_sensor.controller._model = model_description
                new_value = model_description + f"(Protocol {protocol_version})"

            if isinstance(new_value, (numbers.Number, decimal.Decimal, fractions.Fraction)) or isinstance(new_value, str):
                self._attr_available = True
                self._attr_native_value = new_value
                self._state = new_value
                self.schedule_update_ha_state()

            # Update state if valid value exists
            if new_value is not None:
                self._attr_native_value = new_value
                self.schedule_update_ha_state()

            # Clear received values after update
            self._received_values.clear()

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