"""SerialProxyClient: ESPHome serial proxies (e.g. Connect AUX-2) through modbus-connection."""

import pytest
from modbus_connection import IllegalDataAddressError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection

from custom_components.solis_modbus import serial_proxy
from custom_components.solis_modbus.client_manager import ModbusClientManager
from custom_components.solis_modbus.serial_proxy import SerialProxyClient, is_serial_proxy

PROXY_PORT = "esphome-hass://aux-2/0"


@pytest.fixture
def connection(monkeypatch):
    """Back SerialProxyClient with modbus-connection's in-memory connection."""
    mock = MockModbusConnection()
    created = []

    def fake_connection(params, *, timeout=None):
        created.append((params, timeout))
        return mock

    monkeypatch.setattr(serial_proxy, "ModbusConnection", fake_connection)
    mock.created = created
    return mock


@pytest.mark.parametrize(
    ("port", "expected"),
    [
        ("esphome-hass://aux-2/0", True),
        ("ESPHOME-HASS://aux-2/1", True),
        ("/dev/ttyUSB0", False),
        ("socket://192.168.1.50:8899", False),
        ("esphome://192.168.1.60:6053", False),
    ],
)
def test_is_serial_proxy(port, expected):
    """Only schemes Home Assistant registers with serialx take the proxy path."""
    assert is_serial_proxy(port) is expected


def test_builds_serial_params_from_line_settings(connection):
    """The line settings and timeout reach modbus-connection unchanged."""
    SerialProxyClient(PROXY_PORT, baudrate=19200, bytesize=8, parity="E", stopbits=1, timeout=5, retries=1)

    params, timeout = connection.created[0]
    assert (params.device, params.baudrate, params.bytesize, params.parity, params.stopbits) == (PROXY_PORT, 19200, 8, "E", 1)
    assert timeout == 5


async def test_reads_go_to_the_requested_unit(connection):
    """device_id picks the unit; without it the client's slave is used, like the controller sets it."""
    connection.for_unit(3).input[33000] = 1234
    connection.for_unit(1).holding[43000] = 7
    client = SerialProxyClient(PROXY_PORT)

    result = await client.read_input_registers(address=33000, count=1, device_id=3)
    assert not result.isError()
    assert result.registers == [1234]

    result = await client.read_holding_registers(address=43000, count=1)
    assert result.registers == [7]

    client.slave = 3
    assert (await client.read_input_registers(address=33000, count=1)).registers == [1234]


async def test_modbus_exception_is_a_result_not_a_raise(connection):
    """A device exception comes back like pymodbus's: isError() with the exception code."""
    connection.for_unit(1).fail_read(35000, IllegalDataAddressError(2), register_type="input")
    client = SerialProxyClient(PROXY_PORT)

    result = await client.read_input_registers(address=35000, count=1, device_id=1)

    assert result.isError()
    assert result.exception_code == 2
    assert result.registers == []


async def test_link_failure_raises(connection):
    """Timeouts raise, which the controller treats as a dropped link."""
    connection.for_unit(1).fail_read(33000, ModbusTimeoutError("no answer"), register_type="input")
    client = SerialProxyClient(PROXY_PORT)

    with pytest.raises(ModbusTimeoutError):
        await client.read_input_registers(address=33000, count=1, device_id=1)


async def test_writes_echo_values_like_pymodbus(connection):
    """write_register's result carries the written value, which the controller caches."""
    client = SerialProxyClient(PROXY_PORT)

    single = await client.write_register(address=43110, value=42, device_id=1)
    block = await client.write_registers(address=43141, values=[1, 2, 3], device_id=1)

    assert (single.isError(), single.registers) == (False, [42])
    assert (block.isError(), block.registers) == (False, [1, 2, 3])
    unit = connection.for_unit(1)
    assert (unit.holding[43110], unit.holding[43141], unit.holding[43143]) == (42, 1, 3)


async def test_write_exception_is_a_result(connection):
    """A refused write is reported as an error result."""
    connection.for_unit(1).fail_write(43110, IllegalDataAddressError(2))
    client = SerialProxyClient(PROXY_PORT)

    result = await client.write_register(address=43110, value=42, device_id=1)

    assert result.isError()
    assert result.exception_code == 2


async def test_connect_and_close(connection):
    """connect() reports the link state; close() drops it so the next request reopens it."""
    client = SerialProxyClient(PROXY_PORT)

    assert await client.connect() is True
    assert client.connected

    client.close()
    await next(iter(client._closing))
    assert not client.connected


def test_client_manager_picks_the_proxy_client_for_proxy_ports(connection, monkeypatch):
    """ESPHome proxy ports get SerialProxyClient; other serial ports stay on pymodbus."""
    from custom_components.solis_modbus import client_manager

    pymodbus_client = object()
    monkeypatch.setattr(client_manager, "AsyncModbusSerialClient", lambda **kwargs: pymodbus_client)

    manager = ModbusClientManager()
    proxy = manager.get_serial_client(PROXY_PORT, 9600, 8, "N", 1)
    local = manager.get_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1)

    assert isinstance(proxy, SerialProxyClient)
    assert local is pymodbus_client
    # Entries on the same proxy port share one client.
    assert manager.get_serial_client(PROXY_PORT, 9600, 8, "N", 1) is proxy
