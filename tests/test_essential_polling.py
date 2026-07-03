"""Issue #412: essential-only polling to reduce datalogger load.

When `essential_only` is enabled, only sensor groups flagged `"essential": True`
are polled. These tests pin down that the flagged subset stays small while still
covering the core power-flow registers users actually need (PV power, active
power, status, battery SOC/power, energy totals).
"""

import voluptuous as vol

from custom_components.solis_modbus.config_flow import BASE_CONFIG_SCHEMA, OPTIONS_SCHEMA, SOLIS_MODELS
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors
from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors


def _essential_registers(groups):
    registers = set()
    for group in groups:
        if not group.get("essential"):
            continue
        for entity in group.get("entities", []):
            registers.update(int(r) for r in entity.get("register", []))
    return registers


def test_hybrid_essential_covers_core_power_flow():
    regs = _essential_registers(hybrid_sensors)
    assert 33057 in regs  # Total PV / DC output power
    assert 33079 in regs  # Active power
    assert 33095 in regs  # Inverter status
    assert 33139 in regs  # Battery SOC
    assert 33149 in regs  # Battery power
    assert 33147 in regs  # Household load power
    assert 33169 in regs  # Total energy imported from grid


def test_hybrid_essential_is_a_small_subset():
    essential = [g for g in hybrid_sensors if g.get("essential")]
    assert 0 < len(essential) <= len(hybrid_sensors) // 3
    # No holding-register (setting) groups in the essential set
    assert all(g["register_start"] < 40000 for g in essential)


def test_string_essential_covers_core_power_flow():
    regs = _essential_registers(string_sensors)
    assert 3036 in regs or 3033 in regs  # AC phase data
    assert 36028 in regs  # Total load power
    assert 36050 in regs  # Total generation energy


def test_config_schemas_offer_essential_only():
    base_keys = {str(k.schema): k for k in BASE_CONFIG_SCHEMA}
    options_keys = {str(k.schema): k for k in OPTIONS_SCHEMA.schema}
    assert "essential_only" in base_keys
    assert "essential_only" in options_keys
    assert base_keys["essential_only"].default() is False

    validated = vol.Schema(BASE_CONFIG_SCHEMA)(
        {
            "connection_type": "tcp",
            "inverter_serial": "TEST123",
            "slave": 1,
            "model": next(iter(SOLIS_MODELS)),
        }
    )
    assert validated["essential_only"] is False
