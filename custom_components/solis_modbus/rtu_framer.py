"""RTU framer that finds the answer to the pending request inside a noisy serial stream.

pymodbus's stock `FramerRTU` takes the first byte of the receive buffer as the device id and the
second as the function code. A spurious byte in front of an otherwise valid answer therefore makes it
wait for a frame that never completes, and the valid answer behind the junk byte is never decoded.
This framer knows which request is pending (device id from the transaction manager, function code
recorded in `buildFrame`) and only accepts a frame that answers it, so it can hunt through the buffer
for one.

It also ends a failed attempt early instead of leaving it to the client timeout (a backstop):

- no byte at all within `FIRST_BYTE_DEADLINE_S` after the request left the wire: the attempt ends,
  a silent attempt costs about that deadline plus the request's line time;
- bytes arrived but hold no valid answer, then `EarlyEnd.silence_s` without another byte: the attempt
  ends, a corrupted answer costs about its own line time plus the silence. The silence is the Solis
  frame interval, so the retry that follows leaves the inverter that long after its last byte;
- any received byte, junk included, cancels the first-byte deadline: a started answer is never cut by it.

An attempt ends through a hook from the client factory, so the framer never reaches into pymodbus.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from pymodbus.framer import FramerRTU
from pymodbus.pdu import ModbusPDU

_LOGGER = logging.getLogger(__name__)

_EXCEPTION_RESPONSE_FLAG = 0x80
_MIN_CANDIDATE_BYTES = 2  # <device id><function code>
_CRC_BYTES = 2
_MS_PER_S = 1000.0
_BITS_PER_BYTE = 11  # start + 8 data + parity + stop: the longest 8-bit frame format

# Longest wait for the first byte of an answer, from the end of the request on the wire. The Solis
# starts answering within about 0.15 s; 0.5 s keeps a margin of more than three.
FIRST_BYTE_DEADLINE_S = 0.5


Scheduler = Callable[[float, Callable[[], None]], asyncio.TimerHandle | None]


def loop_call_later(delay_s: float, callback: Callable[[], None]) -> asyncio.TimerHandle | None:
    """Schedule `callback` on the running event loop; None (nothing scheduled) outside one."""
    try:
        return asyncio.get_running_loop().call_later(delay_s, callback)
    except RuntimeError:
        return None


@dataclass(frozen=True)
class EarlyEnd:
    """What the framer needs to end a failed attempt early.

    `capture_attempt` is called when a request is built and returns a function that ends exactly
    that attempt (and does nothing once the attempt is over); it is how the framer fails the
    attempt's pending answer without knowing pymodbus's transaction manager.
    """

    baudrate: int
    silence_s: float
    capture_attempt: Callable[[], Callable[[], None]]


class ResyncFramerRTU(FramerRTU):
    """`FramerRTU` that skips junk before the answer to the pending request.

    Counters are plain attributes, updated only from the event loop that owns the transport, so there
    is no race to guard against. They are read by diagnostics only. Without `early_end`, or outside a
    running event loop, no timer is armed and attempts end only by the client's own timeout.
    """

    def __init__(
        self,
        decoder,
        clock: Callable[[], float] = time.monotonic,
        early_end: EarlyEnd | None = None,
        call_later: Scheduler = loop_call_later,
    ) -> None:
        """Create the framer; `clock` (monotonic seconds) and `call_later` are parameters so tests can drive them."""
        super().__init__(decoder)
        self._clock = clock
        self._early_end = early_end
        self._call_later = call_later
        self._request_function_code: int | None = None
        self._request_end_s: float | None = None
        self._attempt_has_bytes = False
        self._end_attempt: Callable[[], None] | None = None
        self._first_byte_timer: asyncio.TimerHandle | None = None
        self._silence_timer: asyncio.TimerHandle | None = None
        self._junk_bytes_this_exchange = 0
        self.junk_bytes_skipped = 0
        self.frames_rescued = 0
        self.first_byte_latency_last_ms: float | None = None
        self.first_byte_latency_max_ms: float | None = None
        self.attempts_no_answer = 0
        self.attempts_bad_answer = 0

    def buildFrame(self, message: ModbusPDU) -> bytes:  # noqa: N802 - pymodbus API name
        """Record the pending request, arm the first-byte deadline, then build the frame as usual."""
        frame = super().buildFrame(message)
        self._cancel_timers()
        self._request_function_code = message.function_code
        self._junk_bytes_this_exchange = 0
        self._attempt_has_bytes = False
        self._end_attempt = None
        line_time_s = len(frame) * _BITS_PER_BYTE / self._early_end.baudrate if self._early_end else 0.0
        self._request_end_s = self._clock() + line_time_s
        if self._early_end is not None:
            end_attempt = self._early_end.capture_attempt()
            self._first_byte_timer = self._call_later(line_time_s + FIRST_BYTE_DEADLINE_S, lambda: self._first_byte_deadline_expired(end_attempt))
            if self._first_byte_timer is not None:
                self._end_attempt = end_attempt
        return frame

    def handleFrame(self, data: bytes, exp_devid: int, exp_tid: int) -> tuple[int, ModbusPDU | None]:  # noqa: N802 - pymodbus API name
        """Return `(bytes consumed, pdu)` for the answer to the pending request found anywhere in `data`.

        A complete valid frame consumes the whole buffer (one answer per request, as the stock framer).
        Without one, only junk in front of the first possible frame start is consumed; a possible start
        is kept so the rest of the frame can still arrive. Returns `(n, None)` when no frame is ready.
        """
        if data:
            self._note_bytes_arrived()
        first_candidate: int | None = None
        for offset in range(len(data)):
            size = self._candidate_frame_size(data, offset, exp_devid)
            if size is None:
                continue
            if size == 0 or len(data) - offset < size:
                if first_candidate is None:
                    first_candidate = offset
                continue
            pdu = self._decode_frame(data[offset : offset + size])
            if pdu is None:
                continue
            return self._accept_frame(data, offset, size, pdu)

        if first_candidate is not None:
            used_len = first_candidate
        elif exp_devid and data[-1:] == bytes([exp_devid]):
            # The FT232R delivers 1-2 bytes per read event: a trailing device id may be the start of a
            # frame whose function code has not arrived yet.
            used_len = len(data) - 1
        else:
            used_len = len(data)
        self._skip_junk(data[:used_len])
        self._arm_silence_timer()
        return used_len, None

    def _candidate_frame_size(self, data: bytes, offset: int, exp_devid: int) -> int | None:
        """Frame size if a frame for the pending request could start at `offset`, 0 if not yet known, None if not."""
        if len(data) - offset < _MIN_CANDIDATE_BYTES:
            return None
        if exp_devid and data[offset] != exp_devid:
            return None
        function_code = data[offset + 1]
        pending = self._request_function_code
        if pending is not None and function_code not in (pending, pending | _EXCEPTION_RESPONSE_FLAG):
            return None
        try:
            if not (pdu_class := self.decoder.lookupPduClass(data[offset:])):
                return None
            return pdu_class.calculateRtuFrameSize(data[offset:])
        except IndexError:  # function codes with a sub-function: it has not arrived yet
            return 0

    def _decode_frame(self, frame: bytes) -> ModbusPDU | None:
        """Decode `frame` (device id .. CRC) if its CRC matches, else None."""
        received_crc = int.from_bytes(frame[-_CRC_BYTES:], "big")
        if not self.check_CRC(frame[:-_CRC_BYTES], received_crc):
            return None
        pdu = self.decoder.decode(frame[1:-_CRC_BYTES])
        if pdu is not None:
            pdu.dev_id = frame[0]
            pdu.transaction_id = 0
        return pdu

    def _accept_frame(self, data: bytes, offset: int, size: int, pdu: ModbusPDU) -> tuple[int, ModbusPDU]:
        """Account for the decoded answer occupying `data[offset : offset + size]`; the whole buffer is consumed."""
        self._cancel_timers()
        self._end_attempt = None
        self._skip_junk(data[:offset])
        if self._junk_bytes_this_exchange:
            self.frames_rescued += 1
            _LOGGER.debug("Rescued a valid answer from device %s after %d junk byte(s)", pdu.dev_id, self._junk_bytes_this_exchange)
        self._skip_junk(data[offset + size :])
        return len(data), pdu

    def _note_bytes_arrived(self) -> None:
        """Bytes arrived: the line is busy, so the first-byte deadline is over; measure the first byte once per attempt."""
        if self._first_byte_timer is not None:
            self._first_byte_timer.cancel()
            self._first_byte_timer = None
        if self._attempt_has_bytes or self._request_end_s is None:
            return
        self._attempt_has_bytes = True
        self.first_byte_latency_last_ms = max(0.0, (self._clock() - self._request_end_s) * _MS_PER_S)
        self.first_byte_latency_max_ms = max(self.first_byte_latency_max_ms or 0.0, self.first_byte_latency_last_ms)

    def _arm_silence_timer(self) -> None:
        """Bytes arrived without a valid answer: end the attempt once the line has been silent for `silence_s`."""
        end_attempt = self._end_attempt
        if end_attempt is None or self._early_end is None or not self._attempt_has_bytes:
            return
        if self._silence_timer is not None:
            self._silence_timer.cancel()
        self._silence_timer = self._call_later(self._early_end.silence_s, lambda: self._silence_expired(end_attempt))

    def _first_byte_deadline_expired(self, end_attempt: Callable[[], None]) -> None:
        """No byte came in time: end the attempt, unless it is not the current one any more."""
        if end_attempt is not self._end_attempt:
            return
        self.attempts_no_answer += 1
        _LOGGER.debug("No answer byte within %.0f ms of the request end, ending the attempt", FIRST_BYTE_DEADLINE_S * _MS_PER_S)
        self._finish_attempt(end_attempt)

    def _silence_expired(self, end_attempt: Callable[[], None]) -> None:
        """The line went silent without a valid answer: end the attempt, unless it is not the current one any more."""
        if end_attempt is not self._end_attempt:
            return
        self.attempts_bad_answer += 1
        _LOGGER.debug("Line silent for %.0f ms without a valid answer, ending the attempt", self._early_end.silence_s * _MS_PER_S)
        self._finish_attempt(end_attempt)

    def _finish_attempt(self, end_attempt: Callable[[], None]) -> None:
        """End the attempt through the hook; bytes that still trickle in belong to no attempt."""
        self._end_attempt = None
        self._cancel_timers()
        end_attempt()

    def _cancel_timers(self) -> None:
        """Cancel both timers of the current attempt."""
        for timer in (self._first_byte_timer, self._silence_timer):
            if timer is not None:
                timer.cancel()
        self._first_byte_timer = self._silence_timer = None

    def _skip_junk(self, junk: bytes) -> None:
        """Count and debug-log bytes that are not part of an answer."""
        if not junk:
            return
        self.junk_bytes_skipped += len(junk)
        self._junk_bytes_this_exchange += len(junk)
        _LOGGER.debug("Skipped %d junk byte(s) on the serial line: %s", len(junk), junk.hex(" "))
