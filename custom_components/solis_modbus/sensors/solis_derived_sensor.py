import decimal
import fractions
import logging
import numbers
from datetime import datetime, UTC
from typing import List

from homeassistant.components.sensor import RestoreSensor, SensorEntity, SensorDeviceClass
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.solis_modbus.const import DOMAIN, MANUFACTURER, REGISTER, VALUE, CONTROLLER, SLAVE
from custom_components.solis_modbus.data.status_mapping import STATUS_MAPPING
from custom_components.solis_modbus.helpers import decode_inverter_model, clock_drift_test, is_correct_controller
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

_LOGGER = logging.getLogger(__name__)

class SolisDerivedSensor(RestoreSensor, SensorEntity):
    """Representation of a Modbus derived/calculated sensor."""

    def __init__(self, hass: HomeAssistant, sensor: SolisBaseSensor):
        self._hass = hass if hass else sensor.hass
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
            if self.base_sensor.device_class != SensorDeviceClass.TIMESTAMP:
                self._attr_native_value = state.native_value
            else:
                self._attr_native_value = datetime.now(UTC)
        self.is_added_to_hass = True

        # 🔥 Register event listener for real-time updates
        self._hass.bus.async_listen(DOMAIN, self.handle_modbus_update)

    @callback
    def handle_modbus_update(self, event):
        """Callback function that updates sensor when new register data is available."""
        updated_register = int(event.data.get(REGISTER))
        updated_controller = str(event.data.get(CONTROLLER))
        updated_controller_slave = int(event.data.get(SLAVE))

        if not is_correct_controller(self.base_sensor.controller, updated_controller, updated_controller_slave):
            return # meant for a different sensor/inverter combo

        # Only process if this register belongs to the sensor
        if updated_register in self._register:
            self._received_values[updated_register] = event.data.get(VALUE)

            # If we haven't received all registers yet, wait
            filtered_registers = {reg for reg in self._register if reg not in (0, 1,90007)}
            if not all(reg in self._received_values for reg in filtered_registers):
                _LOGGER.debug(f"not all values received yet = {self._received_values}")
                return  # Wait until all registers are received

            ## start
            if 90007 in self._register:
                is_adjusted = clock_drift_test(self.hass, self.base_sensor.controller,
                                 self._received_values[33025],
                                 self._received_values[33026],
                                 self._received_values[33027],
                                 )
                if is_adjusted:
                    self._attr_available = True
                    self._attr_native_value = datetime.now(UTC)
                    self.schedule_update_ha_state()
                    self._received_values.clear()


            if 90006 in self._register:
                new_value = self.base_sensor.controller.last_modbus_success
                if new_value == 0 or new_value is None:
                    return
                self._attr_available = True
                self._attr_native_value = new_value
                self.schedule_update_ha_state()
                self._received_values.clear()
                return

            new_value = self.base_sensor.get_value

            if 33095 in self._register:
                new_value = round(self.base_sensor.get_value)
                new_value = STATUS_MAPPING.get(new_value, "Unknown")

            if 33049 in self._register or 33051 in self._register or 33053 in self._register or 33055 in self._register:
                r1_value = self._received_values[self._register[0]] * self.base_sensor.multiplier
                r2_value = self._received_values[self._register[1]] * self.base_sensor.multiplier
                new_value = round(r1_value * r2_value)

            if 33079  in self._register or 33080 in self._register or 33081 in self._register or 33082 in self._register:
                active_power = self.base_sensor.convert_value([self._received_values[self._register[0]], self._received_values[self._register[1]]])
                reactive_power = self.base_sensor.convert_value([self._received_values[self._register[2]], self._received_values[self._register[3]]])

                if active_power == 0 or reactive_power == 0:
                    new_value = 1
                else:
                    new_value = round(active_power / ((active_power**2 + reactive_power**2) ** 0.5),3)

            if 33135 in self._register and len(self._register) == 4:
                registers = self._register.copy()
                self._register = registers[:2]

                p_value = self.base_sensor.convert_value([self._received_values[reg] for reg in filtered_registers])
                d_w_value = registers[3]
                d_value = self._received_values[registers[2]]

                self._register = registers

                if str(d_value) == str(d_w_value):
                    new_value = round(p_value * 10)
                else:
                    new_value = 0

            if 33135 in self._register and len(self._register) == 3:
                registers = self._register.copy()
                self._register = registers[:2]

                p_value = self.base_sensor.convert_value([self._received_values[reg] for reg in filtered_registers])
                d_value = self._received_values[registers[2]]

                self._register = registers

                # 0 indicated charging, 1 indicated discharging
                if str(d_value) == str(0):
                    new_value = round(p_value * 10) * -1
                else:
                    new_value = round(p_value * 10)

            if 33263 in self._register and len(self._register) == 2:
                new_value = new_value * -1

            if 33175 in self._register or 33171 in self._register:
                # 33175 - to grid
                # 33171 - from grid
                to_grid = self._received_values[self._register[0]] * self.base_sensor.multiplier
                from_grid = self._received_values[self._register[1]] * self.base_sensor.multiplier
                new_value = from_grid - to_grid

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
            identifiers={(DOMAIN, "{}_{}_{}".format(self.base_sensor.controller.host, self.base_sensor.controller.slave, self.base_sensor.controller.identification))},
            manufacturer=MANUFACTURER,
            model=self.base_sensor.controller.model,
            name=f"{MANUFACTURER} {self.base_sensor.controller.model}{self.base_sensor.controller.identification}",
            sw_version=self.base_sensor.controller.sw_version,
        )