"""Home Assistant's Serial panel and serial port picker.

The panel (Settings > Connectivity > Serial) attributes a port to a config entry
only when the integration lists `usb` in its (after_)dependencies and stores the
port under a key it scans, `serial_port` among them.
"""

import importlib
import json
import sys
from pathlib import Path

import pytest
import voluptuous as vol

from custom_components.solis_modbus import config_flow
from custom_components.solis_modbus.const import CONF_SERIAL_PORT

MANIFEST = Path(__file__).parent.parent / "custom_components" / "solis_modbus" / "manifest.json"


def _serial_port_marker(schema: dict):
    return next(key for key in schema if getattr(key, "schema", None) == CONF_SERIAL_PORT)


def test_manifest_declares_usb_after_dependency():
    manifest = json.loads(MANIFEST.read_text())
    assert "usb" in manifest.get("after_dependencies", [])
    # A hard dependency would force `usb` to load where it can't.
    assert "usb" not in manifest.get("dependencies", [])


def test_serial_port_key_is_one_the_panel_scans():
    # homeassistant/components/usb/consumers.py SERIAL_PORT_KEY_PATHS
    assert CONF_SERIAL_PORT == "serial_port"


def test_serial_port_field_without_selector_is_text_with_default():
    if hasattr(importlib.import_module("homeassistant.helpers.selector"), "SerialPortSelector"):
        pytest.skip("Home Assistant under test has SerialPortSelector")

    marker = _serial_port_marker(config_flow.SERIAL_CONFIG_SCHEMA)
    assert config_flow.SERIAL_CONFIG_SCHEMA[marker] is str
    assert marker.default() == "/dev/ttyUSB0"


def test_serial_port_field_uses_selector_when_available(monkeypatch):
    class FakeSerialPortSelector:
        def __call__(self, value):
            return str(value)

    selector = importlib.import_module("homeassistant.helpers.selector")
    monkeypatch.setattr(selector, "SerialPortSelector", FakeSerialPortSelector, raising=False)
    try:
        flow = importlib.reload(config_flow)
        marker = _serial_port_marker(flow.SERIAL_CONFIG_SCHEMA)
        assert isinstance(flow.SERIAL_CONFIG_SCHEMA[marker], FakeSerialPortSelector)
        # No preselected port; the picker lists what HA can see.
        assert marker.default is vol.UNDEFINED
    finally:
        monkeypatch.undo()
        importlib.reload(sys.modules[config_flow.__name__])
