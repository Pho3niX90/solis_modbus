"""A poll batch must never open a connection: only check_connection reconnects."""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.client import AsyncModbusTcpClient

from custom_components.solis_modbus.client_manager import ModbusClientManager
from custom_components.solis_modbus.const import CONN_TYPE_TCP
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.data_retrieval import DataRetrieval
from custom_components.solis_modbus.modbus_controller import ModbusController
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup

HOST = "127.0.0.1"


class _FakeClient:
    """Counts connect() calls; can park reads until close() or release()."""

    def __init__(self):
        self.connected = True
        self.connects = 0
        self.closes = 0
        self.reads: list[int] = []
        self.hold_reads = False
        self.drop_after_reads: int | None = None
        self.connect_gate: asyncio.Event | None = None
        self._parked: list[asyncio.Future] = []

    async def connect(self):
        self.connects += 1
        if self.connect_gate is not None:
            await self.connect_gate.wait()
        self.connected = True
        return True

    def close(self):
        self.closes += 1
        self.connected = False
        for fut in self._parked:
            if not fut.done():
                fut.set_exception(ConnectionError("connection closed"))
        self._parked = []

    def release(self):
        self.hold_reads = False
        for fut in self._parked:
            if not fut.done():
                fut.set_result(None)
        self._parked = []

    async def _read(self, address, count):
        if not self.connected:
            raise ConnectionError("Not connected")
        self.reads.append(address)
        if self.hold_reads:
            fut = asyncio.get_running_loop().create_future()
            self._parked.append(fut)
            await fut
        if self.drop_after_reads is not None and len(self.reads) >= self.drop_after_reads:
            self.connected = False
        return MagicMock(isError=lambda: False, registers=[0] * count)

    async def read_input_registers(self, address, count, device_id):
        return await self._read(address, count)

    async def read_holding_registers(self, address, count, device_id):
        return await self._read(address, count)


def _groups(speed: PollSpeed, *starts: int) -> list[SolisSensorGroup]:
    groups = []
    for start in starts:
        group = MagicMock(spec=SolisSensorGroup)
        group.poll_speed = speed
        group.start_register = start
        group.registrar_count = 1
        groups.append(group)
    return groups


@pytest.fixture(autouse=True)
def _real_register_image():
    """The fake client reads zeros; tests for the blank image probe are in test_blank_register_image.py."""
    with patch.object(DataRetrieval, "_image_is_blank", AsyncMock(return_value=False)):
        yield


@pytest.fixture(autouse=True)
def _fresh_manager():
    ModbusClientManager._instance = None
    with patch("custom_components.solis_modbus.client_manager.MIN_INTER_FRAME_MS", 0):
        yield
    ModbusClientManager._instance = None


@pytest.fixture
def rig():
    fast, normal, slow = _groups(PollSpeed.FAST, 33000, 33100, 33200), _groups(PollSpeed.NORMAL, 34000), _groups(PollSpeed.SLOW, 35000)
    client = _FakeClient()
    with patch("custom_components.solis_modbus.client_manager.AsyncModbusTcpClient", return_value=client):
        hass = MagicMock()
        hass.is_running = False
        inverter_config = MagicMock()
        controller = ModbusController(hass, inverter_config, sensor_groups=[*fast, *normal, *slow], connection_type=CONN_TYPE_TCP, host=HOST, port=502)
    with patch("custom_components.solis_modbus.data_retrieval.cache_save"), patch("custom_components.solis_modbus.data_retrieval.notify_register_update"):
        yield DataRetrieval(hass, controller), controller, client


async def _poll_all(retrieval: DataRetrieval) -> None:
    await asyncio.gather(retrieval.modbus_update_fast(), retrieval.modbus_update_normal(), retrieval.modbus_update_slow())


async def _settle() -> None:
    for _ in range(10):
        await asyncio.sleep(0)


async def test_failed_read_drops_link_and_queued_batches_do_not_reconnect(rig):
    retrieval, controller, client = rig

    async def failing_read(address, count, device_id):
        client.reads.append(address)
        await asyncio.sleep(0)  # lets the other batches queue
        if address == 33100:
            raise ConnectionError("no response")
        return MagicMock(isError=lambda: False, registers=[0] * count)

    client.read_input_registers = failing_read
    await _poll_all(retrieval)

    assert client.reads == [33000, 33100]
    assert client.connects == 0
    assert retrieval.poll_updating[PollSpeed.FAST] == {}


async def test_link_dropped_between_groups_does_not_reconnect(rig):
    retrieval, controller, client = rig
    client.drop_after_reads = 1

    await _poll_all(retrieval)

    assert client.reads == [33000]
    assert client.connects == 0


async def test_stop_and_close_with_batches_in_flight_open_no_connection(rig):
    retrieval, controller, client = rig
    client.hold_reads = True

    polling = asyncio.gather(retrieval.modbus_update_fast(), retrieval.modbus_update_normal(), retrieval.modbus_update_slow())
    await _settle()
    assert client.reads == [33000]

    await retrieval.async_stop()
    controller.close_connection()
    await polling

    assert client.reads == [33000]
    assert client.connects == 0


async def test_stop_between_groups_ends_the_batch(rig):
    retrieval, controller, client = rig
    client.hold_reads = True

    polling = asyncio.create_task(retrieval.modbus_update_fast())
    await _settle()
    await retrieval.async_stop()
    client.release()
    await polling

    assert client.reads == [33000]
    assert client.connects == 0


async def test_closed_controller_never_connects(rig):
    retrieval, controller, client = rig
    controller.close_connection()
    assert client.connected is False

    assert await controller.connect() is False
    assert await controller.async_read_holding_register(40000, 1) is None
    assert await controller.async_read_input_register(33000, 1) is None
    assert client.connects == 0


async def test_connect_in_flight_when_closed_is_closed_again(rig):
    retrieval, controller, client = rig
    client.connected = False
    client.connect_gate = asyncio.Event()

    connecting = asyncio.create_task(controller.connect())
    await _settle()
    assert client.connects == 1
    controller.close_connection()
    client.connect_gate.set()

    assert await connecting is False
    assert client.connected is False


async def test_connect_in_flight_when_closed_leaves_a_shared_client_open(rig):
    retrieval, controller, client = rig
    other = ModbusController(MagicMock(), MagicMock(), connection_type=CONN_TYPE_TCP, host=HOST, port=502, device_id=2)
    client.connected = False
    client.connect_gate = asyncio.Event()

    connecting = asyncio.create_task(controller.connect())
    await _settle()
    controller.close_connection()
    client.connect_gate.set()

    assert await connecting is False
    assert other.connected()


async def test_connect_queued_on_the_lock_when_closed_opens_nothing(rig):
    retrieval, controller, client = rig
    client.connected = False
    await controller.poll_lock.acquire()

    connecting = asyncio.create_task(controller.connect())
    await _settle()
    controller.close_connection()
    controller.poll_lock.release()

    assert await connecting is False
    assert client.connects == 0


async def test_closed_controller_does_not_report_a_shared_link(rig):
    retrieval, controller, client = rig
    ModbusController(MagicMock(), MagicMock(), connection_type=CONN_TYPE_TCP, host=HOST, port=502, device_id=2)
    controller.close_connection()

    assert client.connected is True
    assert await controller.connect() is False


async def test_reload_leaves_no_connection_parked_on_a_one_connection_gateway(socket_enabled):
    accepted: list[asyncio.StreamWriter] = []
    request_seen = asyncio.Event()
    hold = asyncio.Event()

    async def gateway(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        accepted.append(writer)
        if len(accepted) > 1:
            await asyncio.sleep(3600)
            return
        with contextlib.suppress(ConnectionError):
            while request := await reader.read(12):
                request_seen.set()
                await hold.wait()
                count = int.from_bytes(request[10:12], "big")
                writer.write(request[:4] + (3 + 2 * count).to_bytes(2, "big") + request[6:8] + bytes([2 * count]) + bytes(2 * count))
                await writer.drain()

    server = await asyncio.start_server(gateway, HOST, 0)
    port = server.sockets[0].getsockname()[1]
    try:
        hass = MagicMock()
        hass.is_running = False
        groups = [*_groups(PollSpeed.FAST, 33000, 33100), *_groups(PollSpeed.NORMAL, 34000), *_groups(PollSpeed.SLOW, 35000)]

        def short_timeout_client(host, port, timeout, retries):
            # pymodbus close() does not abort a pending request; shorten its wait (production: 5 s, 1 retry)
            return AsyncModbusTcpClient(host=host, port=port, timeout=0.5, retries=0)

        with patch("custom_components.solis_modbus.client_manager.AsyncModbusTcpClient", side_effect=short_timeout_client):
            controller = ModbusController(hass, MagicMock(), sensor_groups=groups, connection_type=CONN_TYPE_TCP, host=HOST, port=port)
        retrieval = DataRetrieval(hass, controller)
        assert await controller.connect()

        with patch("custom_components.solis_modbus.data_retrieval.cache_save"), patch("custom_components.solis_modbus.data_retrieval.notify_register_update"):
            polling = asyncio.gather(retrieval.modbus_update_fast(), retrieval.modbus_update_normal(), retrieval.modbus_update_slow())
            await asyncio.wait_for(request_seen.wait(), 5)

            await retrieval.async_stop()
            controller.close_connection()
            await asyncio.wait_for(polling, 5)
        await asyncio.sleep(0.3)

        assert len(accepted) == 1
    finally:
        hold.set()
        server.close()
        for writer in accepted:
            writer.close()
        with contextlib.suppress(Exception):
            await server.wait_closed()
