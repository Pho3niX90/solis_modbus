# solis_base.py
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential, UnitOfApparentPower, UnitOfPower, \
    UnitOfElectricCurrent
from homeassistant.core import HomeAssistant, DOMAIN
from typing_extensions import List, Optional

from custom_components.solis_modbus.helpers import cache_get, extract_serial_number

class SolisBaseSensor:
    """Base class for all Solis sensors."""

    def __init__(self,
                 hass: HomeAssistant,
                 controller_host: str,
                 unique_id: str,
                 name: str,
                 registrars: List[int],
                 multiplier: float,
                 device_class: SwitchDeviceClass | SensorDeviceClass | PERCENTAGE = None,
                 unit_of_measurement: UnitOfElectricPotential | UnitOfApparentPower | UnitOfElectricCurrent | UnitOfPower = None,
                 editable: bool = False,
                 state_class: SensorStateClass = None,
                 default = None,
                 step = 0.1,
                 enabled = True,
                 min_value: Optional[int] = None, max_value: Optional[int] = None):
        """
        :param name: Sensor name
        :param registrars: First register address
        """
        self.hass = hass
        self.unique_id = unique_id
        self.controller_host = controller_host
        self.name = name
        self.default = default
        self.registrars = registrars
        self.editable = editable
        self.multiplier = multiplier
        self.device_class = device_class
        self.unit_of_measurement = unit_of_measurement
        self.state_class = state_class
        self.max_value = max_value
        self.step = step
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

    def __init__(self, hass, definition, controller_host: str):
        self._sensors = list(map(lambda entity: SolisBaseSensor(
            hass=hass,
            name= entity.get("name", "reserve"),
            controller_host=controller_host,
            registrars=[int(r) for r in entity["register"]],
            multiplier=entity.get("multiplier", 1),
            unique_id="{}_{}_{}".format(DOMAIN, controller_host, entity.get("unique", "reserve"))
        ), definition.get("entities", [])))
        # TODO add derived sensors
        # TODO add number sensors
        # TODO add time sensors

    @property
    def sensors_count(self):
        return self._sensors.count()

    @property
    def sensors(self):
        return self._sensors

    @property
    def start_register(self):
        return min(sensor.registrars for sensor in self._sensors)