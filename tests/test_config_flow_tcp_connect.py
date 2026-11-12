"""How the config flow's validation uses TCP connections.

Issue #432: Solis datalogger firmware started closing the local TCP services while
cloud upload kept working. Users saw only "Failed to connect, please check your
settings", so they re-checked host/port/slave for days before someone probed port 502
from a plain PC and found it shut. A failed connect therefore reports itself as such,
separately from "Modbus itself failed".

Issue #545: an S2-WL-ST allows few clients. Validation opened a throwaway socket before
the real one and left a socket open on every retry, so a failed attempt could lock the
logger out until it was rebooted. The tests with a real server count those sockets.
"""

import asyncio
import contextlib
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.client import AsyncModbusTcpClient

from custom_components.solis_modbus.config_flow import ModbusConfigFlow
from custom_components.solis_modbus.const import CONN_TYPE_TCP

HOST = "127.0.0.1"

TCP_INPUT = {
    "connection_type": CONN_TYPE_TCP,
    "host": "1.2.3.4",
    "port": 502,
    "slave": 1,
    "model": "S6-EH1P",
    "connection": "S2_WL_ST",
}


class _FakeLogger:
    """A TCP server that records how many sockets are open, now and at the peak."""

    def __init__(self, answer: bool):
        self.answer = answer
        self.accepted = 0
        self.open = 0
        self.peak = 0
        self.port = 0
        self._server = None
        self._writers = []

    async def _handle(self, reader, writer):
        self.accepted += 1
        self.open += 1
        self.peak = max(self.peak, self.open)
        self._writers.append(writer)
        try:
            while request := await reader.read(12):
                if self.answer:
                    count = int.from_bytes(request[10:12], "big")
                    writer.write(request[:4] + (3 + 2 * count).to_bytes(2, "big") + request[6:8] + bytes([2 * count]) + bytes(2 * count))
                    await writer.drain()
        except ConnectionError:
            pass
        finally:
            self.open -= 1
            writer.close()

    async def __aenter__(self):
        self._server = await asyncio.start_server(self._handle, HOST, 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc):
        self._server.close()
        for writer in self._writers:
            writer.close()
        with contextlib.suppress(Exception):
            await self._server.wait_closed()


def _short_timeout_client(host, port, timeout, retries):
    """The real client, without production's 5 s timeout and 1 retry."""
    return AsyncModbusTcpClient(host=host, port=port, timeout=0.2, retries=0)


async def _validate_against(logger: _FakeLogger):
    with patch("custom_components.solis_modbus.config_flow.AsyncModbusTcpClient", side_effect=_short_timeout_client):
        return await ModbusConfigFlow()._validate_config({**TCP_INPUT, "host": HOST, "port": logger.port})


@pytest.mark.asyncio
async def test_failed_validation_never_holds_more_than_one_socket(socket_enabled):
    """The reported case: the logger accepts connections but never answers."""
    async with _FakeLogger(answer=False) as logger:
        result = await _validate_against(logger)
        async with asyncio.timeout(5):
            while logger.open:
                await asyncio.sleep(0.01)

    assert result == (False, "cannot_connect")
    assert logger.accepted == 3, "one socket per attempt, and no separate probe socket"
    assert logger.peak == 1, "an attempt must close its socket before the next one opens"


@pytest.mark.asyncio
async def test_successful_validation_opens_one_socket(socket_enabled):
    async with _FakeLogger(answer=True) as logger:
        result = await _validate_against(logger)
        async with asyncio.timeout(5):
            while logger.open:
                await asyncio.sleep(0.01)

    assert result == (True, None)
    assert logger.accepted == 1


@pytest.mark.asyncio
async def test_closed_port_reports_tcp_port_closed(socket_enabled):
    """Pings fine, port 502 refuses. Nothing is listening on a port just released here."""
    with socket.socket() as unused:
        unused.bind((HOST, 0))
        port = unused.getsockname()[1]

    result = await ModbusConfigFlow()._validate_config({**TCP_INPUT, "host": HOST, "port": port})

    assert result == (False, "tcp_port_closed")


@pytest.mark.asyncio
async def test_failed_connect_is_not_retried():
    """No point spending three attempts on a port nothing is listening on."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.connected = False
    client.read_input_registers = AsyncMock()

    with patch("custom_components.solis_modbus.config_flow.AsyncModbusTcpClient", return_value=client):
        ok, err = await ModbusConfigFlow()._validate_config(dict(TCP_INPUT))

    assert (ok, err) == (False, "tcp_port_closed")
    client.connect.assert_awaited_once()
    client.read_input_registers.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_port_but_bad_modbus_still_reports_cannot_connect():
    """A listening port that fails the register probe is a different problem."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.connected = True
    client.read_input_registers = AsyncMock(side_effect=ConnectionError("boom"))

    with (
        patch("custom_components.solis_modbus.config_flow.AsyncModbusTcpClient", return_value=client),
        patch("asyncio.sleep", AsyncMock()),
    ):
        ok, err = await ModbusConfigFlow()._validate_config(dict(TCP_INPUT))

    assert (ok, err) == (False, "cannot_connect")
    assert client.close.call_count == 3


@pytest.mark.asyncio
async def test_refused_retry_after_an_accepted_connection_is_not_a_closed_port():
    """The port just accepted a connection, so calling it closed would mislead."""
    client = MagicMock()
    client.read_input_registers = AsyncMock(side_effect=ConnectionError("boom"))

    connects = []

    async def connect():
        connects.append(True)
        client.connected = len(connects) == 1

    client.connect = connect

    with (
        patch("custom_components.solis_modbus.config_flow.AsyncModbusTcpClient", return_value=client),
        patch("asyncio.sleep", AsyncMock()),
    ):
        ok, err = await ModbusConfigFlow()._validate_config(dict(TCP_INPUT))

    assert (ok, err) == (False, "cannot_connect")
    assert len(connects) == 3


@pytest.mark.asyncio
async def test_serial_connect_failure_retries_and_reports_cannot_connect():
    """tcp_port_closed names a TCP port; a serial port that won't open isn't one."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.connected = False

    with (
        patch("custom_components.solis_modbus.client_manager.AsyncModbusSerialClient", return_value=client),
        patch("asyncio.sleep", AsyncMock()),
    ):
        ok, err = await ModbusConfigFlow()._validate_config({"connection_type": "serial", "serial_port": "/dev/ttyUSB0", "model": "S6-EH1P", "slave": 1})

    assert (ok, err) == (False, "cannot_connect")
    assert client.connect.await_count == 3
    assert client.close.call_count == 3
