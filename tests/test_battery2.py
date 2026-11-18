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
