"""ResyncFramerRTU: the answer to the pending request is found past junk bytes on a noisy serial line.

Unit tier: the framer is driven through its public API (`buildFrame` with a real request PDU, then
`handleFrame`), the way pymodbus's transport does it (append received bytes to a buffer, hand the
buffer over, cut the consumed length). The vectors were captured on a live RS-485 line.
"""

import pytest
from pymodbus.framer import FramerRTU
from pymodbus.pdu import DecodePDU
from pymodbus.pdu.register_message import (
    ReadHoldingRegistersRequest,
    ReadInputRegistersRequest,
    WriteMultipleRegistersRequest,
    WriteMultipleRegistersResponse,
)

from custom_components.solis_modbus.rtu_framer import FIRST_BYTE_DEADLINE_S, EarlyEnd, ResyncFramerRTU

DEVICE_ID = 1

# Ack of WriteMultipleRegisters(44105, 8 registers) behind a spurious 0xFF.
WRITE_ACK_WITH_JUNK = bytes.fromhex("ff 01 10 ac 49 00 08 31 49")
WRITE_ACK = WRITE_ACK_WITH_JUNK[1:]
# ReadInputRegisters answer, one register 0xAA55, behind a spurious 0xFF.
READ_ANSWER_WITH_JUNK = bytes.fromhex("ff 01 04 02 aa 55 07 af")
READ_ANSWER = READ_ANSWER_WITH_JUNK[1:]
# Bit-slipped start of an answer: no valid frame anywhere in it (CRC does not match).
BIT_SLIPPED = bytes.fromhex("01 90 0b 54 00 00 00 00 50 24")


def read_input_request(dev_id: int = DEVICE_ID) -> ReadInputRegistersRequest:
    return ReadInputRegistersRequest(dev_id=dev_id, address=33000, count=1)


def write_request(dev_id: int = DEVICE_ID) -> WriteMultipleRegistersRequest:
    return WriteMultipleRegistersRequest(dev_id=dev_id, address=44105, registers=list(range(8)))


def framer_after(request) -> ResyncFramerRTU:
    """A framer that has just sent `request`."""
    framer = ResyncFramerRTU(DecodePDU(False))
    framer.buildFrame(request)
    return framer


def crc_appended(frame_without_crc: str) -> bytes:
    body = bytes.fromhex(frame_without_crc)
    return body + FramerRTU.compute_CRC(body).to_bytes(2, "big")


def receive(framer, chunks, exp_devid: int = DEVICE_ID):
    """Deliver `chunks` like the transport does; return (pdu or None, bytes left in the buffer)."""
    buffer = b""
    for chunk in chunks:
        buffer += chunk
        used_len, pdu = framer.handleFrame(buffer, exp_devid, 0)
        buffer = buffer[used_len:]
        if pdu is not None:
            return pdu, buffer
    return None, buffer


def one_byte_per_call(data: bytes) -> list[bytes]:
    return [data[i : i + 1] for i in range(len(data))]


def whole(data: bytes) -> list[bytes]:
    return [data]


DELIVERIES = [pytest.param(whole, id="whole"), pytest.param(one_byte_per_call, id="one_byte_per_call")]


@pytest.mark.parametrize("deliver", DELIVERIES)
def test_write_ack_behind_junk_byte_decodes(deliver):
    pdu, _ = receive(framer_after(write_request()), deliver(WRITE_ACK_WITH_JUNK))

    assert isinstance(pdu, WriteMultipleRegistersResponse), "write ack behind a junk byte must still decode"
    assert (pdu.dev_id, pdu.address, pdu.count) == (DEVICE_ID, 44105, 8)


@pytest.mark.parametrize("deliver", DELIVERIES)
def test_read_answer_behind_junk_byte_decodes(deliver):
    pdu, _ = receive(framer_after(read_input_request()), deliver(READ_ANSWER_WITH_JUNK))

    assert pdu is not None, "read answer behind a junk byte must still decode"
    assert (pdu.dev_id, pdu.registers) == (DEVICE_ID, [0xAA55])


@pytest.mark.parametrize("deliver", DELIVERIES)
def test_clean_answer_decodes(deliver):
    pdu, _ = receive(framer_after(read_input_request()), deliver(READ_ANSWER))

    assert pdu is not None and pdu.registers == [0xAA55]


@pytest.mark.parametrize("deliver", DELIVERIES)
def test_bit_slipped_answer_yields_no_frame_and_consumes_everything(deliver):
    pdu, left_over = receive(framer_after(read_input_request()), deliver(BIT_SLIPPED))

    assert pdu is None
    assert left_over == b"", "nothing may be kept, the next attempt must start clean"


def test_bit_slipped_answer_without_pending_request_yields_no_frame_and_consumes_everything():
    pdu, left_over = receive(ResyncFramerRTU(DecodePDU(False)), whole(BIT_SLIPPED))

    assert pdu is None
    assert left_over == b""


def test_junk_frame_junk_returns_the_frame_and_consumes_the_junk():
    framer = framer_after(read_input_request())
    data = bytes.fromhex("ff 00") + READ_ANSWER + bytes.fromhex("ff 55")

    used_len, pdu = framer.handleFrame(data, DEVICE_ID, 0)

    assert pdu is not None and pdu.registers == [0xAA55]
    assert used_len == len(data)


def test_answer_found_behind_a_false_frame_start_that_never_completes():
    """A junk byte equal to the device id followed by a plausible function code claims a long frame."""
    framer = framer_after(read_input_request())
    data = bytes.fromhex("01 04 ff") + READ_ANSWER

    used_len, pdu = framer.handleFrame(data, DEVICE_ID, 0)

    assert pdu is not None and pdu.registers == [0xAA55]
    assert used_len == len(data)


@pytest.mark.parametrize("deliver", DELIVERIES)
def test_junk_byte_equal_to_device_id_in_front_of_answer_decodes(deliver):
    pdu, _ = receive(framer_after(read_input_request()), deliver(b"\x01" + READ_ANSWER))

    assert pdu is not None and pdu.registers == [0xAA55]


def test_incomplete_answer_is_kept_until_the_rest_arrives():
    framer = framer_after(read_input_request())

    used_len, pdu = framer.handleFrame(READ_ANSWER_WITH_JUNK[:5], DEVICE_ID, 0)

    assert pdu is None
    assert READ_ANSWER_WITH_JUNK[:5][used_len:] == READ_ANSWER[:4], "the junk byte goes, the started frame stays"


def test_answer_from_another_device_is_ignored():
    other_device = crc_appended("02 04 02 aa 55")

    pdu, left_over = receive(framer_after(read_input_request()), whole(other_device))

    assert pdu is None
    assert left_over == b""


def test_answer_for_the_pending_device_is_found_behind_another_devices_answer():
    other_device = crc_appended("02 04 02 11 22")

    pdu, _ = receive(framer_after(read_input_request()), whole(other_device + READ_ANSWER))

    assert pdu is not None and (pdu.dev_id, pdu.registers) == (DEVICE_ID, [0xAA55])


def test_answer_with_another_function_code_is_ignored():
    holding_answer = crc_appended("01 03 02 aa 55")

    pdu, _ = receive(framer_after(read_input_request()), whole(holding_answer))

    assert pdu is None


def test_exception_response_to_the_pending_request_decodes():
    exception_answer = crc_appended("01 84 02")

    pdu, _ = receive(framer_after(read_input_request()), whole(b"\xff" + exception_answer))

    assert pdu is not None and pdu.isError()
    assert (pdu.dev_id, pdu.exception_code) == (DEVICE_ID, 2)


def test_exception_response_to_another_function_is_ignored():
    pdu, _ = receive(framer_after(read_input_request()), whole(crc_appended("01 83 02")))

    assert pdu is None


def test_answer_with_wrong_crc_is_not_decoded():
    corrupted = READ_ANSWER[:-1] + b"\x00"

    pdu, left_over = receive(framer_after(read_input_request()), whole(corrupted))

    assert pdu is None
    assert left_over == b""


def test_without_pending_request_any_known_function_code_is_accepted_for_the_expected_device():
    framer = ResyncFramerRTU(DecodePDU(False))

    pdu, _ = receive(framer, whole(READ_ANSWER_WITH_JUNK))

    assert pdu is not None and pdu.registers == [0xAA55]


def test_function_code_with_sub_function_cut_short_waits_for_more_data():
    """Without a pending request, `01 18` (function 24) must not raise out of the transport callback."""
    framer = ResyncFramerRTU(DecodePDU(False))

    used_len, pdu = framer.handleFrame(bytes.fromhex("01 18"), DEVICE_ID, 0)

    assert (used_len, pdu) == (0, None)


def test_unknown_function_code_without_pending_request_is_junk():
    framer = ResyncFramerRTU(DecodePDU(False))

    pdu, left_over = receive(framer, whole(bytes.fromhex("01 55 00 00 00 00")))

    assert pdu is None
    assert left_over == b""


def test_next_request_after_an_answer_decodes_its_own_answer():
    framer = framer_after(read_input_request())
    receive(framer, whole(READ_ANSWER))
    framer.buildFrame(write_request())

    pdu, _ = receive(framer, whole(WRITE_ACK_WITH_JUNK))

    assert isinstance(pdu, WriteMultipleRegistersResponse)


def test_request_frame_is_the_stock_rtu_frame():
    request = ReadHoldingRegistersRequest(dev_id=DEVICE_ID, address=43000, count=4)

    ours = ResyncFramerRTU(DecodePDU(False)).buildFrame(request)
    stock = FramerRTU(DecodePDU(False)).buildFrame(request)

    assert ours == stock


def test_stock_framer_loses_the_write_ack_behind_a_junk_byte():
    """Pins the defect this framer works around: the stock framer never decodes the ack behind the junk byte."""
    stock = FramerRTU(DecodePDU(False))

    pdu, _ = receive(stock, whole(WRITE_ACK_WITH_JUNK))
    pdu_bytewise, _ = receive(FramerRTU(DecodePDU(False)), one_byte_per_call(WRITE_ACK_WITH_JUNK))

    assert pdu is None
    assert pdu_bytewise is None


def test_junk_bytes_are_counted():
    framer = framer_after(read_input_request())

    receive(framer, whole(BIT_SLIPPED))

    assert framer.junk_bytes_skipped == len(BIT_SLIPPED)


def test_junk_bytes_are_counted_when_delivered_one_byte_per_call():
    framer = framer_after(read_input_request())

    receive(framer, one_byte_per_call(BIT_SLIPPED))

    assert framer.junk_bytes_skipped == len(BIT_SLIPPED)


def test_answer_after_junk_counts_as_rescued():
    framer = framer_after(read_input_request())

    receive(framer, whole(READ_ANSWER_WITH_JUNK))

    assert (framer.frames_rescued, framer.junk_bytes_skipped) == (1, 1)


def test_answer_after_junk_counts_as_rescued_when_delivered_one_byte_per_call():
    framer = framer_after(read_input_request())

    receive(framer, one_byte_per_call(READ_ANSWER_WITH_JUNK))

    assert (framer.frames_rescued, framer.junk_bytes_skipped) == (1, 1)


def test_clean_answer_counts_nothing():
    framer = framer_after(read_input_request())

    receive(framer, whole(READ_ANSWER))

    assert (framer.frames_rescued, framer.junk_bytes_skipped) == (0, 0)


def test_junk_before_a_lost_answer_is_not_credited_to_the_retry():
    framer = framer_after(read_input_request())
    receive(framer, whole(BIT_SLIPPED))
    framer.buildFrame(read_input_request())  # the retry

    receive(framer, whole(READ_ANSWER))

    assert framer.frames_rescued == 0


BAUDRATE = 9600
SILENCE_S = 0.310
BITS_PER_BYTE = 11  # start + 8 data + parity + stop
EPSILON_S = 0.001


class FakeTimer:
    def __init__(self, due_s: float, callback) -> None:
        self.due_s = due_s
        self.callback = callback
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class FakeScheduler:
    """Clock and `call_later` in one: time only moves when the test advances it."""

    def __init__(self) -> None:
        self.now_s = 100.0
        self.timers: list[FakeTimer] = []

    def clock(self) -> float:
        return self.now_s

    def call_later(self, delay_s: float, callback) -> FakeTimer:
        timer = FakeTimer(self.now_s + delay_s, callback)
        self.timers.append(timer)
        return timer

    def advance(self, seconds: float) -> None:
        """Move time forward, firing every timer that falls due, in order, at its due time."""
        target_s = self.now_s + seconds
        while True:
            due = [timer for timer in self.timers if not timer.cancelled and timer.due_s <= target_s]
            if not due:
                break
            timer = min(due, key=lambda t: t.due_s)
            self.timers.remove(timer)
            self.now_s = max(self.now_s, timer.due_s)
            timer.callback()
        self.now_s = target_s


class Attempts:
    """The framer's hook: remembers, per attempt number, whether it was ended."""

    def __init__(self) -> None:
        self.started = 0
        self.ended: list[int] = []

    def capture_attempt(self):
        number = self.started
        self.started += 1
        return lambda: self.ended.append(number)


class EarlyEndRig:
    def __init__(self) -> None:
        self.scheduler = FakeScheduler()
        self.attempts = Attempts()
        self.framer = ResyncFramerRTU(
            DecodePDU(False),
            clock=self.scheduler.clock,
            early_end=EarlyEnd(BAUDRATE, SILENCE_S, self.attempts.capture_attempt),
            call_later=self.scheduler.call_later,
        )

    def send(self, request=None) -> float:
        """Build a request; return the line time of its frame in seconds."""
        frame = self.framer.buildFrame(request or read_input_request())
        return len(frame) * BITS_PER_BYTE / BAUDRATE

    def receive(self, buffer: bytes):
        return self.framer.handleFrame(buffer, DEVICE_ID, 0)

    def deliver_one_byte_at_a_time(self, data: bytes, spacing_s: float) -> None:
        buffer = b""
        for byte in one_byte_per_call(data):
            self.scheduler.advance(spacing_s)
            buffer += byte
            used_len, pdu = self.receive(buffer)
            buffer = buffer[used_len:]
            if pdu is not None:
                return


def test_attempt_with_no_byte_ends_at_the_first_byte_deadline_after_the_request_end():
    rig = EarlyEndRig()
    line_time_s = rig.send()

    rig.scheduler.advance(line_time_s + FIRST_BYTE_DEADLINE_S - EPSILON_S)
    assert rig.attempts.ended == [], "the deadline runs from the end of the request on the wire, not before"
    rig.scheduler.advance(2 * EPSILON_S)

    assert rig.attempts.ended == [0]
    assert (rig.framer.attempts_no_answer, rig.framer.attempts_bad_answer) == (1, 0)


def test_attempt_with_no_byte_is_ended_once():
    rig = EarlyEndRig()
    rig.send()

    rig.scheduler.advance(10.0)

    assert rig.attempts.ended == [0]
    assert rig.framer.attempts_no_answer == 1


def test_bit_slipped_answer_ends_the_attempt_310_ms_after_the_last_byte():
    rig = EarlyEndRig()
    rig.send()

    rig.deliver_one_byte_at_a_time(BIT_SLIPPED, spacing_s=0.2)  # slower than 10 bytes of line time, faster than the silence
    assert rig.attempts.ended == [], "the line is not silent between the bytes"
    rig.scheduler.advance(SILENCE_S - EPSILON_S)
    assert rig.attempts.ended == [], "310 ms of silence have not passed yet"
    rig.scheduler.advance(2 * EPSILON_S)

    assert rig.attempts.ended == [0]
    assert (rig.framer.attempts_no_answer, rig.framer.attempts_bad_answer) == (0, 1)


def test_bit_slipped_answer_delivered_in_one_chunk_ends_the_attempt_310_ms_later():
    rig = EarlyEndRig()
    rig.send()
    rig.scheduler.advance(0.1)
    rig.receive(BIT_SLIPPED)

    rig.scheduler.advance(SILENCE_S - EPSILON_S)
    assert rig.attempts.ended == []
    rig.scheduler.advance(2 * EPSILON_S)

    assert rig.attempts.ended == [0]


def test_valid_answer_ends_nothing_and_leaves_no_timer():
    rig = EarlyEndRig()
    rig.send()

    rig.deliver_one_byte_at_a_time(READ_ANSWER_WITH_JUNK, spacing_s=0.05)
    rig.scheduler.advance(10.0)

    assert rig.attempts.ended == []
    assert (rig.framer.attempts_no_answer, rig.framer.attempts_bad_answer) == (0, 0)


def test_valid_answer_in_one_chunk_ends_nothing():
    rig = EarlyEndRig()
    rig.send()
    rig.scheduler.advance(0.1)

    _, pdu = rig.receive(READ_ANSWER_WITH_JUNK)
    rig.scheduler.advance(10.0)

    assert pdu is not None
    assert rig.attempts.ended == []


def test_bytes_after_a_valid_answer_do_not_end_or_count_anything():
    rig = EarlyEndRig()
    rig.send()
    rig.receive(READ_ANSWER)

    rig.receive(b"\xff")
    rig.scheduler.advance(10.0)

    assert rig.attempts.ended == []
    assert rig.framer.attempts_bad_answer == 0


def test_byte_arriving_just_before_the_deadline_cancels_it_and_the_answer_still_decodes():
    rig = EarlyEndRig()
    line_time_s = rig.send()
    rig.scheduler.advance(line_time_s + FIRST_BYTE_DEADLINE_S - EPSILON_S)

    rig.receive(b"\xff")
    rig.scheduler.advance(0.1)
    assert rig.attempts.ended == [], "a started answer is never cut by the first-byte deadline"
    _, pdu = rig.receive(READ_ANSWER_WITH_JUNK)
    rig.scheduler.advance(10.0)

    assert pdu is not None and pdu.registers == [0xAA55]
    assert rig.attempts.ended == []
    assert rig.framer.attempts_no_answer == 0


def test_timers_of_a_finished_attempt_never_end_the_next_attempt():
    rig = EarlyEndRig()
    rig.send()
    rig.scheduler.advance(0.1)
    rig.receive(BIT_SLIPPED)  # attempt 0 now waits for its silence timer
    stale_timers = list(rig.scheduler.timers)
    rig.send()  # attempt 1

    for timer in stale_timers:
        timer.callback()  # even a timer that could not be cancelled in time must not touch attempt 1

    assert rig.attempts.ended == []
    assert (rig.framer.attempts_no_answer, rig.framer.attempts_bad_answer) == (0, 0)


def test_only_the_current_attempt_is_ended_when_time_passes_after_a_resend():
    rig = EarlyEndRig()
    rig.send()
    rig.scheduler.advance(0.3)
    rig.send()

    rig.scheduler.advance(10.0)

    assert rig.attempts.ended == [1]
    assert rig.framer.attempts_no_answer == 1


def test_first_byte_latency_counts_from_the_request_end_and_a_junk_byte_is_the_first_byte():
    rig = EarlyEndRig()
    assert (rig.framer.first_byte_latency_last_ms, rig.framer.first_byte_latency_max_ms) == (None, None), "nothing measured yet"
    line_time_s = rig.send()
    rig.scheduler.advance(0.250)

    rig.receive(b"\xff")
    rig.scheduler.advance(0.020)
    rig.receive(b"\xff\x01")  # later bytes of the same attempt are not first bytes

    assert rig.framer.first_byte_latency_last_ms == pytest.approx((0.250 - line_time_s) * 1000.0)


def test_first_byte_latency_keeps_the_maximum_over_attempts():
    rig = EarlyEndRig()
    line_time_s = rig.send()
    rig.scheduler.advance(0.250)
    rig.receive(READ_ANSWER)
    rig.send()
    rig.scheduler.advance(0.100)
    rig.receive(READ_ANSWER)

    assert rig.framer.first_byte_latency_last_ms == pytest.approx((0.100 - line_time_s) * 1000.0)
    assert rig.framer.first_byte_latency_max_ms == pytest.approx((0.250 - line_time_s) * 1000.0)


def test_without_a_running_event_loop_the_framer_works_and_arms_no_timer():
    attempts = Attempts()
    framer = ResyncFramerRTU(DecodePDU(False), early_end=EarlyEnd(BAUDRATE, SILENCE_S, attempts.capture_attempt))
    framer.buildFrame(read_input_request())

    used_len, pdu = framer.handleFrame(BIT_SLIPPED, DEVICE_ID, 0)
    pdu_after, _ = receive(framer, whole(READ_ANSWER_WITH_JUNK))

    assert (used_len, pdu) == (len(BIT_SLIPPED), None)
    assert pdu_after is not None and pdu_after.registers == [0xAA55]
    assert attempts.ended == []
