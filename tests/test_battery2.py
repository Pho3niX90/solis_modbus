"""Second battery (BAT2) support on dual-battery hybrids such as the S6-EH3P50K-H.

Registers verified live on an S6-EH3P50K-H: SOC 34278 matches the app's battery-2
value, direction 34291 is 0 while charging and 1 while discharging, and power
34368/34369 is S32 (positive charging, negative discharging), like battery 1.
"""

from custom_components.solis_modbus.data.enums import DataType, InverterFeature
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, inverter_options_from_config
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors

BATTERY2_GROUP_STARTS = {34275, 34368, 34373}


def _battery2_groups():
    return [g for g in hybrid_sensors if g.get("register_start") in BATTERY2_GROUP_STARTS]


def _battery2_entities():
    return {e["unique"]: e for g in _battery2_groups() for e in g["entities"] if "unique" in e}


def test_battery2_groups_exist_and_are_gated():
    groups = _battery2_groups()
    assert len(groups) == 3
    for group in groups:
        assert group.get("feature_requirement") == [InverterFeature.BATTERY2]


def test_battery2_feature_from_config():
    template = next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH3P")

    default_opts = inverter_options_from_config({}, template)
    enabled_opts = inverter_options_from_config({"has_battery2": True}, template)

    assert InverterFeature.BATTERY2 not in template.clone_with_options(default_opts, "S2_WL_ST").features
    assert InverterFeature.BATTERY2 in template.clone_with_options(enabled_opts, "S2_WL_ST").features


def test_battery2_core_registers():
    ents = _battery2_entities()
    assert ents["solis_modbus_inverter_battery2_soc"]["register"] == ["34278"]
    assert ents["solis_modbus_inverter_battery2_voltage"]["register"] == ["34289"]
    assert ents["solis_modbus_inverter_battery2_current"]["register"] == ["34290"]
    assert ents["solis_modbus_inverter_battery2_current_direction"]["register"] == ["34291"]
    power = ents["solis_modbus_inverter_battery2_power"]
    assert power["register"] == ["34368", "34369"]
    # Two registers decode as S32 by default; discharging must come out negative.
    assert power.get("data_type") in (None, DataType.S32)


def test_battery2_unique_ids_do_not_clash_with_other_sensors():
    others = {e["unique"] for g in hybrid_sensors if g.get("register_start") not in BATTERY2_GROUP_STARTS for e in g["entities"] if "unique" in e}
    assert not others & set(_battery2_entities())


def _derived(hass, registrars):
    from unittest.mock import MagicMock

    from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.slave = 1
    controller.device_id = 1
    base = MagicMock()
    base.controller = controller
    base.name = "Test"
    base.unique_id = "test"
    base.registrars = registrars
    base.multiplier = 0
    base.device_class = None
    base.unit_of_measurement = None
    base.hidden = False
    base.state_class = "measurement"
    return SolisDerivedSensor(hass, base)


def _feed(sensor, values):
    from unittest.mock import patch

    from custom_components.solis_modbus.const import CONTROLLER, REGISTER, SLAVE, VALUE

    with patch.object(sensor, "schedule_update_ha_state"):
        for reg, val in values.items():
            sensor.handle_modbus_update({REGISTER: reg, VALUE: val, CONTROLLER: "1.2.3.4", SLAVE: 1})


def test_combined_soc_matches_app(hass):
    """The app showed 51 % with BAT1 at 60 % and BAT2 at 42 %."""
    sensor = _derived(hass, [33139, 34278])
    _feed(sensor, {33139: 60, 34278: 42})
    assert sensor.native_value == 51


def test_combined_power_sums_signed_values(hass):
    """Measured while discharging: BAT1 -2300 W (0xFFFF F704), BAT2 -2500 W (0xFFFF F63C)."""
    sensor = _derived(hass, [33149, 33150, 34368, 34369])
    _feed(sensor, {33149: 0xFFFF, 33150: 0xF704, 34368: 0xFFFF, 34369: 0xF63C})
    assert sensor.native_value == -4800


def test_combined_sensors_only_with_battery2():
    from custom_components.solis_modbus.helpers import derived_sensor_is_supported
    from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors_derived

    known = {int(r) for g in hybrid_sensors for e in g["entities"] for r in e.get("register", [])}
    without_b2 = {int(r) for g in hybrid_sensors if g.get("register_start") not in BATTERY2_GROUP_STARTS for e in g["entities"] for r in e.get("register", [])}
    combined = [e for e in hybrid_sensors_derived if "combined_soc" in e["unique"] or "combined_power" in e["unique"]]
    assert len(combined) == 2
    for entity in combined:
        assert not derived_sensor_is_supported(entity, without_b2, known)
        assert derived_sensor_is_supported(entity, known, known)
