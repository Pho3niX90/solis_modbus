"""A closed TCP port must be reported as such, not as a generic config error.

Issue #432: Solis datalogger firmware started closing the local TCP services while
cloud upload kept working. Users saw only "Failed to connect, please check your
settings", so they re-checked host/port/slave for days before someone probed port 502
from a plain PC and found it shut. The pre-probe separates "nothing is listening" from
"Modbus itself failed" so the error text can say which.
"""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.solis_modbus.config_flow import ModbusConfigFlow, _probe_tcp_port
from custom_components.solis_modbus.const import CONN_TYPE_TCP

TCP_INPUT = {
    "connection_type": CONN_TYPE_TCP,
    "host": "1.2.3.4",
    "port": 502,
    "slave": 1,
    "model": "S6-EH1P",
    "connection": "S2_WL_ST",
}


class _FakeWriter:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


@pytest.mark.asyncio
async def test_probe_returns_true_when_something_listens():
    writer = _FakeWriter()
    with patch("asyncio.open_connection", AsyncMock(return_value=(object(), writer))):
        reachable, reason = await _probe_tcp_port("1.2.3.4", 502)
    assert reachable is True
    assert reason is None
    assert writer.closed, "the probe socket must not be leaked"


@pytest.mark.asyncio
async def test_probe_reports_refused_connection():
    with patch("asyncio.open_connection", AsyncMock(side_effect=ConnectionRefusedError())):
        reachable, reason = await _probe_tcp_port("1.2.3.4", 502)
    assert reachable is False
    assert reason == "ConnectionRefusedError"


@pytest.mark.asyncio
async def test_probe_reports_timeout():
    with patch("asyncio.open_connection", AsyncMock(side_effect=TimeoutError())):
        reachable, reason = await _probe_tcp_port("1.2.3.4", 502)
    assert reachable is False
    assert reason == "timeout"


@pytest.mark.asyncio
async def test_validate_config_returns_tcp_port_closed_when_port_shut():
    """The reported case: pings fine, port 502 refuses."""
    flow = ModbusConfigFlow()
    with patch(
        "custom_components.solis_modbus.config_flow._probe_tcp_port",
        AsyncMock(return_value=(False, "ConnectionRefusedError")),
    ):
        ok, err = await flow._validate_config(dict(TCP_INPUT))
    assert ok is False
    assert err == "tcp_port_closed"


@pytest.mark.asyncio
async def test_validate_config_does_not_probe_modbus_when_port_is_shut():
    """No point spending three Modbus attempts on a port nothing is listening on."""
    flow = ModbusConfigFlow()
    with (
        patch(
            "custom_components.solis_modbus.config_flow._probe_tcp_port",
            AsyncMock(return_value=(False, "ConnectionRefusedError")),
        ),
        patch("custom_components.solis_modbus.config_flow.AsyncModbusTcpClient") as client_cls,
    ):
        await flow._validate_config(dict(TCP_INPUT))
    client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_open_port_but_bad_modbus_still_reports_cannot_connect():
    """A listening port that fails the register probe is a different problem."""
    flow = ModbusConfigFlow()

    client = AsyncMock()
    client.connected = True
    client.read_input_registers = AsyncMock(side_effect=ConnectionError("boom"))
    client.close = lambda: None

    with (
        patch("custom_components.solis_modbus.config_flow._probe_tcp_port", AsyncMock(return_value=(True, None))),
        patch("custom_components.solis_modbus.config_flow.AsyncModbusTcpClient", return_value=client),
        patch("asyncio.sleep", AsyncMock()),
    ):
        ok, err = await flow._validate_config(dict(TCP_INPUT))

    assert ok is False
    assert err == "cannot_connect"


@pytest.mark.asyncio
async def test_serial_connections_skip_the_tcp_probe():
    flow = ModbusConfigFlow()

    client = AsyncMock()
    client.connected = True
    result = AsyncMock()
    result.isError = lambda: False
    client.read_input_registers = AsyncMock(return_value=result)
    client.close = lambda: None

    with (
        patch("custom_components.solis_modbus.config_flow._probe_tcp_port", AsyncMock()) as probe,
        patch("custom_components.solis_modbus.config_flow.AsyncModbusSerialClient", return_value=client),
    ):
        ok, err = await flow._validate_config({"connection_type": "serial", "serial_port": "/dev/ttyUSB0", "model": "S6-EH1P", "slave": 1})

    probe.assert_not_called()
    assert ok is True
    assert err is None
