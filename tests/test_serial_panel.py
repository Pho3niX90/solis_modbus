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
        "esphome-hass://aux-2/0",
    ],
)
def test_supported_serial_ports(port):
    """Device paths, pyserial's URL schemes and ESPHome serial proxies are accepted."""
    assert config_flow._is_supported_serial_port(port)


@pytest.mark.parametrize("port", ["esphome://192.168.1.60:6053", "tcp://192.168.1.50:502"])
def test_unsupported_serial_ports(port):
    """URLs neither pyserial nor the serial proxy client can open are rejected."""
    assert not config_flow._is_supported_serial_port(port)


async def test_validate_config_rejects_unsupported_port(hass):
    """An unsupported port gives a clear error instead of a failed connection."""
    flow = config_flow.ModbusConfigFlow()
    flow.hass = hass

    with patch.object(config_flow, "AsyncModbusSerialClient") as serial_client, patch.object(config_flow, "SerialProxyClient") as proxy_client:
        valid, err = await flow._validate_config(
            {
                "connection_type": "serial",
                CONF_SERIAL_PORT: "tcp://192.168.1.50:502",
                "slave": 1,
                "model": "S6-EH1P",
            }
        )

    assert (valid, err) == (False, "serial_port_unsupported")
    serial_client.assert_not_called()
    proxy_client.assert_not_called()


async def test_validate_config_probes_esphome_proxy_through_serialx(hass):
    """An ESPHome serial proxy (e.g. Connect AUX-2) is probed with SerialProxyClient, at the configured slave."""
    from unittest.mock import AsyncMock, MagicMock

    flow = config_flow.ModbusConfigFlow()
    flow.hass = hass

    probe = MagicMock()
    probe.isError.return_value = False
    client = MagicMock()
    client.connect = AsyncMock()
    client.connected = True
    client.read_input_registers = AsyncMock(return_value=probe)

    with (
        patch.object(config_flow, "AsyncModbusSerialClient") as serial_client,
        patch.object(config_flow, "SerialProxyClient", return_value=client) as proxy_client,
    ):
        valid, err = await flow._validate_config(
            {
                "connection_type": "serial",
                CONF_SERIAL_PORT: "esphome-hass://aux-2/0",
                "slave": 4,
                "model": "S6-EH1P",
            }
        )

    assert (valid, err) == (True, None)
    serial_client.assert_not_called()
    assert proxy_client.call_args.kwargs["port"] == "esphome-hass://aux-2/0"
    assert client.read_input_registers.await_args.kwargs["device_id"] == 4
