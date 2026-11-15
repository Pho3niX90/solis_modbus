"""Multi-MPPT string inverters (80-110K-5G class): 20 string currents, 10 MPPTs.

Register layout (protocol doc → wire = doc - 1), field-verified on a Solis-100K-5G:
  3287        string voltage/current combination
  3299 / 3300 total PV voltage / current (= sum of the 20 string currents)
  3301-3320   PV string current 1-20
  3500-3509   MPPT voltage 1-10
  3530-3539   MPPT current 1-10 (= sum of the MPPT's 2 strings)
"""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.solis_modbus.const import CONTROLLER, REGISTER, SLAVE, VALUE
from custom_components.solis_modbus.data.enums import InverterFeature, InverterType
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, InverterOptions
from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors, string_sensors_derived
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

MULTI_MPPT_MODEL = "3P(80-110)K-5G"


def _template(model):
    return next(inv for inv in SOLIS_INVERTERS if inv.model == model)


def _multi_mppt_groups():
    return [g for g in string_sensors if InverterFeature.MULTI_MPPT in g.get("feature_requirement", [])]


def _entity_by_unique(unique):
    for group in string_sensors:
        for entity in group.get("entities", []):
            if entity.get("unique") == unique:
                return entity
    raise AssertionError(unique)


def test_multi_mppt_model_is_a_grid_inverter_with_the_feature():
    template = _template(MULTI_MPPT_MODEL)
    assert template.type == InverterType.GRID
    assert InverterFeature.MULTI_MPPT in template.features
    # User options must not drop an intrinsic feature.
    cfg = template.clone_with_options(InverterOptions(), "S2_WL_ST")
    assert InverterFeature.MULTI_MPPT in cfg.features


@pytest.mark.parametrize("model", ["S5-GC", "S5-GR3P", "S6-GR1P", "3P(3-20)K-4G", "1P(2.5-6)K-4G"])
def test_other_string_models_do_not_get_multi_mppt(model):
    assert InverterFeature.MULTI_MPPT not in _template(model).features


def test_multi_mppt_groups():
    starts = sorted(g["register_start"] for g in _multi_mppt_groups())
    assert starts == [3286, 3499]


@pytest.mark.parametrize("j", range(1, 11))
def test_mppt_voltage_and_current_are_read_in_the_same_block(j):
    """MPPT Power must never pair values from two different reads (PR #571 review)."""
    group = next(g for g in _multi_mppt_groups() if g["register_start"] == 3499)
    registers = {r for e in group["entities"] for r in e["register"]}
    assert {str(3498 + j), str(3528 + j)} <= registers


@pytest.mark.parametrize("k", range(1, 21))
def test_string_current_registers(k):
    entity = _entity_by_unique(f"solis_modbus_pv_string_current_{k}")
    assert entity["register"] == [str(3299 + k)]
    assert entity["multiplier"] == 0.1


@pytest.mark.parametrize("j", range(1, 11))
def test_mppt_registers(j):
    assert _entity_by_unique(f"solis_modbus_mppt_voltage_{j}")["register"] == [str(3498 + j)]
    assert _entity_by_unique(f"solis_modbus_mppt_current_{j}")["register"] == [str(3528 + j)]


def test_totals_registers():
    assert _entity_by_unique("solis_modbus_total_pv_voltage")["register"] == ["3298"]
    assert _entity_by_unique("solis_modbus_total_pv_current")["register"] == ["3299"]


def test_mppt_power_derived_sources_are_polled_only_by_multi_mppt_groups():
    polled = {int(r) for g in _multi_mppt_groups() for e in g["entities"] for r in e["register"]}
    mppt_power = [e for e in string_sensors_derived if e["unique"].startswith("solis_modbus_mppt_power_")]
    assert len(mppt_power) == 10
    for entity in mppt_power:
        assert {int(r) for r in entity["register"]} <= polled


@pytest.fixture
def mppt_base_sensor():
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.slave = 1
    controller.device_id = 1
    sensor = MagicMock()
    sensor.controller = controller
    sensor.name = "MPPT Power 1"
    sensor.unique_id = "test_mppt_power_1"
    sensor.registrars = [3499, 3529]
    sensor.multiplier = 0.1
    sensor.device_class = None
    sensor.unit_of_measurement = None
    sensor.hidden = False
    sensor.state_class = "measurement"
    return sensor


@pytest.mark.parametrize(
    ("current_raw", "expected"),
    [
        (67, 2295),  # 342.6 V x 6.7 A (100K-5G MPPT 1, 14 Nov)
        (0, 0),
        (0xFFFF, -34),  # -0.1 A, signed
    ],
)
def test_mppt_power(hass, mppt_base_sensor, current_raw, expected):
    sensor = SolisDerivedSensor(hass, mppt_base_sensor)
    with patch.object(sensor, "schedule_update_ha_state"):
        _send(sensor, 3499, 3426)
        _send(sensor, 3529, current_raw)
    assert sensor.native_value == expected


def _send(sensor, register, value):
    sensor.handle_modbus_update({REGISTER: register, VALUE: value, CONTROLLER: "1.2.3.4", SLAVE: 1})


def test_mppt_power_ignores_a_current_left_over_from_a_read_without_voltage(hass, mppt_base_sensor):
    """PR #571 review: 600 V with a stale 10 A must not give 6000 W when the fresh current is 20 A."""
    sensor = SolisDerivedSensor(hass, mppt_base_sensor)
    with patch.object(sensor, "schedule_update_ha_state") as update:
        _send(sensor, 3529, 100)  # poll N: current only (voltage missing)
        assert update.call_count == 0
        _send(sensor, 3499, 6000)  # poll N+1: 600.0 V ...
        assert update.call_count == 0  # ... not multiplied by the stale 10 A
        _send(sensor, 3529, 200)  # ... then 20.0 A
    assert update.call_count == 1
    assert sensor.native_value == 12000


def test_mppt_power_ignores_a_voltage_left_over_from_a_read_without_current(hass, mppt_base_sensor):
    sensor = SolisDerivedSensor(hass, mppt_base_sensor)
    with patch.object(sensor, "schedule_update_ha_state") as update:
        _send(sensor, 3499, 5000)  # poll N: 500.0 V, current missing
        _send(sensor, 3499, 6000)  # poll N+1: 600.0 V
        _send(sensor, 3529, 200)  # 20.0 A
    assert update.call_count == 1
    assert sensor.native_value == 12000


def test_mppt_power_stays_in_step_after_a_missed_read(hass, mppt_base_sensor):
    """After one current-only read, later polls must pair their own voltage and current again."""
    sensor = SolisDerivedSensor(hass, mppt_base_sensor)
    with patch.object(sensor, "schedule_update_ha_state"):
        _send(sensor, 3529, 100)
        for voltage, current, expected in [(6000, 200, 12000), (6100, 300, 18300), (5900, 50, 2950)]:
            _send(sensor, 3499, voltage)
            _send(sensor, 3529, current)
            assert sensor.native_value == expected
