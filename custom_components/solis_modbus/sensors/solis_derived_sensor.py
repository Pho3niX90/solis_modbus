import decimal
import fractions
import numbers
from typing import List

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.solis_modbus.const import DOMAIN, MANUFACTURER
from custom_components.solis_modbus.helpers import get_value, decode_inverter_model
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor
from custom_components.solis_modbus.status_mapping import STATUS_MAPPING


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

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value
        self.is_added_to_hass = True

    def update(self):
        """Update the sensor value."""
        try:
            if not self.is_added_to_hass:
                return

            n_value = None

            if '33095' in self._register:
                n_value = round(get_value(self))
                n_value = STATUS_MAPPING.get(n_value, "Unknown")

            if '33049' in self._register or '33051' in self._register or '33053' in self._register or '33055' in self._register:
                r1_value = self._hass.data[DOMAIN]['values'][self._register[0]] * self._multiplier
                r2_value = self._hass.data[DOMAIN]['values'][self._register[1]] * self._multiplier
                n_value = round(r1_value * r2_value)

            if '33135' in self._register and len(self._register) == 4:
                registers = self._register.copy()
                self._register = registers[:2]

                p_value = get_value(self)
                d_w_value = registers[3]
                d_value = self._hass.data[DOMAIN]['values'][registers[2]]

                self._register = registers

                if str(d_value) == str(d_w_value):
                    n_value = round(p_value * 10)
                else:
                    n_value = 0

            # set after
            if '35000' in self._register:
                protocol_version, model_description = decode_inverter_model(n_value)
                self.base_sensor.controller._sw_version = protocol_version
                self.base_sensor.controller._model = model_description
                n_value = model_description + f"(Protocol {protocol_version})"

            if isinstance(n_value, (numbers.Number, decimal.Decimal, fractions.Fraction)):
                self._attr_available = True
                self._attr_native_value = n_value
                self._state = n_value
                self.schedule_update_ha_state()
            if isinstance(n_value, str):
                self._attr_available = True
                self._attr_native_value = n_value
                self._state = n_value
                self.schedule_update_ha_state()

        except ValueError as e:
            self._state = None
            self._attr_available = False

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