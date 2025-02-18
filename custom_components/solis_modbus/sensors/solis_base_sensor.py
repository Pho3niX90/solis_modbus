# solis_base.py
import logging
from typing import Union

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential, UnitOfApparentPower, UnitOfPower, \
    UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from typing_extensions import List, Optional

from custom_components.solis_modbus.const import DOMAIN
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.helpers import cache_get, extract_serial_number

_LOGGER = logging.getLogger(__name__)

class SolisBaseSensor:
    """Base class for all Solis sensors."""

    def __init__(self,
                 hass: HomeAssistant,
                 controller,
                 unique_id: str,
                 name: str,
                 registrars: List[int],
                 multiplier: float,
                 device_class: Union[SwitchDeviceClass, SensorDeviceClass, str] = None,
                 unit_of_measurement: UnitOfElectricPotential | UnitOfApparentPower | UnitOfElectricCurrent | UnitOfPower = None,
                 editable: bool = False,
                 state_class: SensorStateClass = None,
                 default = None,
                 step = 0.1,
                 hidden = False,
                 enabled = True,
                 min_value: Optional[int] = None, max_value: Optional[int] = None):
        """
        :param name: Sensor name
        :param registrars: First register address
        """
        self.hass = hass
        self.unique_id = unique_id
        self.controller = controller
        self.name = name
        self.default = default
        self.registrars = registrars
        self.editable = editable
        self.multiplier = multiplier
        self.device_class = device_class
        self.unit_of_measurement = unit_of_measurement
        self.hidden = hidden
        self.state_class = state_class
        self.max_value = max_value
        self.step = self.get_step(step)
        self.enabled = enabled
        self.min_value = min_value

    @property
    def min_max(self):
        if self.min_value is not None and self.max_value is not None:
            return self.min_value, self.max_value
        if self.device_class == PERCENTAGE:
            return 0,100
        if self.device_class == UnitOfPower.KILO_WATT:
            return 0,6
        if self.device_class == UnitOfPower.WATT:
            return 0,6000


    def get_step(self, wanted_step):
        if self.device_class == PERCENTAGE:
            return 1
        if self.device_class == UnitOfPower.KILO_WATT:
            return 0,1
        if self.device_class == UnitOfPower.WATT:
            return 1
        return wanted_step

    @property
    def get_raw_values(self):
        return [cache_get(self.hass, reg) for reg in self.registrars]

    @property
    def get_value(self):
        return self._convert_raw_value()

    def _convert_raw_value(self):
        values = self.get_raw_values

        if None in values:
            return None

        if len(self.registrars) >= 15:
            values = values
            n_value = extract_serial_number(values)
        elif len(self.registrars) > 1:
            s32_values = values
            # These are two 16-bit values representing a 32-bit signed/unsigned integer (S32/U32)
            high_word = s32_values[0] - (1 << 16) if s32_values[0] & (1 << 15) else s32_values[0]
            low_word = s32_values[1] - (1 << 16) if s32_values[1] & (1 << 15) else s32_values[1]

            # Combine the high and low words to form a 32-bit signed/unsigned integer
            combined_value = (high_word << 16) | (low_word & 0xFFFF)
            if self.multiplier == 0 or self.multiplier == 1:
                n_value = round(combined_value)
            else:
                n_value = combined_value * self.multiplier
        else:
            # Treat it as a single register (U16/S16)
            if self.multiplier == 0 or self.multiplier == 1:
                n_value = round(values[0])
            else:
                n_value = values[0] * self.multiplier

        return n_value

    def get_info(self):
        """Return basic sensor information."""
        return {
            "name": self.name,
            "registrars": self.registrars
        }

class SolisSensorGroup:
    sensors: List[SolisBaseSensor]

    def __init__(self, hass, definition, controller):
        self.poll_speed: PollSpeed = definition.get("poll_speed", PollSpeed.NORMAL)
        self._sensors = list(map(lambda entity: SolisBaseSensor(
            hass=hass,
            name= entity.get("name", "reserve"),
            controller=controller,
            registrars=[int(r) for r in entity["register"]],
            state_class=entity.get("state_class", None),
            device_class=entity.get("device_class", None),
            unit_of_measurement=entity.get("unit_of_measurement", None),
            hidden=entity.get("hidden", False),
            editable=entity.get("editable", False),
            max_value=entity.get("max", 3000),
            min_value=entity.get("min", 0),
            default=entity.get("default", 0),
            multiplier=entity.get("multiplier", 1),
            unique_id="{}_{}_{}".format(DOMAIN, controller.host, entity.get("unique", "reserve"))
        ), definition.get("entities", [])))
        _LOGGER.debug(f"Sensor group creation. start registrar = {self.start_register}, sensor count = {self.sensors_count}, registrar count = {self.registrar_count}")
        self.validate_sequential_registrars()

    def validate_sequential_registrars(self):
        """Ensure all registrars increase sequentially without skipping numbers."""
        all_registrars = sorted(set(reg for sensor in self._sensors for reg in sensor.registrars))

        for i in range(len(all_registrars) - 1):
            if all_registrars[i + 1] != all_registrars[i] + 1:
                _LOGGER.error(f"🚨 Registrar sequence error! Found gap between {all_registrars[i]} and {all_registrars[i + 1]} in sensor group.")

    @property
    def sensors_count(self):
        return len(self._sensors)

    @property
    def sensors(self):
        return self._sensors

    @property
    def registrar_count(self):
        return sum(len(sensor.registrars) for sensor in self._sensors)

    @property
    def start_register(self):
        return min(reg for sensor in self._sensors for reg in sensor.registrars)