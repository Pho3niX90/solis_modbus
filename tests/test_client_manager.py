import asyncio
import logging
import sys
import time
import unittest
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.framer import FramerRTU
from pymodbus.pdu.register_message import ReadInputRegistersRequest

from custom_components.solis_modbus import client_manager
from custom_components.solis_modbus.client_manager import MIN_INTER_FRAME_MS, ModbusClientManager, create_serial_client
from custom_components.solis_modbus.rtu_framer import FIRST_BYTE_DEADLINE_S, ResyncFramerRTU


class TestModbusClientManager(unittest.TestCase):
    def setUp(self):
        # Reset singleton
        ModbusClientManager._instance = None
        self.manager = ModbusClientManager.get_instance()

    def tearDown(self):
        ModbusClientManager._instance = None

    @patch("custom_components.solis_modbus.client_manager.AsyncModbusTcpClient")
    def test_get_client_creates_new_if_not_exists(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client1 = self.manager.get_tcp_client("1.2.3.4", 502)

        mock_client_cls.assert_called_once_with(host="1.2.3.4", port=502, timeout=5, retries=1)
        self.assertEqual(client1, mock_client)
        self.assertEqual(self.manager._clients["1.2.3.4:502"]["ref_count"], 1)

    @patch("custom_components.solis_modbus.client_manager.AsyncModbusTcpClient")
    def test_get_client_returns_existing_and_increments_ref(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client1 = self.manager.get_tcp_client("1.2.3.4", 502)
        client2 = self.manager.get_tcp_client("1.2.3.4", 502)

        mock_client_cls.assert_called_once()  # Called only once!
        self.assertEqual(client1, client2)
        self.assertEqual(self.manager._clients["1.2.3.4:502"]["ref_count"], 2)

    @patch("custom_components.solis_modbus.client_manager.AsyncModbusTcpClient")
    def test_get_client_lock(self, mock_client_cls):
        self.manager.get_tcp_client("1.2.3.4", 502)
        lock = self.manager.get_client_lock("1.2.3.4:502")

        self.assertIsNotNone(lock)
        # Should be the same lock instance
        self.assertEqual(lock, self.manager._clients["1.2.3.4:502"]["lock"])

        # Non-existent
        self.assertIsNone(self.manager.get_client_lock("9.9.9.9:502"))

    @patch("custom_components.solis_modbus.client_manager.AsyncModbusTcpClient")
    def test_release_client(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.connected = True
        mock_client_cls.return_value = mock_client

        # Get twice
        self.manager.get_tcp_client("1.2.3.4", 502)
        self.manager.get_tcp_client("1.2.3.4", 502)

        # Release once
        self.manager.release_client("1.2.3.4:502")
        self.assertEqual(self.manager._clients["1.2.3.4:502"]["ref_count"], 1)
        mock_client.close.assert_not_called()

        # Release again
        self.manager.release_client("1.2.3.4:502")
        # Should be removed
        self.assertNotIn("1.2.3.4:502", self.manager._clients)
        mock_client.close.assert_called_once()

    @patch("custom_components.solis_modbus.client_manager.AsyncModbusTcpClient")
    def test_release_closes_a_client_that_is_down(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.connected = False
        mock_client_cls.return_value = mock_client

        self.manager.get_tcp_client("1.2.3.4", 502)
        self.manager.release_client("1.2.3.4:502")

        self.assertNotIn("1.2.3.4:502", self.manager._clients)
        mock_client.close.assert_called_once()

    def test_release_non_existent_client(self):
        # Should not raise
        self.manager.release_client("9.9.9.9:502")


class TestModbusClientManagerInterFrame(IsolatedAsyncioTestCase):
    def setUp(self):
        ModbusClientManager._instance = None
        self.manager = ModbusClientManager.get_instance()

    def tearDown(self):
        ModbusClientManager._instance = None

    @patch("custom_components.solis_modbus.client_manager.AsyncModbusTcpClient")
    async def test_inter_frame_wait_updates_shared_timestamp(self, mock_client_cls):
        mock_client_cls.return_value = MagicMock()
        self.manager.get_tcp_client("1.2.3.4", 502)
        self.assertEqual(0.0, self.manager.get_last_modbus_request("1.2.3.4:502"))
        await self.manager.inter_frame_wait("1.2.3.4:502", is_write=False)
        self.assertGreater(self.manager.get_last_modbus_request("1.2.3.4:502"), 0.0)

    @patch("custom_components.solis_modbus.client_manager.AsyncModbusTcpClient")
    @patch("custom_components.solis_modbus.client_manager.time.perf_counter")
    @patch("custom_components.solis_modbus.client_manager.asyncio.sleep", new_callable=AsyncMock)
    async def test_inter_frame_wait_enforces_min_interval_for_reads_and_writes(self, mock_sleep, mock_perf_counter, mock_client_cls):
        mock_client_cls.return_value = MagicMock()
        # Two operations back-to-back on the same connection: each should independently
        # compute a wait based on MIN_INTER_FRAME_MS, regardless of is_write.
        # Call sequence: [read: current_time, read: recorded last] [write: current_time, write: recorded last]
        mock_perf_counter.side_effect = [0.0, 0.31, 0.32, 0.62]
        self.manager.get_tcp_client("1.2.3.4", 502)

        await self.manager.inter_frame_wait("1.2.3.4:502", is_write=False)
        await self.manager.inter_frame_wait("1.2.3.4:502", is_write=True)

        expected_delay_s = MIN_INTER_FRAME_MS / 1000
        self.assertEqual(2, mock_sleep.call_count)
        # Read: 0.0 elapsed since last (0.0) -> full MIN_INTER_FRAME_MS wait.
        self.assertAlmostEqual(expected_delay_s, mock_sleep.call_args_list[0].args[0])
        # Write: 10ms elapsed since last (0.31) -> remaining wait is MIN_INTER_FRAME_MS - 10ms.
        self.assertAlmostEqual(expected_delay_s - 0.01, mock_sleep.call_args_list[1].args[0])


@pytest.fixture(autouse=False)
def pyserial_present(monkeypatch):
    """pymodbus's serial client only checks that pyserial is importable when it is constructed; nothing here opens a port."""
    monkeypatch.setitem(sys.modules, "serial", MagicMock())


async def test_serial_client_waits_1500_ms_and_retries_3_times(pyserial_present):
    client = create_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1)

    assert client.ctx.comm_params.timeout_connect == 1.5
    assert client.ctx.retries == 3


async def test_serial_client_leaves_reconnecting_to_the_integration(pyserial_present):
    """pymodbus's own reconnect (after retries+3 unanswered requests) would race check_connection."""
    client = create_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1)

    assert client.ctx.comm_params.reconnect_delay == 0


async def test_serial_client_without_a_response_future_leaves_the_attempt_to_the_timeout(pyserial_present):
    """If pymodbus stops exposing ctx.response_future, building a request must not fail it."""
    client = create_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1)
    client.ctx.response_future = None
    framer = client.ctx.framer

    framer.buildFrame(ReadInputRegistersRequest(address=33000, count=1, dev_id=1))

    assert framer._end_attempt is client_manager._no_early_end
    framer._end_attempt()  # nothing to end, nothing raised
    framer._cancel_timers()


async def test_serial_client_uses_the_resync_framer(pyserial_present):
    client = create_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1)

    assert isinstance(client.ctx.framer, ResyncFramerRTU)


async def test_manager_serial_client_resyncs_and_tcp_client_is_unchanged(pyserial_present):
    manager = ModbusClientManager()

    serial = manager.get_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1)
    tcp = manager.get_tcp_client("1.2.3.4", 502)

    assert isinstance(serial.ctx.framer, ResyncFramerRTU)
    assert (tcp.ctx.comm_params.timeout_connect, tcp.ctx.retries) == (5, 1)
    assert not isinstance(tcp.ctx.framer, ResyncFramerRTU)


async def test_serial_client_decodes_an_answer_that_arrives_one_byte_at_a_time_behind_junk(pyserial_present):
    """Through pymodbus's transport: request sent, answer `ff 01 04 02 aa 55 07 af` trickles in."""
    client = create_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1)
    ctx = client.ctx
    request = ReadInputRegistersRequest(dev_id=1, address=33000, count=1)
    ctx.response_future = asyncio.get_running_loop().create_future()
    ctx.request_dev_id = request.dev_id
    ctx.framer.buildFrame(request)

    for byte in bytes.fromhex("ff 01 04 02 aa 55 07 af"):
        ctx.datagram_received(bytes([byte]), None)

    assert ctx.response_future.done()
    assert ctx.response_future.result().registers == [0xAA55]
    assert ctx.recv_buffer == b""


BIT_SLIPPED_ANSWER = bytes.fromhex("01 90 0b 54 00 00 00 00 50 24")
VALID_ANSWER = bytes.fromhex("01 04 02 aa 55 07 af")
BACKSTOP_S = 1.5


class _SerialLine:
    """Stands in for the transport of a real pymodbus serial client: records each request sent and when."""

    def __init__(self, ctx) -> None:
        self.sent_at_s: list[float] = []
        self.sent_events = [asyncio.Event(), asyncio.Event()]
        ctx.transport = MagicMock()
        ctx.low_level_send = self.send

    def send(self, data, addr=None):
        self.sent_events[len(self.sent_at_s)].set()
        self.sent_at_s.append(time.monotonic())


async def test_serial_client_resends_310_ms_after_a_bad_answer_instead_of_waiting_for_the_timeout(pyserial_present):
    """Timing tier (real event loop, wall clock): a bit-slipped answer, silence, resend, then a valid answer completes the call."""
    ctx = create_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1).ctx
    line = _SerialLine(ctx)
    call = asyncio.create_task(ctx.execute(False, ReadInputRegistersRequest(dev_id=1, address=33000, count=1)))
    await asyncio.wait_for(line.sent_events[0].wait(), 1)

    for byte in BIT_SLIPPED_ANSWER:
        ctx.datagram_received(bytes([byte]), None)
    last_byte_at_s = time.monotonic()
    await asyncio.wait_for(line.sent_events[1].wait(), BACKSTOP_S)
    resend_after_s = line.sent_at_s[1] - last_byte_at_s
    for byte in VALID_ANSWER:
        ctx.datagram_received(bytes([byte]), None)
    response = await asyncio.wait_for(call, 1)

    assert MIN_INTER_FRAME_MS / 1000 - 0.01 <= resend_after_s < BACKSTOP_S - 0.5, "resent after the line silence, well before the client timeout"
    assert response.registers == [0xAA55]
    assert response.retries == 1
    assert ctx.framer.attempts_bad_answer == 1


async def test_serial_client_resends_after_the_first_byte_deadline_when_nothing_answers(pyserial_present):
    """Timing tier (real event loop, wall clock): a silent attempt is resent after about 0.5 s, not the 1.5 s timeout."""
    ctx = create_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1).ctx
    line = _SerialLine(ctx)
    call = asyncio.create_task(ctx.execute(False, ReadInputRegistersRequest(dev_id=1, address=33000, count=1)))

    await asyncio.wait_for(line.sent_events[1].wait(), BACKSTOP_S)
    silent_attempt_s = line.sent_at_s[1] - line.sent_at_s[0]
    for byte in VALID_ANSWER:
        ctx.datagram_received(bytes([byte]), None)
    response = await asyncio.wait_for(call, 1)

    assert FIRST_BYTE_DEADLINE_S <= silent_attempt_s < BACKSTOP_S - 0.5
    assert response.registers == [0xAA55]
    assert ctx.framer.attempts_no_answer == 1


async def test_serial_client_keeps_a_stock_framer_that_is_not_rtu_and_says_so(caplog):
    class NoRtuClient:
        ctx = MagicMock(framer=object())

        def __init__(self, **kwargs):
            pass

    with patch.object(client_manager, "AsyncModbusSerialClient", NoRtuClient), caplog.at_level(logging.WARNING, logger=client_manager.__name__):
        client = create_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1)

    assert not isinstance(client.ctx.framer, ResyncFramerRTU)
    assert "keeping its stock framer" in caplog.text


async def test_serial_client_framer_replacement_keeps_the_stock_type_for_tid_handling(pyserial_present):
    """TransactionManager.getNextTID keeps transaction id 0 for FramerRTU subclasses."""
    client = create_serial_client("/dev/ttyUSB0", 9600, 8, "N", 1)

    assert isinstance(client.ctx.framer, FramerRTU)
    assert client.ctx.getNextTID() == 0


if __name__ == "__main__":
    unittest.main()
