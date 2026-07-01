from custom_components.solis_modbus.data.status_mapping import STATUS_MAPPING


def test_grid_voltage_fault_codes_match_soliscloud():
    """Issue #404: register 33095 reports fault codes whose hex form is the
    SolisCloud alarm code. 4112 = 0x1010 = OV-G-V, 4113 = 0x1011 = UV-G-V."""
    assert STATUS_MAPPING[0x1010] == "Grid overvoltage"
    assert STATUS_MAPPING[0x1011] == "Grid undervoltage"
    assert STATUS_MAPPING[0x1012] == "Grid overfrequency"
    assert STATUS_MAPPING[0x1013] == "Grid underfrequency"


def test_fault_blocks_are_hex_keyed():
    assert STATUS_MAPPING[0x1020] == "DC overvoltage"
    assert STATUS_MAPPING[0x1030] == "Grid disturbance"
    assert STATUS_MAPPING[0x1055] == "Battery no connected"
    assert STATUS_MAPPING[0x2010] == "Fail safe"
    assert STATUS_MAPPING[0xF010] == "Grid surge"


def test_no_mis_keyed_legacy_fault_codes():
    """The old table assigned grid faults to 4110/4111 and ran the blocks
    together (4122-4127, 4130-4157 carrying labels that belong at 4144+)."""
    assert 4110 not in STATUS_MAPPING
    assert STATUS_MAPPING.get(4131) != "DSP initialization malfunction protection"
    assert STATUS_MAPPING.get(4146) != "DSP key register exception"
