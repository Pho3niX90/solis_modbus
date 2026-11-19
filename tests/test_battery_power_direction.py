"""Battery Power Net / Charge Power / Discharge Power take their sign from 33135 only.

Some firmware reports battery power 33149/50 as an unsigned magnitude (S6-EA1P, see
fixtures/s6_ea1p6k_l.json). Others report it signed, positive charging and negative
discharging (S6-EH3P50K-H: 0xFFFF F704 = -2300 W while discharging, 33135 = 1). The
derived sensors must give the same result for both, so they use the magnitude.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.solis_modbus.const import CONTROLLER, DOMAIN, REGISTER, SLAVE, VALUE, VALUES
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, InverterOptions
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors_derived
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

NAMES = ("Battery Power Net", "Battery Charge Power", "Battery Discharge Power")


def _sensor(hass, name):
    hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
    template = next(config for config in SOLIS_INVERTERS if config.model == "S6-EH3P")
    controller = SimpleNamespace(
        inverter_config=template.clone_with_options(InverterOptions(), "S2_WL_ST"),
        device_serial_number="TEST",
        identification=None,
        host="test.invalid",
        connection_id="test",
        device_id=1,
        poll_speed={PollSpeed.FAST: 10, PollSpeed.NORMAL: 15, PollSpeed.SLOW: 30},
    )
    definition = next(d for d in hybrid_sensors_derived if d["name"] == name)
    base = SolisBaseSensor(
        hass=hass,
        controller=controller,
        unique_id=f"test_{name}",
        name=name,
        registrars=[int(reg) for reg in definition["register"]],
        write_register=None,
        multiplier=definition.get("multiplier", 1),
        unit_of_measurement=definition.get("unit_of_measurement"),
        device_class=definition.get("device_class"),
    )
    sensor = SolisDerivedSensor(hass, base)
    sensor.hass = hass
    return sensor


def _values(hass, words):
    result = {}
    for name in NAMES:
        sensor = _sensor(hass, name)
        with patch.object(sensor, "schedule_update_ha_state"):
            for reg, word in words.items():
                sensor.handle_modbus_update({REGISTER: reg, VALUE: word, CONTROLLER: "test.invalid", SLAVE: 1})
        result[name] = sensor.native_value
    return result


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        # Signed firmware, discharging 2300 W.
        ({33149: 0xFFFF, 33150: 0xF704, 33135: 1}, (2300, 0, 2300)),
        # Signed firmware, charging 1500 W.
        ({33149: 0, 33150: 1500, 33135: 0}, (-1500, 1500, 0)),
        # Magnitude firmware, discharging 1367 W (S6-EA1P capture).
        ({33149: 0, 33150: 1367, 33135: 1}, (1367, 0, 1367)),
        # Magnitude firmware, charging 800 W.
        ({33149: 0, 33150: 800, 33135: 0}, (-800, 800, 0)),
    ],
    ids=["signed-discharging", "signed-charging", "magnitude-discharging", "magnitude-charging"],
)
def test_battery_power_sign_follows_direction_register(hass, words, expected):
    assert _values(hass, words) == dict(zip(NAMES, expected, strict=True))
