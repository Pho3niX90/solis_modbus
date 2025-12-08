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
from custom_components.solis_modbus.data.enums import PollSpeed, Category, InverterFeature
from custom_components.solis_modbus.helpers import cache_get, extract_serial_number, split_s32, _any_in

_LOGGER = logging.getLogger(__name__)


class SolisBaseSensor:
    """Base class for all Solis sensors."""

    def __init__(self,
                 hass: HomeAssistant,
                 controller,
                 unique_id: str,
                 name: str,
                 registrars: List[int],
                 write_register: int,
                 multiplier: float,
                 device_class: Union[SwitchDeviceClass, SensorDeviceClass, str] = None,
                 unit_of_measurement: UnitOfElectricPotential | UnitOfApparentPower | UnitOfElectricCurrent | UnitOfPower = None,
                 editable: bool = False,
                 state_class: SensorStateClass = None,
                 default=None,
                 step=0.1,
                 hidden=False,
                 enabled=True,
                 category: Category = None,
                 min_value: Optional[int] = None,
                 max_value: Optional[int] = None,
                 poll_speed=PollSpeed.NORMAL):
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
        self.write_register = write_register
        _LOGGER.debug(f" self.registrars = {self.registrars} | self.write_register = {self.write_register}")
        self.editable = editable
        self.multiplier = multiplier
        self.device_class = device_class
        self.unit_of_measurement = unit_of_measurement
        self.hidden = hidden
        self.state_class = state_class
        self.max_value = max_value
        self.adjust_max(max_value)
        self.step = self.get_step(step)
        self.enabled = enabled
        self.min_value = min_value
        self.poll_speed = poll_speed
        self.category = category

        self.dynamic_adjustments()

    def dynamic_adjustments(self):
        inv_model = self.controller.inverter_config.model
        inv_features = self.controller.inverter_config.features

        # HV battery-specific adjustments
        if InverterFeature.HV_BATTERY in inv_features:
            hv_battery_sensitive_regs = {33205, 33206, 33207, 43013, 43117}
            if _any_in(self.registrars, hv_battery_sensitive_regs):
                self.min_value = 0
                self.step = min(self.step, 0.1)

        # RHI/RAI models: 1 <--> 1W (range: 0–30000)
        if inv_model in {"RHI-1P", "RHI-3P", "RAI-3K-48ES-5G"} and 43074 in self.registrars:
            self.multiplier = 1

        # S6-EH3P10K-H-ZP or ZONNEPLAN feature: apply 0.01 multiplier
        elif inv_model == "S6-EH3P10K-H-ZP" or InverterFeature.ZONNEPLAN in inv_features:
            s6_registers = {33142, 33161, 33162, 33163, 33164, 33165, 33166, 33167, 33168}
            if _any_in(self.registrars, s6_registers):
                self.multiplier = 0.01

    def adjust_max(self, max_default):
        try:
            new_max = max_default
            if self.unit_of_measurement == UnitOfElectricCurrent.AMPERE:
                new_max = round(
                    (self.controller.inverter_config.wattage_chosen / 44) / 5) * 5
            elif self.unit_of_measurement == UnitOfPower.WATT:
                new_max = self.controller.inverter_config.wattage_chosen
            elif self.unit_of_measurement == UnitOfPower.KILO_WATT:
                new_max = self.controller.inverter_config.wattage_chosen / 1000
            _LOGGER.debug(
                f"max value for {self.registrars} with UOM {self.unit_of_measurement} set to {new_max} instead of {max_default}")
            self.max_value = new_max
        except Exception as e:
            _LOGGER.error("❌ Dynamic UOM set failed, wanted = %s : %s",
                          self.controller.inverter_config.wattage_chosen, e)

    def get_step(self, wanted_step):
        if wanted_step is not None:
            return wanted_step
        if self.unit_of_measurement == PERCENTAGE:
            return 1
        if self.unit_of_measurement == UnitOfPower.KILO_WATT:
            return 0.1
        if self.unit_of_measurement == UnitOfPower.WATT:
            return 1

    @property
    def get_raw_values(self):
        return [cache_get(self.hass, reg) for reg in self.registrars]

    @property
    def get_value(self):
        return self._convert_raw_value(self.get_raw_values)

    def convert_value(self, value: List[int]):
        return self._convert_raw_value(value)

    def _convert_raw_value(self, values: List[int]):
        if None in values:
            return None

        if len(self.registrars) >= 15:
            values = values
            n_value = extract_serial_number(values)
        elif len(self.registrars) > 1:
            combined_value = split_s32(values)

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
        self._sensors = list(map(lambda entity: SolisBaseSensor(
            hass=hass,
            name=entity.get("name", "reserve"),
            controller=controller,
            registrars=[int(r) for r in entity["register"]],
            write_register=entity.get("write_register", None),
            state_class=entity.get("state_class", None),
            device_class=entity.get("device_class", None),
            unit_of_measurement=entity.get("unit_of_measurement", None),
            hidden=entity.get("hidden", False),
            editable=entity.get("editable", False),
            max_value=entity.get("max", 3000),
            min_value=entity.get("min", 0),
            step=entity.get("step", None),
            category=entity.get("category", None),
            default=entity.get("default", 0),
            multiplier=entity.get("multiplier", 1),
            unique_id="{}_{}_{}".format(DOMAIN, controller.device_serial_number, entity.get("unique", "reserve")),
            poll_speed=definition.get("poll_speed", PollSpeed.NORMAL)
        ), definition.get("entities", [])))
        self.poll_speed: PollSpeed = definition.get("poll_speed",
                                                    PollSpeed.NORMAL if self.start_register < 40000 else PollSpeed.SLOW)

        _LOGGER.debug(
            f"Sensor group creation. start registrar = {self.start_register}, sensor count = {self.sensors_count}, registrar count = {self.registrar_count}")
        self.validate_sequential_registrars()

    def validate_sequential_registrars(self):
        """Ensure all registrars increase sequentially without skipping numbers."""
        all_registrars = sorted(set(reg for sensor in self._sensors for reg in sensor.registrars))

        for i in range(len(all_registrars) - 1):
            if all_registrars[i + 1] != all_registrars[i] + 1:
                _LOGGER.error(
                    f"🚨 Registrar sequence error! Found gap between {all_registrars[i]} and {all_registrars[i + 1]} in sensor group.")

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
