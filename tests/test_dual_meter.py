"""Dual-meter (Meter 2) support — issue #425.

The 33300/33316 register groups only poll when the user enables the
"has_dual_meter" option (Grid + PV Inverter dual-meter installs).
"""

from custom_components.solis_modbus.data.enums import InverterFeature
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, inverter_options_from_config
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors

METER2_GROUP_STARTS = {33300, 33316}


def _meter2_groups():
    return [g for g in hybrid_sensors if g.get("register_start") in METER2_GROUP_STARTS]


def test_meter2_groups_exist_and_are_gated():
    groups = _meter2_groups()
    assert len(groups) == 2
    for group in groups:
        assert group.get("feature_requirement") == [InverterFeature.DUAL_METER]


def test_meter2_registers_match_2020_protocol():
    """33300-33337 per ESINV-33000ID 2020-09-15 pp.20-21 (contiguity is enforced
    by test_sensor_definition_integrity; here we pin the exact span)."""
    regs = []
    for group in _meter2_groups():
        for entity in group["entities"]:
            regs.extend(int(r) for r in entity.get("register", []))
    assert min(regs) == 33300
    assert max(regs) == 33337


def test_dual_meter_feature_from_config():
    template = next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH1P")

    default_opts = inverter_options_from_config({}, template)
    enabled_opts = inverter_options_from_config({"has_dual_meter": True}, template)

    assert InverterFeature.DUAL_METER not in template.clone_with_options(default_opts, "S2_WL_ST").features
    assert InverterFeature.DUAL_METER in template.clone_with_options(enabled_opts, "S2_WL_ST").features


def test_meter2_energy_counters_are_unsigned():
    for group in _meter2_groups():
        for entity in group["entities"]:
            if "energy" in entity.get("unique", ""):
                assert entity.get("data_type") is not None, entity["unique"]
