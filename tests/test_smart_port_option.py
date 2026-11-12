"""The Smart Port can be switched off in the options, and the parallel block is gated."""

from custom_components.solis_modbus.data.enums import InverterFeature
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, inverter_options_from_config
from custom_components.solis_modbus.helpers import group_in_poll_profile
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors


def _s6():
    return next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH3P")


def _features(config):
    template = _s6()
    return template.clone_with_options(inverter_options_from_config(config, template), "S2_WL_ST").features


def _groups(start):
    return [g for g in hybrid_sensors if g.get("register_start") == start]


def test_smart_port_defaults_on_for_s6():
    """Existing entries have no has_smart_port key; their behaviour must not change on upgrade."""
    assert InverterFeature.SMART_PORT in _features({})


def test_smart_port_can_be_switched_off():
    assert InverterFeature.SMART_PORT not in _features({"has_smart_port": False})


def test_switching_smart_port_off_leaves_other_features():
    on, off = _features({}), _features({"has_smart_port": False})
    assert set(on) - set(off) == {InverterFeature.SMART_PORT}


def test_template_is_not_mutated():
    template = _s6()
    before = list(template.features)
    _features({"has_smart_port": False})
    assert template.features == before
    assert InverterFeature.SMART_PORT in template.features


def test_smart_port_groups_are_skipped_without_the_feature():
    """Every Smart Port group is gated, so the option removes them all from polling."""
    gated = [g for g in hybrid_sensors if InverterFeature.SMART_PORT in (g.get("feature_requirement") or [])]
    assert gated
    features = set(_features({"has_smart_port": False}))
    for group in gated:
        assert not set(group["feature_requirement"]) <= features


def _polled(group, config):
    """Same rule as setup: a group is polled when any of its required features is present."""
    requirement = group.get("feature_requirement") or []
    return not requirement or any(f in _features(config) for f in requirement)


def test_parallel_registers_are_gated():
    (parallel,) = _groups(33243)
    assert parallel.get("feature_requirement") == [InverterFeature.PARALLEL, InverterFeature.PARALLEL_READINGS]
    registers = {r for e in parallel["entities"] for r in e["register"]}
    assert registers == {"33243", "33244", "33245", "33246"}


def test_epm_status_is_still_polled_without_parallel():
    (epm,) = _groups(33247)
    assert not epm.get("feature_requirement")
    registers = {r for e in epm["entities"] for r in e["register"]}
    assert registers == {"33247", "33248", "33249", "33250"}
    uniques = {e["unique"] for e in epm["entities"]}
    assert "solis_modbus_inverter_epm_setpoint_power" in uniques
    assert "solis_modbus_inverter_meter_placement_status_bits" in uniques


def test_split_keeps_every_entity_once():
    """The split must not add, drop or duplicate entities."""
    uniques = [e["unique"] for g in _groups(33243) + _groups(33247) for e in g["entities"]]
    assert len(uniques) == len(set(uniques)) == 8


def test_poll_profiles_treat_the_new_group_like_the_old_one():
    """The EPM group inherits the old group's NORMAL speed and has no profile flags."""
    (epm,) = _groups(33247)
    (parallel,) = _groups(33243)
    for key in ("poll_speed", "essential", "extreme"):
        assert epm.get(key) == parallel.get(key)
    assert group_in_poll_profile(epm, "full", False, False)


def test_new_single_inverter_entry_skips_parallel_readings():
    (parallel,) = _groups(33243)
    assert not _polled(parallel, {})


def test_parallel_option_polls_parallel_readings():
    (parallel,) = _groups(33243)
    assert _polled(parallel, {"has_parallel": True})


def test_migrated_entry_keeps_parallel_readings_without_the_parallel_option():
    """Existing parallel installs may never have ticked has_parallel (#562)."""
    (parallel,) = _groups(33243)
    config = {"has_parallel": False, "parallel_readings": True}
    assert _polled(parallel, config)
    assert InverterFeature.PARALLEL not in _features(config)


def test_parallel_readings_do_not_enable_the_other_parallel_group():
    """Only the readings carry over; 34243 still needs the parallel option."""
    (sync,) = _groups(34243)
    assert not _polled(sync, {"parallel_readings": True})


def test_epm_status_is_polled_either_way():
    (epm,) = _groups(33247)
    assert _polled(epm, {}) and _polled(epm, {"parallel_readings": True})
