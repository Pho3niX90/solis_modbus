"""Issue #584: Modbus exception code 5 handling (Solis: HMI/DSP communication failure).

During morning startup on PV-powered string inverters (e.g. Mini-3000-4G), the HMI
answers RS485 Modbus requests before the DSP is ready and replies with exception
code 5. The integration should abort the batch, back off polling for that inverter
without blocking shared links or disabling the blank-image guard, avoid ERROR log
spam, and not let the stale-link watchdog tear down an actively replying link.
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solis_modbus import async_setup
from custom_components.solis_modbus.const import CONN_TYPE_TCP, DOMAIN, MODBUS_ACKNOWLEDGE
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.data_retrieval import (
    _NOT_READY_BACKOFF_INITIAL_S,
    _NOT_READY_BACKOFF_MAX_S,
    _NOT_READY_WARN_AFTER_S,
    DataRetrieval,
)
from custom_components.solis_modbus.modbus_controller import ModbusController
from custom_components.solis_modbus.runtime import SolisRuntimeData
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup

MODEL = 0x00E5


def _group(start: int, count: int = 2, speed: PollSpeed = PollSpeed.FAST) -> SolisSensorGroup:
    group = MagicMock(spec=SolisSensorGroup)
    group.poll_speed = speed
    group.start_register = start
    group.registrar_count = count
    return group


def _mock_sensor(registrars: list[int], name: str, *, enabled: bool = True) -> MagicMock:
    sensor = MagicMock()
    sensor.registrars = registrars
    sensor.name = name
    sensor.enabled = enabled
    return sensor


class _Clock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def time_module(self) -> SimpleNamespace:
        """Module-scoped stand-in for `time` in data_retrieval without touching asyncio's global clock."""
        return SimpleNamespace(monotonic=self.monotonic, perf_counter=time.perf_counter)


class _Rig:
    def __init__(self, *, check_image: bool = False, suppress_night_issue: bool = False, entry_id: str | None = None):
        self.clock = _Clock()
        self.probe_result: tuple[list[int] | None, int | None] = ([MODEL], None)
        self.read_result: tuple[list[int] | None, int | None] = ([1, 2], None)
        self.probe_calls: list[int] = []
        self.read_calls: list[int] = []
        self.cache: dict[int, int] = {}

        controller = MagicMock()
        controller.host = "10.54.36.177"
        controller.slave = 1
        controller.device_id = 1
        controller.connection_id = "rtu_tcp:10.54.36.177:502"
        controller.enabled = True
        controller.connected = MagicMock(return_value=True)
        controller.connection_count = 1
        controller.last_read_unanswered = False
        controller.last_modbus_success = datetime.now(UTC)
        controller.last_modbus_reply = None
        controller.poll_speed = {PollSpeed.FAST: 10, PollSpeed.NORMAL: 15, PollSpeed.SLOW: 30}
        controller.inverter_config.identity_register = 2999
        controller.async_read_input_registers_with_exception = AsyncMock(side_effect=self._read)
        controller.async_read_holding_registers_with_exception = AsyncMock(side_effect=self._read)
        controller._async_read_input_register_raw_detailed = AsyncMock(side_effect=self._probe)
        self.controller = controller

        hass = MagicMock()
        hass.is_running = False
        hass.async_create_background_task = MagicMock(side_effect=lambda coro, name: coro.close())
        self.hass = hass

        self.fast_groups = [_group(2999, 2, PollSpeed.FAST), _group(3033, 2, PollSpeed.FAST)]
        self.normal_groups = [_group(3250, 2, PollSpeed.NORMAL)]
        self.slow_groups = [_group(3089, 1, PollSpeed.SLOW)]
        controller.sensor_groups = [*self.fast_groups, *self.normal_groups, *self.slow_groups]

        self.retrieval = DataRetrieval(hass, controller, entry_id=entry_id, suppress_night_issue=suppress_night_issue)
        self.retrieval.first_poll = False
        if not check_image:
            # Mark blank-image guard already checked for tests focused on group polling.
            self.retrieval._image_checked_on = controller.connection_count

    async def _probe(self, register: int, count: int, quiet: bool = False):
        self.probe_calls.append(register)
        return self.probe_result

    async def _read(self, start: int, count: int):
        self.read_calls.append(start)
        vals, exc = self.read_result
        if vals is not None:
            return list(vals[:count]) if len(vals) >= count else [vals[0]] * count, None
        return None, exc

    def _save(self, hass, controller, reg, value):
        self.cache[reg] = value

    def _get(self, hass, controller, reg):
        return self.cache.get(reg)

    async def poll_fast(self):
        with (
            patch("custom_components.solis_modbus.data_retrieval.time", self.clock.time_module()),
            patch("custom_components.solis_modbus.data_retrieval.cache_save", side_effect=self._save),
            patch("custom_components.solis_modbus.data_retrieval.cache_get", side_effect=self._get),
            patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
        ):
            await self.retrieval.modbus_update_fast()

    async def poll_normal(self):
        with (
            patch("custom_components.solis_modbus.data_retrieval.time", self.clock.time_module()),
            patch("custom_components.solis_modbus.data_retrieval.cache_save", side_effect=self._save),
            patch("custom_components.solis_modbus.data_retrieval.cache_get", side_effect=self._get),
            patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
        ):
            await self.retrieval.modbus_update_normal()

    async def poll_all(self):
        with (
            patch("custom_components.solis_modbus.data_retrieval.time", self.clock.time_module()),
            patch("custom_components.solis_modbus.data_retrieval.cache_save", side_effect=self._save),
            patch("custom_components.solis_modbus.data_retrieval.cache_get", side_effect=self._get),
            patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
        ):
            await self.retrieval.modbus_update_all()


async def test_exception_5_aborts_batch_and_backs_off_exponentially():
    rig = _Rig()
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)

    # First tick: reads only the first group, aborts the rest of the batch (no 3033), enters 15 s backoff.
    await rig.poll_fast()
    assert rig.read_calls == [2999]
    rig.controller.force_close.assert_not_called()

    # Ticks during the 15 s backoff (any speed) send no Modbus requests.
    rig.clock.advance(10.0)
    await rig.poll_fast()
    await rig.poll_normal()
    assert rig.read_calls == [2999]

    # Once 15 s elapses, one probe read is tried; another exc 5 steps backoff to 30 s.
    rig.clock.advance(5.0)
    await rig.poll_fast()
    assert rig.read_calls == [2999, 2999]

    rig.clock.advance(29.0)
    await rig.poll_fast()
    assert rig.read_calls == [2999, 2999]

    # After 30 s elapses, next exc 5 steps backoff to 60 s (cap).
    rig.clock.advance(1.0)
    await rig.poll_fast()
    assert rig.read_calls == [2999, 2999, 2999]

    rig.clock.advance(59.0)
    await rig.poll_fast()
    assert rig.read_calls == [2999, 2999, 2999]

    # After 60 s elapses, inverter answers normally -> full batch succeeds and backoff resets to 15 s.
    rig.clock.advance(1.0)
    rig.read_result = ([10, 20], None)
    await rig.poll_fast()
    assert rig.read_calls == [2999, 2999, 2999, 2999, 3033]
    assert rig.retrieval._not_ready_delay == _NOT_READY_BACKOFF_INITIAL_S
    assert rig.retrieval._not_ready_until is None


async def test_modbus_update_all_sends_one_read_on_exception_5():
    rig = _Rig()
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)

    await rig.poll_all()

    assert rig.read_calls == [2999]


async def test_concurrent_batches_do_not_double_poll_when_first_hits_exception_5():
    rig = _Rig()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_exc5(start: int, count: int):
        rig.read_calls.append(start)
        entered.set()
        await release.wait()
        return None, MODBUS_ACKNOWLEDGE

    rig.controller.async_read_input_registers_with_exception = AsyncMock(side_effect=slow_exc5)

    with (
        patch("custom_components.solis_modbus.data_retrieval.time", rig.clock.time_module()),
        patch("custom_components.solis_modbus.data_retrieval.cache_save"),
        patch("custom_components.solis_modbus.data_retrieval.cache_get", return_value=None),
        patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
    ):
        t_fast = asyncio.create_task(rig.retrieval.modbus_update_fast())
        await entered.wait()
        # Normal batch starts while fast is in flight and waits on poll_lock.
        t_normal = asyncio.create_task(rig.retrieval.modbus_update_normal())
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(t_fast, t_normal)

    assert rig.read_calls == [2999]


async def test_external_successful_read_clears_backoff_early():
    rig = _Rig()
    t0 = datetime.now(UTC)
    rig.controller.last_modbus_success = t0
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)

    await rig.poll_fast()
    assert rig.read_calls == [2999]

    # Another read on the controller (e.g. read_register service) succeeds 2 s later.
    rig.clock.advance(2.0)
    rig.controller.last_modbus_success = t0 + timedelta(seconds=2)
    rig.read_result = ([10, 20], None)

    await rig.poll_fast()
    assert rig.read_calls == [2999, 2999, 3033]
    assert rig.retrieval._not_ready_until is None


async def test_blank_image_probe_exception_5_backs_off_and_keeps_guard_armed():
    """Exception 5 on the identity register must neither count toward the 3-probe bypass nor fall through."""
    rig = _Rig(check_image=True)
    rig.probe_result = (None, MODBUS_ACKNOWLEDGE)
    rig.read_result = ([0, 0], None)

    # Even across 5 expired backoff windows (> _MAX_INCONCLUSIVE_IMAGE_PROBES),
    # the blank-image guard stays armed and no group reads are issued.
    for _ in range(5):
        await rig.poll_fast()
        rig.clock.advance(_NOT_READY_BACKOFF_MAX_S + 1.0)

    assert len(rig.probe_calls) == 5
    assert rig.read_calls == []
    assert rig.retrieval._image_checked_on is None
    assert rig.retrieval._inconclusive_image_probes == 0

    # If the datalogger then replies with a blank image (0), the guard is still active and blocks it.
    rig.probe_result = ([0], None)
    await rig.poll_fast()
    assert rig.read_calls == []
    assert rig.retrieval._not_ready_until is None  # no longer exc 5

    # Once a real model number comes back, normal polling resumes in the same batch.
    rig.probe_result = ([MODEL], None)
    rig.read_result = ([11, 22], None)
    await rig.poll_fast()
    assert rig.read_calls == [2999, 3033]
    assert rig.retrieval._image_checked_on == 1


async def test_mid_session_all_zero_block_hitting_exception_5_on_probe_backs_off():
    rig = _Rig()
    rig.read_result = ([10, 20], None)
    await rig.poll_fast()
    assert rig.cache == {2999: 10, 3000: 20, 3033: 10, 3034: 20}

    # Block drops to all zeros mid-session; identity probe returns exc 5.
    rig.read_calls.clear()
    rig.read_result = ([0, 0], None)
    rig.probe_result = (None, MODBUS_ACKNOWLEDGE)
    await rig.poll_fast()

    # Did not overwrite cached values with zeros, aborted before 3033, armed image check, entered backoff.
    assert rig.cache == {2999: 10, 3000: 20, 3033: 10, 3034: 20}
    assert rig.read_calls == [2999]
    assert rig.retrieval._image_checked_on is None
    assert rig.retrieval._not_ready_until is not None


async def test_exception_5_during_active_blank_image_keeps_blank_state():
    rig = _Rig(check_image=True)
    rig.probe_result = ([0], None)
    await rig.poll_fast()
    assert rig.retrieval._blank_since is not None

    rig.probe_result = (None, MODBUS_ACKNOWLEDGE)
    with patch("custom_components.solis_modbus.data_retrieval.time", rig.clock.time_module()):
        assert await rig.retrieval._image_is_blank() is True
    assert rig.retrieval._blank_since is not None
    assert rig.retrieval._not_ready_until is not None


async def test_probe_timeout_dropping_link_requests_reconnect():
    rig = _Rig(check_image=True)

    async def drop_on_probe(register: int, count: int, quiet: bool = False):
        rig.probe_calls.append(register)
        rig.controller.connected.return_value = False
        return None, None

    rig.controller._async_read_input_register_raw_detailed = AsyncMock(side_effect=drop_on_probe)
    await rig.poll_fast()

    assert rig.probe_calls == [2999]
    assert rig.read_calls == []
    rig.hass.async_create_background_task.assert_called_once()


async def test_exception_5_during_bisection_aborts_without_disabling_sensors():
    rig = _Rig()
    s1 = _mock_sensor([301], "s1")
    s2 = _mock_sensor([302], "s2")
    group = MagicMock(spec=SolisSensorGroup)
    group.sensors = [s1, s2]
    group.poll_speed = PollSpeed.FAST
    group.identification = "test"
    group.start_register = 301
    group.registrar_count = 2

    # Initial block read returns exc 2 (recoverable), but bisection probes hit exc 5.
    rig.controller.async_read_input_registers_with_exception = AsyncMock(return_value=(None, 2))
    rig.controller._async_read_input_register_raw_detailed = AsyncMock(return_value=(None, MODBUS_ACKNOWLEDGE))

    with (
        patch("custom_components.solis_modbus.data_retrieval.time", rig.clock.time_module()),
        patch("custom_components.solis_modbus.data_retrieval.mark_platform_entities_unavailable_for_base_sensors") as mark_unavail,
    ):
        await rig.retrieval.get_modbus_updates([group, _group(3033)], PollSpeed.FAST)

    assert s1.enabled is True
    assert s2.enabled is True
    mark_unavail.assert_not_called()
    rig.controller.replace_sensor_group.assert_not_called()
    assert rig.retrieval._not_ready_until is not None
    # Stopped before polling the next group (3033).
    assert rig.controller.async_read_input_registers_with_exception.await_count == 1


async def test_partial_recovery_followed_by_exception_5_keeps_backoff_and_stops_batch():
    """Exc 2 splits into [g1, g2]; g1 succeeds, g2 hits exc 5 -> apply g1, keep backoff, stop batch."""
    rig = _Rig()
    s_left = _mock_sensor([301], "left")
    s_bad = _mock_sensor([302], "bad")
    s_right = _mock_sensor([303], "right")
    group = MagicMock(spec=SolisSensorGroup)
    group.sensors = [s_left, s_bad, s_right]
    group.poll_speed = PollSpeed.FAST
    group.identification = "test"
    group.start_register = 301
    group.registrar_count = 3
    next_group = _group(3033, 1, PollSpeed.FAST)
    rig.controller._sensor_groups = [group, next_group]
    rig.controller.sensor_groups = rig.controller._sensor_groups
    rig.controller.replace_sensor_group = partial(ModbusController.replace_sensor_group, rig.controller)

    # Bisection isolates bad register 302.
    async def bisect_probe(start: int, count: int, quiet: bool = False):
        if 302 in range(start, start + count):
            return None, 2
        return [7] * count, None

    rig.controller._async_read_input_register_raw_detailed = AsyncMock(side_effect=bisect_probe)

    read_log: list[tuple[int, int]] = []

    async def block_read(start: int, count: int):
        read_log.append((start, count))
        if (start, count) == (301, 3):
            return None, 2
        if (start, count) == (301, 1):
            return [42], None
        if (start, count) == (303, 1):
            return None, MODBUS_ACKNOWLEDGE
        return [99] * count, None

    rig.controller.async_read_input_registers_with_exception = AsyncMock(side_effect=block_read)

    with (
        patch("custom_components.solis_modbus.data_retrieval.time", rig.clock.time_module()),
        patch("custom_components.solis_modbus.data_retrieval.cache_save", side_effect=rig._save),
        patch("custom_components.solis_modbus.data_retrieval.cache_get", side_effect=rig._get),
        patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
        patch("custom_components.solis_modbus.data_retrieval.mark_platform_entities_unavailable_for_base_sensors"),
    ):
        await rig.retrieval.get_modbus_updates([group, next_group], PollSpeed.FAST)

    # g1 (301) was applied, g2 (303) triggered exc 5 backoff, and 3033 was NOT polled.
    assert rig.cache == {301: 42}
    assert read_log == [(301, 3), (301, 1), (303, 1)]
    assert rig.retrieval._not_ready_until is not None
    assert rig.retrieval._not_ready_since is not None


async def test_watchdog_leaves_link_open_while_inverter_replies_exception_5():
    rig = _Rig()
    rig.controller.last_modbus_success = datetime.now(UTC) - timedelta(minutes=10)
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)
    rig.controller.connect = AsyncMock(return_value=True)

    await rig.poll_fast()

    with (
        patch("custom_components.solis_modbus.data_retrieval.time", rig.clock.time_module()),
        patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
        patch.object(rig.retrieval, "_update_connection_issue") as update_issue,
    ):
        await rig.retrieval.check_connection()

    rig.controller.force_close.assert_not_called()
    rig.controller.connect.assert_not_awaited()
    update_issue.assert_called_with(False)

    # Once exception 5 replies stop arriving for longer than _stale_after_s() (120 s),
    # the watchdog treats the link as stale again and force-closes.
    rig.clock.advance(130.0)
    rig.controller.connected = MagicMock(side_effect=lambda: not rig.controller.force_close.called)
    with (
        patch("custom_components.solis_modbus.data_retrieval.time", rig.clock.time_module()),
        patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
    ):
        await rig.retrieval.check_connection()

    rig.controller.force_close.assert_called_once()


async def test_force_close_skipped_if_exception_5_arrives_during_lock_wait():
    rig = _Rig()
    rig.controller.last_modbus_success = datetime.now(UTC) - timedelta(minutes=10)
    lock = asyncio.Lock()
    rig.controller.poll_lock = lock
    rig.controller.connected = MagicMock(return_value=True)

    await lock.acquire()
    with (
        patch("custom_components.solis_modbus.data_retrieval.time", rig.clock.time_module()),
        patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
        patch.object(rig.retrieval, "_update_connection_issue") as update_issue,
    ):
        check = asyncio.create_task(rig.retrieval.check_connection())
        await asyncio.sleep(0)
        # While check_connection waited on the link lock, an exc 5 reply arrived.
        rig.retrieval._note_inverter_not_ready()
        lock.release()
        await check

    rig.controller.force_close.assert_not_called()
    assert update_issue.call_args_list[-1].args == (False,)


async def test_sibling_watchdog_leaves_shared_link_open_when_other_inverter_replies_exception_5():
    """On a shared bus, inverter A replying exc 5 proves the link is alive so B's watchdog must not close it."""
    rig_b = _Rig()
    rig_b.controller.slave = 2
    rig_b.controller.device_id = 2
    rig_b.controller.last_modbus_success = datetime.now(UTC) - timedelta(minutes=10)
    rig_b.controller.connected = MagicMock(return_value=True)

    sibling_a = MagicMock()
    sibling_a.connection_id = rig_b.controller.connection_id
    sibling_a.has_answered = False
    sibling_a.last_modbus_success = datetime.now(UTC) - timedelta(minutes=10)
    sibling_a.last_modbus_reply = rig_b.clock.monotonic() - 10.0  # A just replied with exc 5

    with (
        patch("custom_components.solis_modbus.data_retrieval.time", rig_b.clock.time_module()),
        patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
        patch("custom_components.solis_modbus.data_retrieval.iter_controllers", return_value=[rig_b.controller, sibling_a]),
        patch.object(rig_b.retrieval, "_update_connection_issue") as update_issue,
    ):
        await rig_b.retrieval.check_connection()

    rig_b.controller.force_close.assert_not_called()
    update_issue.assert_called_once_with(False)


async def test_timeout_and_serial_unanswered_and_external_drop_reset_pause_without_losing_episode():
    # 1. TCP link drop mid-batch clears poll pause without resetting the ongoing episode or repair issue.
    rig = _Rig(entry_id="entry1")
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)
    with patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        mock_ir.IssueSeverity = ir.IssueSeverity
        await rig.poll_fast()
        for _ in range(11):
            rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
            await rig.poll_fast()
        mock_ir.async_create_issue.assert_called_once()
        episode_start = rig.retrieval._not_ready_since

        rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)

        async def drop_link(start: int, count: int):
            rig.controller.connected.return_value = False
            return None, None

        rig.controller.async_read_input_registers_with_exception = AsyncMock(side_effect=drop_link)
        await rig.poll_fast()
        assert rig.retrieval._not_ready_until is None
        assert rig.retrieval._not_ready_since == episode_start
        mock_ir.async_delete_issue.assert_not_called()

    # 2. Serial unanswered read (port stays open) resets pause so next tick retries, while keeping episode.
    rig_s = _Rig()
    rig_s.read_result = (None, MODBUS_ACKNOWLEDGE)
    await rig_s.poll_fast()
    episode_start_s = rig_s.retrieval._not_ready_since
    rig_s.clock.advance(_NOT_READY_BACKOFF_INITIAL_S)

    async def serial_unanswered(start: int, count: int):
        rig_s.controller.last_read_unanswered = True
        return None, None

    rig_s.controller.async_read_input_registers_with_exception = AsyncMock(side_effect=serial_unanswered)
    await rig_s.poll_fast()
    assert rig_s.retrieval._not_ready_until is None
    assert rig_s.retrieval._not_ready_since == episode_start_s

    # 3. Link drop outside a batch clears the poll pause; reconnect bumps connection_count so
    # the new socket polls immediately and is not shielded from the stale-link watchdog.
    rig_ext = _Rig()
    rig_ext.read_result = (None, MODBUS_ACKNOWLEDGE)
    await rig_ext.poll_fast()
    rig_ext.controller.connected.return_value = False
    await rig_ext.poll_fast()
    assert rig_ext.retrieval._not_ready_until is None

    rig_rc = _Rig()
    rig_rc.read_result = (None, MODBUS_ACKNOWLEDGE)
    await rig_rc.poll_fast()
    rig_rc.controller.connection_count = 2
    with patch("custom_components.solis_modbus.data_retrieval.time", rig_rc.clock.time_module()):
        assert rig_rc.retrieval._inverter_not_ready_recently() is False
    rig_rc.read_result = ([1, 2], None)
    rig_rc.retrieval._image_checked_on = 2
    await rig_rc.poll_fast()
    assert rig_rc.read_calls == [2999, 2999, 3033]
    assert rig_rc.retrieval._not_ready_until is None
    assert rig_rc.retrieval._not_ready_since is None


async def test_mixed_batch_success_then_exception_5_does_not_flap_episode(caplog):
    """If group 1 answers and group 2 returns exc 5, keep escalating the episode instead of flapping."""
    rig = _Rig()

    async def mixed_read(start: int, count: int):
        rig.read_calls.append(start)
        if start == 2999:
            return [11, 22][:count], None
        return None, MODBUS_ACKNOWLEDGE

    rig.controller.async_read_input_registers_with_exception = AsyncMock(side_effect=mixed_read)

    with caplog.at_level(logging.DEBUG, logger="custom_components.solis_modbus.data_retrieval"):
        await rig.poll_fast()
        episode_start = rig.retrieval._not_ready_since
        assert episode_start is not None

        rig.clock.advance(_NOT_READY_BACKOFF_INITIAL_S)
        await rig.poll_fast()

    assert rig.retrieval._not_ready_since == episode_start
    assert rig.retrieval._not_ready_delay == _NOT_READY_BACKOFF_INITIAL_S * 4
    assert not any("ready again" in r.message for r in caplog.records)


async def test_stale_not_ready_episode_resets_after_unrelated_failures(caplog):
    """Exc 5 followed hours later by another exc 5 (with unrelated failures in between) starts fresh."""
    rig = _Rig()
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)
    with caplog.at_level(logging.DEBUG, logger="custom_components.solis_modbus.data_retrieval"):
        await rig.poll_fast()
        assert rig.retrieval._not_ready_delay == _NOT_READY_BACKOFF_INITIAL_S * 2

        # Hours pass with non-timeout errors (e.g. exc 4) so nothing cleared _not_ready_since.
        rig.clock.advance(4 * 3600)
        rig.read_result = (None, 4)
        await rig.poll_fast()

        # A new exc 5 must be treated as a fresh episode (INFO, 15 s delay), not a 4-hour WARNING.
        caplog.clear()
        rig.read_result = (None, MODBUS_ACKNOWLEDGE)
        await rig.poll_fast()

    exc5_levels = [r.levelname for r in caplog.records if "exception 5" in r.message]
    assert exc5_levels == ["INFO"]
    assert rig.retrieval._not_ready_delay == _NOT_READY_BACKOFF_INITIAL_S * 2


async def test_logging_stays_quiet_during_startup_and_warns_if_prolonged(caplog):
    rig = _Rig()
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)

    with caplog.at_level(logging.DEBUG, logger="custom_components.solis_modbus.data_retrieval"):
        # Initial exc 5 logs INFO, not WARNING/ERROR.
        await rig.poll_fast()
        assert [r.levelname for r in caplog.records if "exception 5" in r.message] == ["INFO"]

        # Step continuously through backoff retries until past 10 minutes (daytime).
        elapsed = 0.0
        while elapsed < _NOT_READY_WARN_AFTER_S:
            step = _NOT_READY_BACKOFF_MAX_S
            rig.clock.advance(step)
            elapsed += step
            await rig.poll_fast()

        exc5_levels = [r.levelname for r in caplog.records if "exception 5" in r.message]
        assert exc5_levels[0] == "INFO"
        assert exc5_levels.count("WARNING") == 1
        assert all(level in ("INFO", "DEBUG", "WARNING") for level in exc5_levels)

        # Further retries stay at DEBUG (no repeated warning spam).
        rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
        await rig.poll_fast()
        assert [r.levelname for r in caplog.records if "exception 5" in r.message][-1] == "DEBUG"

        # Recovery logs once at WARNING (matching the escalation).
        rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
        rig.read_result = ([1, 2], None)
        await rig.poll_fast()
        assert [r.levelname for r in caplog.records if "exception 5" in r.message][-1] == "WARNING"


async def test_prolonged_warning_suppressed_at_night_and_fires_in_daytime(caplog):
    rig = _Rig(suppress_night_issue=True)
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)

    with (
        caplog.at_level(logging.DEBUG, logger="custom_components.solis_modbus.data_retrieval"),
        patch.object(rig.retrieval, "_expected_offline_at_night", return_value=True) as mock_night,
    ):
        await rig.poll_fast()
        elapsed = 0.0
        while elapsed < _NOT_READY_WARN_AFTER_S:
            rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
            elapsed += _NOT_READY_BACKOFF_MAX_S
            await rig.poll_fast()

        assert not any(r.levelname == "WARNING" for r in caplog.records)
        assert rig.retrieval._not_ready_warned is False

        # Sun rises: first daytime retry past 600 s fires the single WARNING.
        mock_night.return_value = False
        rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
        await rig.poll_fast()
        assert [r.levelname for r in caplog.records if r.levelname == "WARNING"] == ["WARNING"]
        assert rig.retrieval._not_ready_warned is True


async def test_controller_logs_exception_5_at_debug_and_tracks_last_reply(caplog):
    manager = MagicMock()
    manager.inter_frame_wait = AsyncMock()
    lock = MagicMock()
    lock.__aenter__ = AsyncMock(return_value=None)
    lock.__aexit__ = AsyncMock(return_value=None)
    manager.get_client_lock.return_value = lock

    client = MagicMock()
    client.connected = True
    manager.get_tcp_client.return_value = client

    with patch("custom_components.solis_modbus.modbus_controller.ModbusClientManager") as manager_class:
        manager_class.get_instance.return_value = manager
        controller = ModbusController(
            hass=MagicMock(),
            connection_type=CONN_TYPE_TCP,
            host="10.54.36.177",
            port=502,
            inverter_config=MagicMock(),
            device_id=1,
        )

    assert controller.last_modbus_reply is None
    exc5 = MagicMock(isError=MagicMock(return_value=True), exception_code=MODBUS_ACKNOWLEDGE)
    exc4 = MagicMock(isError=MagicMock(return_value=True), exception_code=4)
    exc10 = MagicMock(isError=MagicMock(return_value=True), exception_code=10)
    exc11 = MagicMock(isError=MagicMock(return_value=True), exception_code=11)

    with caplog.at_level(logging.DEBUG, logger="custom_components.solis_modbus.modbus_controller"):
        # Gateway-generated exception codes (10, 11) must NOT count as a live inverter reply.
        client.read_input_registers = AsyncMock(return_value=exc10)
        client.read_holding_registers = AsyncMock(return_value=exc11)
        assert await controller.async_read_input_registers_with_exception(2999, 1) == (None, 10)
        assert await controller.async_read_holding_registers_with_exception(43000, 1) == (None, 11)
        assert controller.last_modbus_reply is None
        caplog.clear()

        client.read_input_registers = AsyncMock(return_value=exc5)
        client.read_holding_registers = AsyncMock(return_value=exc5)
        assert await controller.async_read_input_registers_with_exception(2999, 1) == (None, 5)
        assert controller.last_modbus_reply is not None
        assert await controller.async_read_holding_registers_with_exception(43000, 1) == (None, 5)
        assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []

        client.read_input_registers = AsyncMock(return_value=exc4)
        client.read_holding_registers = AsyncMock(return_value=exc4)
        assert await controller.async_read_input_registers_with_exception(2999, 1) == (None, 4)
        assert await controller.async_read_holding_registers_with_exception(43000, 1) == (None, 4)
        assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 2


async def test_backoff_is_isolated_per_controller_on_shared_link():
    rig_a = _Rig()
    rig_b = _Rig()
    rig_b.controller.slave = 2
    rig_b.controller.device_id = 2
    shared_lock = asyncio.Lock()
    rig_a.controller.poll_lock = shared_lock
    rig_b.controller.poll_lock = shared_lock

    rig_a.read_result = (None, MODBUS_ACKNOWLEDGE)
    rig_b.read_result = ([10, 20], None)

    await rig_a.poll_fast()
    assert rig_a.read_calls == [2999]
    assert not shared_lock.locked()

    # Inverter B on the same bus continues polling unimpeded while A is backed off.
    await rig_b.poll_fast()
    assert rig_b.read_calls == [2999, 3033]


async def test_read_register_service_reports_exception_5_clearly(hass):
    controller = MagicMock()
    controller.host = "10.54.36.177"
    controller.device_id = 1
    controller.async_read_input_registers_with_exception = AsyncMock(return_value=(None, MODBUS_ACKNOWLEDGE))

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.runtime_data = SolisRuntimeData(controller=controller)

    await async_setup(hass, {})

    with pytest.raises(HomeAssistantError, match=r"Modbus exception 5"):
        await hass.services.async_call(
            DOMAIN,
            "solis_read_register",
            {"address": 2999, "count": 1, "register_type": "input"},
            blocking=True,
            return_response=True,
        )


async def test_prolonged_exception_5_raises_and_clears_repair_issue():
    rig = _Rig(entry_id="entry1")
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)
    issue_id = "inverter_not_ready_entry1"

    with patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        mock_ir.IssueSeverity = ir.IssueSeverity
        await rig.poll_fast()
        # Brief dawn-like episode (< 600 s) does not create a repair issue.
        for _ in range(5):
            rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
            await rig.poll_fast()
        mock_ir.async_create_issue.assert_not_called()

        # Crossing _NOT_READY_WARN_AFTER_S creates the repair issue once.
        elapsed = 5 * _NOT_READY_BACKOFF_MAX_S
        while elapsed <= _NOT_READY_WARN_AFTER_S + _NOT_READY_BACKOFF_MAX_S:
            rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
            elapsed += _NOT_READY_BACKOFF_MAX_S
            await rig.poll_fast()

        mock_ir.async_create_issue.assert_called_once()
        args, kwargs = mock_ir.async_create_issue.call_args
        assert args == (rig.hass, DOMAIN, issue_id)
        assert kwargs["is_fixable"] is False
        assert kwargs["severity"] == ir.IssueSeverity.WARNING
        assert kwargs["translation_key"] == "inverter_not_ready"
        assert kwargs["translation_placeholders"]["host"] == "10.54.36.177"
        assert kwargs["translation_placeholders"]["slave"] == "1"
        assert kwargs["translation_placeholders"]["last_success"] != "unknown"
        mock_ir.async_delete_issue.assert_not_called()

        # Once the inverter recovers, the repair issue is deleted (once).
        rig.read_result = ([11, 22], None)
        rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
        await rig.poll_fast()
        await rig.poll_fast()
        mock_ir.async_delete_issue.assert_called_once_with(rig.hass, DOMAIN, issue_id)


async def test_not_ready_repair_issue_respects_night_suppression_and_dusk_transition():
    rig = _Rig(entry_id="entry1", suppress_night_issue=True)
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)
    issue_id = "inverter_not_ready_entry1"

    with (
        patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir,
        patch.object(rig.retrieval, "_expected_offline_at_night", return_value=True) as mock_night,
    ):
        mock_ir.IssueSeverity = ir.IssueSeverity
        await rig.poll_fast()
        for _ in range(11):
            rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
            await rig.poll_fast()

        # Suppressed overnight; pre-restart stale issue deleted once.
        mock_ir.async_create_issue.assert_not_called()
        mock_ir.async_delete_issue.assert_called_once_with(rig.hass, DOMAIN, issue_id)

        # Daytime arrives: issue is created.
        mock_night.return_value = False
        rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
        await rig.poll_fast()
        mock_ir.async_create_issue.assert_called_once()

        # Dusk arrives while still in exception 5: daytime issue is cleared.
        mock_night.return_value = True
        rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
        await rig.poll_fast()
        rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
        await rig.poll_fast()
        assert mock_ir.async_delete_issue.call_count == 2


async def test_not_ready_repair_issue_cleared_on_stop_and_link_silence():
    issue_id = "inverter_not_ready_entry1"

    # 1. Cleared on async_stop (unload/reload).
    rig = _Rig(entry_id="entry1")
    rig.read_result = (None, MODBUS_ACKNOWLEDGE)
    with patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        mock_ir.IssueSeverity = ir.IssueSeverity
        await rig.poll_fast()
        for _ in range(11):
            rig.clock.advance(_NOT_READY_BACKOFF_MAX_S)
            await rig.poll_fast()
        mock_ir.async_create_issue.assert_called_once()

        await rig.retrieval.async_stop()
        mock_ir.async_delete_issue.assert_any_call(rig.hass, DOMAIN, issue_id)

    # 2. Cleared if exception 5 stops arriving and watchdog marks the link stale/unreachable.
    rig2 = _Rig(entry_id="entry1")
    rig2.controller.last_modbus_success = datetime.now(UTC) - timedelta(minutes=20)
    rig2.controller.connect = AsyncMock(return_value=True)
    rig2.read_result = (None, MODBUS_ACKNOWLEDGE)
    with (
        patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir,
        patch("custom_components.solis_modbus.data_retrieval.time", rig2.clock.time_module()),
        patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
    ):
        mock_ir.IssueSeverity = ir.IssueSeverity
        await rig2.poll_fast()
        for _ in range(11):
            rig2.clock.advance(_NOT_READY_BACKOFF_MAX_S)
            await rig2.poll_fast()
        mock_ir.async_create_issue.assert_called_once()

        # Inverter stops answering altogether; watchdog force-closes and clears inverter_not_ready.
        rig2.clock.advance(130.0)
        rig2.controller.connected = MagicMock(side_effect=lambda: not rig2.controller.force_close.called)
        await rig2.retrieval.check_connection()
        mock_ir.async_delete_issue.assert_any_call(rig2.hass, DOMAIN, issue_id)


async def test_first_healthy_poll_clears_pre_restart_not_ready_issue():
    rig = _Rig(entry_id="entry1")
    rig.read_result = ([11, 22], None)

    with patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        await rig.poll_fast()
        await rig.poll_fast()

    # Deleted once on first healthy poll (in case an issue persisted from before restart), not repeated.
    mock_ir.async_delete_issue.assert_called_once_with(rig.hass, DOMAIN, "inverter_not_ready_entry1")


def test_not_ready_issue_translations_present_in_all_languages():
    translations_dir = Path(__file__).resolve().parents[1] / "custom_components" / "solis_modbus" / "translations"
    files = sorted(translations_dir.glob("*.json"))
    assert len(files) >= 8
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        entry = data["issues"]["inverter_not_ready"]
        assert entry["title"]
        for placeholder in ("{host}", "{slave}", "{last_success}"):
            assert placeholder in entry["description"], f"Missing {placeholder} in {path.name}"
