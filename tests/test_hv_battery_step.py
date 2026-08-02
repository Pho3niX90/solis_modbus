"""Regression tests for the HV-battery step adjustment.

v4.2.0 added amp-denominated sensors on registers 33206/33207, which sit inside
the HV-battery branch of ``dynamic_adjustments``. That branch narrowed the step
with ``min(self.step, 0.1)``, but ``get_step`` only derives a step for %, kW and
W -- amps arrive as ``None``. The result was a TypeError during setup that took
the entire config entry down on HV-battery inverters (#445, #446, #447).
"""

from unittest.mock import MagicMock

import pytest
from homeassistant.const import PERCENTAGE, UnitOfElectricCurrent, UnitOfPower

from custom_components.solis_modbus.data.enums import InverterType
from custom_components.solis_modbus.data.solis_config import (
    InverterConfig,
    InverterOptions,
)
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor


def _controller(hv_battery: bool):
    """A controller whose inverter may or may not have an HV battery."""
    controller = MagicMock()
    controller.inverter_config = InverterConfig(
        model="S6-EH3P",
        wattage=[10000],
        phases=3,
        type=InverterType.HYBRID,
        options=InverterOptions(hv_battery=hv_battery),
    )
    controller.inverter_config.wattage_chosen = 10000
    return controller


def _sensor(controller, register: str, unit, step=None):
    """Build a sensor the way SolisSensorGroup does.

    Note ``step=None``: the group passes ``entity.get("step", None)``, so a
    definition that declares no step overrides the constructor default rather
    than inheriting it. That is what makes this reachable at all.
    """
    return SolisBaseSensor(
        hass=MagicMock(),
        controller=controller,
        unique_id="test",
        name="Test",
        registrars=[int(register)],
        write_register=None,
        multiplier=1,
        unit_of_measurement=unit,
        step=step,
    )


class TestHvBatteryStep:
    @pytest.mark.parametrize("register", ["33206", "33207"])
    def test_amp_sensors_do_not_crash_setup(self, register):
        """The exact failure from #445/#446/#447."""
        sensor = _sensor(_controller(hv_battery=True), register, UnitOfElectricCurrent.AMPERE)

        assert sensor.step == 0.1, "an undeclared step must fall back, not raise"
        assert sensor.min_value == 0

    def test_a_declared_step_is_still_narrowed(self):
        """The branch exists to tighten the step; that must keep working."""
        sensor = _sensor(_controller(hv_battery=True), "33206", UnitOfElectricCurrent.AMPERE, step=1)

        assert sensor.step == 0.1

    def test_a_finer_declared_step_is_preserved(self):
        """min() means finer-than-0.1 wins; don't coarsen someone's sensor."""
        sensor = _sensor(
            _controller(hv_battery=True),
            "33206",
            UnitOfElectricCurrent.AMPERE,
            step=0.01,
        )

        assert sensor.step == 0.01

    def test_non_hv_inverters_are_untouched(self):
        """Without an HV battery the branch must not run at all."""
        sensor = _sensor(_controller(hv_battery=False), "33206", UnitOfElectricCurrent.AMPERE)

        assert sensor.step is None

    def test_unrelated_registers_are_untouched(self):
        """Only the listed registers are HV-sensitive."""
        sensor = _sensor(_controller(hv_battery=True), "33000", UnitOfElectricCurrent.AMPERE)

        assert sensor.step is None


class TestGetStep:
    @pytest.mark.parametrize(
        ("unit", "expected"),
        [
            (PERCENTAGE, 1),
            (UnitOfPower.KILO_WATT, 0.1),
            (UnitOfPower.WATT, 1),
            (UnitOfElectricCurrent.AMPERE, None),
        ],
    )
    def test_derived_steps(self, unit, expected):
        """Amps deriving to None is intended; callers must cope with it."""
        assert _sensor(_controller(hv_battery=False), "33000", unit).step == expected

    def test_a_declared_step_always_wins(self):
        sensor = _sensor(_controller(hv_battery=False), "33000", PERCENTAGE, step=5)

        assert sensor.step == 5
