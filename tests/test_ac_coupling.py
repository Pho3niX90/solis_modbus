from custom_components.solis_modbus.data.enums import InverterFeature, InverterType
from custom_components.solis_modbus.data.solis_config import (
    SOLIS_INVERTERS,
    InverterConfig,
    InverterOptions,
    inverter_options_from_config,
)


def test_ac_coupling_feature_enabled():
    """Test that AC_COUPLING feature is added when option is enabled."""
    options = InverterOptions(ac_coupling=True)
    config = InverterConfig(model="S6-EH1P", wattage=[8000], phases=1, type=InverterType.HYBRID, options=options)

    assert InverterFeature.AC_COUPLING in config.features


def test_ac_coupling_feature_disabled_by_default():
    """Test that AC_COUPLING feature is NOT added by default."""
    config = InverterConfig(model="S6-EH1P", wattage=[8000], phases=1, type=InverterType.HYBRID)

    assert InverterFeature.AC_COUPLING not in config.features


def test_clone_applies_user_options_and_leaves_templates_untouched():
    """User options must rebuild features; SOLIS_INVERTERS entries must stay immutable."""
    template = next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH1P")
    feats_before = list(template.features)

    user = {
        "has_v2": True,
        "has_pv": True,
        "has_ac_coupling": True,
        "has_parallel": False,
        "has_battery": True,
        "has_hv_battery": False,
        "has_generator": True,
    }
    clone = template.clone_with_options(inverter_options_from_config(user, template), "S2_WL_ST")

    assert InverterFeature.AC_COUPLING in clone.features
    assert InverterFeature.GENERATOR in clone.features
    assert template.features == feats_before
    assert InverterFeature.AC_COUPLING not in template.features


def test_hybrid_sensors_ac_coupling_requirement():
    """Test that some hybrid sensors require AC_COUPLING feature."""
    from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors

    ac_coupling_groups = [group for group in hybrid_sensors if group.get("feature_requirement") and InverterFeature.AC_COUPLING in group["feature_requirement"]]

    assert len(ac_coupling_groups) > 0
    for group in ac_coupling_groups:
        assert InverterFeature.AC_COUPLING in group["feature_requirement"]


def test_parallel_feature_disabled_by_default():
    """PARALLEL is opt-in; default installs must not advertise it on the template."""
    config = InverterConfig(model="S5-EH1P", wattage=[5000], phases=1, type=InverterType.HYBRID)

    assert InverterFeature.PARALLEL not in config.features


def test_parallel_feature_when_option_enabled():
    options = InverterOptions(parallel=True)
    config = InverterConfig(model="S5-EH1P", wattage=[5000], phases=1, type=InverterType.HYBRID, options=options)

    assert InverterFeature.PARALLEL in config.features


def test_hybrid_sensors_parallel_sync_block_gated():
    """Parallel synchronization result (34243) must only load when PARALLEL is enabled."""
    from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors

    parallel_groups = [
        group for group in hybrid_sensors if group.get("register_start") == 34243 and group.get("feature_requirement")
    ]
    assert len(parallel_groups) == 1
    assert InverterFeature.PARALLEL in parallel_groups[0]["feature_requirement"]
