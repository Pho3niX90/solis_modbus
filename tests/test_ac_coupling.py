import pytest
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, InverterConfig, InverterOptions
from custom_components.solis_modbus.data.enums import InverterFeature, InverterType


def test_ac_coupling_feature_enabled():
    """Test that AC_COUPLING feature is added when option is enabled."""
    options = InverterOptions(ac_coupling=True)
    config = InverterConfig(model="S6-EH1P", wattage=[8000], phases=1, type=InverterType.HYBRID, options=options)

    assert InverterFeature.AC_COUPLING in config.features


def test_ac_coupling_feature_disabled_by_default():
    """Test that AC_COUPLING feature is NOT added by default."""
    config = InverterConfig(model="S6-EH1P", wattage=[8000], phases=1, type=InverterType.HYBRID)

    assert InverterFeature.AC_COUPLING not in config.features


def test_hybrid_sensors_ac_coupling_requirement():
    """Test that some hybrid sensors require AC_COUPLING feature."""
    from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors

    ac_coupling_groups = [group for group in hybrid_sensors if group.get("feature_requirement") and InverterFeature.AC_COUPLING in group["feature_requirement"]]

    assert len(ac_coupling_groups) > 0
    for group in ac_coupling_groups:
        assert InverterFeature.AC_COUPLING in group["feature_requirement"]
