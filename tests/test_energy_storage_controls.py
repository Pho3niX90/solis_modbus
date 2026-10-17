"""Issue #514: battery-only (ENERGY) inverters such as the S6-EA1P get the same controls as hybrids."""

import pytest

from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, InverterOptions
from custom_components.solis_modbus.sensor_data.select_sensors import get_select_sensors
from custom_components.solis_modbus.sensor_data.switch_sensors import get_switch_sensors
from custom_components.solis_modbus.sensor_data.time_sensors import get_time_sensors


def _config(model):
    template = next(inv for inv in SOLIS_INVERTERS if inv.model == model)
    return template.clone_with_options(InverterOptions(pv=False), "S2_WL_ST")


def _registers(definitions):
    # Hybrid switch groups key on "register"; GRID/STRING ones on "read_register".
    return {d.get("register", d.get("read_register")) for d in definitions}


@pytest.mark.parametrize("model", ["S6-EA1P", "RAI-*"])
def test_energy_inverter_gets_hybrid_controls(model):
    energy = _config(model)
    hybrid = _config("S6-EH1P")

    assert _registers(get_select_sensors(energy)) == _registers(get_select_sensors(hybrid))
    assert _registers(get_switch_sensors(energy)) == _registers(get_switch_sensors(hybrid))
    assert _registers(get_time_sensors(energy)) == _registers(get_time_sensors(hybrid))


def test_energy_inverter_storage_mode_switches_present():
    switches = get_switch_sensors(_config("S6-EA1P"))
    assert 43110 in _registers(switches)


def test_grid_inverter_still_gets_no_storage_controls():
    grid = _config("S6-GR1P")
    assert get_select_sensors(grid) == []
    assert get_time_sensors(grid) == []
    assert 43110 not in _registers(get_switch_sensors(grid))
