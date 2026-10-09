"""Home Assistant's Serial panel and serial port picker.

The panel (Settings > Connectivity > Serial) attributes a port to a config entry
only when the integration lists `usb` in its (after_)dependencies and stores the
port under a key it scans, `serial_port` among them.
"""

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import voluptuous as vol

from custom_components.solis_modbus import config_flow
from custom_components.solis_modbus.const import CONF_SERIAL_PORT

MANIFEST = Path(__file__).parent.parent / "custom_components" / "solis_modbus" / "manifest.json"


def _serial_port_marker(schema: dict):
    """Return the schema key for the serial port field."""
    return next(key for key in schema if getattr(key, "schema", None) == CONF_SERIAL_PORT)


def test_manifest_declares_usb_after_dependency():
    """The Serial panel only attributes ports to integrations that declare usb."""
    manifest = json.loads(MANIFEST.read_text())
    assert "usb" in manifest.get("after_dependencies", [])
    # A hard dependency would force `usb` to load where it can't.
    assert "usb" not in manifest.get("dependencies", [])


def test_serial_port_key_is_one_the_panel_scans():
    """The port is stored under a key the Serial panel reads."""
    # homeassistant/components/usb/consumers.py SERIAL_PORT_KEY_PATHS
    assert CONF_SERIAL_PORT == "serial_port"


def test_serial_port_field_without_selector_is_text_with_default():
    """Before HA 2026.5 the port stays a text field defaulting to /dev/ttyUSB0."""
    if hasattr(importlib.import_module("homeassistant.helpers.selector"), "SerialPortSelector"):
        pytest.skip("Home Assistant under test has SerialPortSelector")

    marker = _serial_port_marker(config_flow.SERIAL_CONFIG_SCHEMA)
    assert config_flow.SERIAL_CONFIG_SCHEMA[marker] is str
    assert marker.default() == "/dev/ttyUSB0"


def test_serial_port_field_uses_selector_when_available(monkeypatch):
    """From HA 2026.5 the port is picked from the ports HA can see."""

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


@pytest.mark.parametrize(
    "port",
    [
        "/dev/ttyUSB0",
        "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0",
        "COM3",
        "socket://192.168.1.50:8899",
        "rfc2217://192.168.1.50:4000",
        "RFC2217://192.168.1.50:4000",
    ],
)
def test_supported_serial_ports(port):
    """Device paths and the URL schemes pyserial handles are accepted."""
    assert config_flow._is_supported_serial_port(port)


@pytest.mark.parametrize("port", ["esphome-hass://living-room-proxy/0", "esphome://192.168.1.60:6053", "tcp://192.168.1.50:502"])
def test_unsupported_serial_ports(port):
    """URLs pyserial cannot open, such as ESPHome serial proxies, are rejected."""
    assert not config_flow._is_supported_serial_port(port)


async def test_validate_config_rejects_esphome_serial_proxy(hass):
    """Picking an ESPHome serial proxy gives a clear error instead of a failed connection."""
    flow = config_flow.ModbusConfigFlow()
    flow.hass = hass

    with patch.object(config_flow, "AsyncModbusSerialClient") as serial_client:
        valid, err = await flow._validate_config(
            {
                "connection_type": "serial",
                CONF_SERIAL_PORT: "esphome-hass://living-room-proxy/0",
                "slave": 1,
                "model": "S6-EH1P",
            }
        )

    assert (valid, err) == (False, "serial_port_unsupported")
    serial_client.assert_not_called()
