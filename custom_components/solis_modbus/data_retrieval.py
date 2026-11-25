import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers import sun
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus.helpers import (
    cache_get,
    cache_save,
    iter_controllers,
    mark_platform_entities_unavailable_for_base_sensors,
    notify_register_update,
)

from .const import CONN_TYPE_SERIAL, DOMAIN, MODBUS_ACKNOWLEDGE
from .data.enums import PollSpeed
from .modbus_controller import RECOVERABLE_REGISTER_READ_EXCEPTIONS, ModbusController
from .sensors.solis_base_sensor import SolisSensorGroup, cluster_sensors_by_contiguous_registers

_LOGGER = logging.getLogger(__name__)

_MAX_REGISTER_RECOVERY_DEPTH = 24

# Raise a repair issue once the reconnect loop has failed this many times
# (~the datalogger has been gone for a while, not a single blip).
_ISSUE_AFTER_FAILURES = 5

# With night suppression on, also treat this long before sunset / after sunrise
# as night: inverters drop off at dusk and wake well after the sun is up.
_NIGHT_GRACE = timedelta(hours=1)

# How long a serial inverter must go unanswered from startup before we check
# whether it answers at unit 1 instead of its configured slave ID.
_SLAVE_PROBE_AFTER = timedelta(minutes=1)

# Failed model-number probes on one connection before polling goes ahead without
# the blank image check (an inverter that rejects the register mustn't stall).
_MAX_INCONCLUSIVE_IMAGE_PROBES = 3

# Backoff after Modbus exception 5 (Solis: HMI/DSP communication failure, #584).
# Keeps polling off a waking/shutting-down inverter without blocking shared links,
# and stays below _stale_after_s() (>= 120 s) so the watchdog sees live replies.
_NOT_READY_BACKOFF_INITIAL_S = 15.0
_NOT_READY_BACKOFF_MAX_S = 60.0
_NOT_READY_WARN_AFTER_S = 600.0


class DataRetrieval:
    def __init__(
        self,
        hass: HomeAssistant,
        controller: ModbusController,
        entry_id: str | None = None,
        suppress_night_issue: bool = False,
    ):
        self._spike_counter = {}
        self.controller: ModbusController = controller
        self.hass = hass
        self._entry_id = entry_id
        # Fixed for this instance's lifetime: an options change reloads the entry.
        self._suppress_night_issue = suppress_night_issue
        # None = unknown (an issue may survive from before a restart), so the first
        # night-time pass still clears it; afterwards we skip redundant deletes.
        self._issue_raised: bool | None = None
        # Set once the slave ID check is settled (see _check_serial_slave_id).
        self._slave_id_checked = False
        # Set once its issue is raised: stop probing, but keep checking whether to clear it.
        self._slave_id_issue_raised = False
        self._polling_since: float | None = None
        # Blank register image guard (issue #540): the connection_count the image
        # was last found real on, and when the current blank image was first seen.
        self._image_checked_on: int | None = None
        self._blank_since: float | None = None
        self._inconclusive_image_probes = 0
        # Modbus exception 5 (Solis: HMI/DSP communication failure, issue #584):
        # per-controller non-blocking backoff so startup/shutdown doesn't hammer the inverter.
        self._not_ready_until: float | None = None
        self._not_ready_since: float | None = None
        self._last_not_ready: float | None = None
        self._not_ready_delay: float = _NOT_READY_BACKOFF_INITIAL_S
        self._not_ready_warned: bool = False
        self._not_ready_last_success: datetime | None = None
        self._not_ready_connection: int | None = None
        self._not_ready_issue_raised: bool | None = None
        self.poll_lock = asyncio.Lock()
        # Incremented per poll batch; sent with each value so derived sensors can pair
        # registers from different groups that were read in the same batch.
        self._poll_id = 0
        self.connection_check = False
        self.first_poll = True
        self.poll_updating = {
            PollSpeed.FAST: {},
            PollSpeed.NORMAL: {},
            PollSpeed.SLOW: {},
            PollSpeed.STARTUP: {},
        }

        self._unsub_listeners = []
        self._startup_unsub = None  # Store startup listener separately
        self._write_task = None  # process_write_queue task, cancelled on unload
        self._poll_task = None  # poll_controller task, cancelled on unload
        self._reconnect_task = None  # check_connection started by a poll, cancelled on unload
        self._stopping = False  # set on async_stop so in-flight reconnect loops exit

        if self.hass.is_running:
            self._poll_task = self.hass.async_create_task(self.poll_controller())
        else:
            # Store the unsub function separately so we can manage its lifecycle
            self._startup_unsub = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.poll_controller)

    def _can_poll(self) -> bool:
        """True while a poll batch may keep reading."""
        return not self._stopping and self.controller.enabled and self.controller.connected()

    def _request_reconnect(self) -> None:
        """Start check_connection now instead of waiting for the next watchdog tick.

        A failed read closes the link and poll batches never reconnect (#527), so
        without this the link, and with it the queued writes, stayed down until the
        2-minute watchdog ran (issue #556). check_connection stays the only place
        that connects, and its guard keeps it to one connection at a time.
        """
        if self._stopping or not self.controller.enabled or self.controller.connected() or self.connection_check:
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        self._reconnect_task = self.hass.async_create_background_task(
            self.check_connection(),
            f"{DOMAIN} reconnect {self.controller.host}.{self.controller.slave}",
        )

    async def _read_register_block_with_exception(self, start_register: int, count: int, is_holding: bool) -> tuple[list[int] | None, int | None]:
        # The controller's read wrappers reconnect; only check_connection may.
        if not self._can_poll():
            return None, None
        if is_holding:
            return await self.controller.async_read_holding_registers_with_exception(start_register, count)
        return await self.controller.async_read_input_registers_with_exception(start_register, count)

    def _note_inverter_not_ready(self) -> None:
        """Pause polling this inverter after Modbus exception 5 (Solis: HMI/DSP comm failure, #584)."""
        now = time.monotonic()
        # A long gap since the last exception 5 (e.g. unrelated errors in between) starts a fresh episode.
        if self._last_not_ready is not None and (now - self._last_not_ready) > self._stale_after_s():
            self._clear_inverter_not_ready(recovered=False)
        delay = self._not_ready_delay
        self._not_ready_until = now + delay
        self._last_not_ready = now
        self._not_ready_delay = min(delay * 2, _NOT_READY_BACKOFF_MAX_S)
        last = getattr(self.controller, "last_modbus_success", None)
        self._not_ready_last_success = last if isinstance(last, datetime) else None
        conn = getattr(self.controller, "connection_count", None)
        self._not_ready_connection = conn if isinstance(conn, int) and not isinstance(conn, bool) else None
        if self._not_ready_since is None:
            self._not_ready_since = now
            self._not_ready_warned = False
            _LOGGER.info(
                "(%s.%s) Inverter not ready (Modbus exception 5: HMI/DSP communication failure); pausing polls for %.0f s.",
                self.controller.host,
                self.controller.slave,
                delay,
            )
            return
        elapsed = now - self._not_ready_since
        if elapsed >= _NOT_READY_WARN_AFTER_S:
            self._update_not_ready_issue(True)
            if not self._not_ready_warned and not self._expected_offline_at_night():
                self._not_ready_warned = True
                _LOGGER.warning(
                    "(%s.%s) Inverter still not ready after %.0f s (Modbus exception 5: HMI/DSP communication failure).",
                    self.controller.host,
                    self.controller.slave,
                    elapsed,
                )
                return
        _LOGGER.debug(
            "(%s.%s) Inverter still not ready (Modbus exception 5); pausing polls for %.0f s.",
            self.controller.host,
            self.controller.slave,
            delay,
        )

    def _clear_inverter_not_ready(self, *, recovered: bool = True) -> None:
        """Reset exception-5 backoff once the inverter answers again (or the link fails differently)."""
        if self._not_ready_since is not None and recovered:
            elapsed = time.monotonic() - self._not_ready_since
            log_fn = _LOGGER.warning if self._not_ready_warned else _LOGGER.info
            log_fn(
                "(%s.%s) Inverter ready again after %.0f s of Modbus exception 5; resuming normal polling.",
                self.controller.host,
                self.controller.slave,
                elapsed,
            )
        self._not_ready_until = None
        self._not_ready_since = None
        self._last_not_ready = None
        self._not_ready_delay = _NOT_READY_BACKOFF_INITIAL_S
        self._not_ready_warned = False
        self._not_ready_last_success = None
        self._not_ready_connection = None
        self._update_not_ready_issue(False)

    def _reset_not_ready_pause(self) -> None:
        """Clear the poll-pause window without ending an ongoing exception-5 episode.

        A single lost frame or transient reconnect shouldn't reset the 10-minute
        escalation clock or flap the repair issue; if exception 5 really stopped,
        the stale-gap rule and watchdog will end the episode.
        """
        self._not_ready_until = None
        self._not_ready_delay = _NOT_READY_BACKOFF_INITIAL_S

    def _is_backed_off(self) -> bool:
        """Pure check: True while the exception-5 pause deadline has not expired."""
        return self._not_ready_until is not None and time.monotonic() < self._not_ready_until

    def _poll_paused_for_not_ready(self) -> bool:
        """Check whether this poll tick should skip due to exception-5 backoff.

        Clears the pause early if the link reconnected or another read
        (e.g. a service call) succeeded in the meantime.
        """
        if self._not_ready_until is None:
            return False
        conn = getattr(self.controller, "connection_count", None)
        if self._not_ready_connection is not None and isinstance(conn, int) and not isinstance(conn, bool) and conn != self._not_ready_connection:
            self._reset_not_ready_pause()
            return False
        last = getattr(self.controller, "last_modbus_success", None)
        if isinstance(last, datetime) and self._not_ready_last_success is not None and last > self._not_ready_last_success:
            self._clear_inverter_not_ready(recovered=True)
            return False
        return self._is_backed_off()

    def _inverter_not_ready_recently(self) -> bool:
        """True when the inverter recently replied with Modbus exception 5 (HMI/DSP not ready).

        The link itself is alive (the HMI is replying to Modbus frames), so the stale-link
        watchdog must not treat it as a half-open socket and tear it down.
        """
        if self._last_not_ready is None:
            return False
        conn = getattr(self.controller, "connection_count", None)
        if self._not_ready_connection is not None and isinstance(conn, int) and not isinstance(conn, bool) and conn != self._not_ready_connection:
            return False
        return (time.monotonic() - self._last_not_ready) <= self._stale_after_s()

    async def _probe_register_block_quiet(self, start_register: int, count: int, is_holding: bool) -> tuple[bool, list[int] | None, int | None]:
        if count <= 0:
            return True, [], None
        if is_holding:
            vals, err = await self.controller._async_read_holding_register_raw_detailed(start_register, count, quiet=True)
        else:
            vals, err = await self.controller._async_read_input_register_raw_detailed(start_register, count, quiet=True)
        if vals is None or len(vals) != count:
            return False, None, err
        return True, vals, None

    async def _async_isolate_one_bad_register(self, start: int, count: int, is_holding: bool) -> int | None:
        if count <= 0:
            return None
        if count == 1:
            return start
        mid = count // 2
        if mid < 1:
            mid = 1
        left_ok, _, left_exc = await self._probe_register_block_quiet(start, mid, is_holding)
        if left_exc == MODBUS_ACKNOWLEDGE:
            self._note_inverter_not_ready()
            return None
        if not left_ok:
            return await self._async_isolate_one_bad_register(start, mid, is_holding)
        right_ok, _, right_exc = await self._probe_register_block_quiet(start + mid, count - mid, is_holding)
        if right_exc == MODBUS_ACKNOWLEDGE:
            self._note_inverter_not_ready()
            return None
        if not right_ok:
            return await self._async_isolate_one_bad_register(start + mid, count - mid, is_holding)
        for off in range(count):
            ok_one, _, exc_one = await self._probe_register_block_quiet(start + off, 1, is_holding)
            if exc_one == MODBUS_ACKNOWLEDGE:
                self._note_inverter_not_ready()
                return None
            if not ok_one:
                return start + off
        return None

    async def _image_is_blank(self) -> bool | None:
        """Whether the datalogger answers from a blank register image (issue #540).

        A WiFi datalogger that has just rebooted can answer every read with zeros
        for minutes before it relays the inverter again. Those aren't readings:
        a lifetime energy counter at 0 is recorded as a meter reset. The model
        number tells them apart: it is never 0 on a real inverter, unlike the
        clock, which reads 0 on an inverter whose RTC lost power. A failed probe
        proves nothing: during a blank image it stays blank, otherwise the
        result is None (unknown).
        """
        ok, vals, exc = await self._probe_register_block_quiet(self.controller.inverter_config.identity_register, 1, False)
        if exc == MODBUS_ACKNOWLEDGE:
            # HMI is awake but DSP is not ready yet (#584): back off without
            # counting this against the blank-image probe limit.
            self._inconclusive_image_probes = 0
            self._note_inverter_not_ready()
            return True if self._blank_since is not None else None
        if not ok:
            if self._not_ready_until is not None and (not self._can_poll() or self.controller.last_read_unanswered is True):
                self._reset_not_ready_pause()
            if self._blank_since is not None:
                return True
            self._inconclusive_image_probes += 1
            return None
        self._inconclusive_image_probes = 0
        if self._not_ready_since is not None:
            self._clear_inverter_not_ready(recovered=True)
        if vals == [0]:
            if self._blank_since is None:
                self._blank_since = time.monotonic()
                _LOGGER.warning(
                    "(%s.%s) The datalogger answers with a blank register image (model number 0); "
                    "keeping the last readings until it relays the inverter again.",
                    self.controller.host,
                    self.controller.slave,
                )
            return True
        if self._blank_since is not None:
            _LOGGER.warning(
                "(%s.%s) The datalogger relays the inverter again after %.0f s of a blank register image; readings resume.",
                self.controller.host,
                self.controller.slave,
                time.monotonic() - self._blank_since,
            )
            self._blank_since = None
        return False

    def _apply_register_read_to_cache(self, sensor_group: SolisSensorGroup, values: list[int], marked_for_removal: list, poll_id: int | None = None) -> None:
        start_register = sensor_group.start_register
        for i, value in enumerate(values):
            reg = start_register + i
            _LOGGER.debug("block %s, register %s has value %s", start_register, reg, value)
            corrected_value = self.spike_filtering(reg, value)
            cache_save(self.hass, self.controller, reg, corrected_value)
            notify_register_update(self.hass, self.controller, reg, corrected_value, poll_id)

        if sensor_group.poll_speed == PollSpeed.ONCE:
            marked_for_removal.append(sensor_group)

        self.controller._data_received = True

    async def _recover_sensor_group_after_modbus_failure(
        self,
        sensor_group: SolisSensorGroup,
        start_register: int,
        count: int,
        is_holding: bool,
        marked_for_removal: list,
        *,
        _depth: int = 0,
    ) -> list[tuple[SolisSensorGroup, list[int]]] | None:
        """Bisect to find a bad register, disable affected sensors, split the group, and read replacement blocks."""
        if _depth > _MAX_REGISTER_RECOVERY_DEPTH:
            _LOGGER.warning(
                "(%s.%s) Register recovery aborted: exceeded max depth for block starting at %s",
                self.controller.host,
                self.controller.slave,
                start_register,
            )
            return None

        bad = await self._async_isolate_one_bad_register(start_register, count, is_holding)
        if bad is None:
            _LOGGER.debug(
                "(%s.%s) Could not isolate a single bad register in %s-%s",
                self.controller.host,
                self.controller.slave,
                start_register,
                start_register + count - 1,
            )
            return None

        disabled_sensors = [s for s in sensor_group.sensors if bad in s.registrars]
        for s in disabled_sensors:
            s.enabled = False
        mark_platform_entities_unavailable_for_base_sensors(self.hass, disabled_sensors)

        remaining = [s for s in sensor_group.sensors if bad not in s.registrars]
        clusters = cluster_sensors_by_contiguous_registers(remaining)
        new_groups = [SolisSensorGroup.from_sensors(c, sensor_group.poll_speed, sensor_group.identification) for c in clusters]

        self.controller.replace_sensor_group(sensor_group, new_groups)

        disabled_names = ", ".join(s.name for s in disabled_sensors) or "(unknown)"
        _LOGGER.warning(
            "(%s.%s) Adapted Modbus block %s-%s: bad register %s; disabled: %s; split into %d group(s).",
            self.controller.host,
            self.controller.slave,
            start_register,
            start_register + count - 1,
            bad,
            disabled_names,
            len(new_groups),
        )

        results: list[tuple[SolisSensorGroup, list[int]]] = []
        for g in new_groups:
            vals, exc = await self._read_register_block_with_exception(g.start_register, g.registrar_count, is_holding)
            if vals is not None and len(vals) == g.registrar_count:
                results.append((g, vals))
            elif exc == MODBUS_ACKNOWLEDGE:
                self._note_inverter_not_ready()
                break
            elif exc in RECOVERABLE_REGISTER_READ_EXCEPTIONS:
                nested = await self._recover_sensor_group_after_modbus_failure(
                    g, g.start_register, g.registrar_count, is_holding, marked_for_removal, _depth=_depth + 1
                )
                if nested:
                    results.extend(nested)
                if self._is_backed_off():
                    break
        return results if results else None

    async def async_stop(self):
        """Cancel all listeners and background tasks."""
        # Signal any in-flight reconnect loop to exit (it may be mid-backoff while
        # the datalogger is offline — otherwise it keeps spinning after unload).
        self._stopping = True
        self._update_connection_issue(False)
        self._update_not_ready_issue(False)
        if self._entry_id is not None:
            # A reload re-raises it if it still applies.
            ir.async_delete_issue(self.hass, DOMAIN, f"serial_slave_id_{self._entry_id}")

        # Clean up the startup listener only if it hasn't fired yet
        if self._startup_unsub:
            self._startup_unsub()
            self._startup_unsub = None

        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners = []
        self.connection_check = False  # Stop connection loop logic if any

        # Cancel the background tasks so they don't leak on reload. Cancel _poll_task
        # FIRST: poll_controller() creates _write_task as its last step, so stopping
        # poll first prevents it spawning a fresh write task after we've cancelled the
        # old one. getattr re-reads _write_task afterwards, catching any it just created.
        for task_attr in ("_poll_task", "_write_task", "_reconnect_task"):
            task = getattr(self, task_attr)
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                setattr(self, task_attr, None)

    def _stale_after_s(self) -> float:
        """Seconds without a successful read after which the link counts as stale."""
        return max(120.0, float(max(self.controller.poll_speed.values())) * 3)

    def _link_is_stale(self) -> bool:
        """True when the link claims to be connected but reads have stopped succeeding."""
        last = self.controller.last_modbus_success
        if last is None:
            return False
        return (datetime.now(UTC) - last).total_seconds() > self._stale_after_s()

    def _link_answers_another_inverter(self) -> bool:
        """True when another inverter on this link replied within the stale window.

        Several inverters can share one serial port or RS485 gateway. When only this one has gone
        quiet (powered off at night, say) the link itself is fine, and closing it would cut the
        other inverters' requests (issue #581). A valid Modbus exception reply (such as exc 5
        during dawn startup) also proves the link is alive (#584).
        """
        connection_id = self.controller.connection_id
        stale_after = self._stale_after_s()
        now = datetime.now(UTC)
        mono_now = time.monotonic()
        for other in iter_controllers(self.hass):
            if other is self.controller or getattr(other, "connection_id", None) != connection_id:
                continue
            last_reply = getattr(other, "last_modbus_reply", None)
            if isinstance(last_reply, (int, float)) and not isinstance(last_reply, bool) and (mono_now - last_reply) <= stale_after:
                return True
            # has_answered: last_modbus_success starts at "now", so a controller that never answered
            # (just set up behind a dead link) would otherwise look alive for a whole window.
            last = other.last_modbus_success
            if other.has_answered and last is not None and (now - last).total_seconds() <= stale_after:
                return True
        return False

    def _force_close_if_still_stale(self) -> None:
        """Close the link unless it came back while waiting for the link lock.

        The wait can take seconds behind another inverter's request: that read may succeed, another
        entry's watchdog may already have reopened the link, or this entry may have been unloaded.
        """
        if self._stopping or not self.controller.connected():
            return
        if not self._link_is_stale() or self._inverter_not_ready_recently() or self._link_answers_another_inverter():
            # The link answered while we waited: drop the issue raised before the wait, as
            # nothing will reconnect (and clear it) on a link that stays open.
            self._update_connection_issue(False)
            return
        self.controller.force_close()

    def _expected_offline_at_night(self) -> bool:
        """True when the datalogger is expected to be offline because it's night.

        Solar inverters normally power off overnight, so a stale/absent Modbus
        link then is expected rather than a fault (issue #465). Opt-in via
        CONF_SUPPRESS_NIGHT_OFFLINE_ISSUE since not every setup is PV-only.

        "Night" is widened by _NIGHT_GRACE on both sides: inverters shut down
        before sunset and only wake once irradiance picks up well after sunrise.
        Computed from the HA home location, so the sun integration isn't needed.
        """
        if not self._suppress_night_issue:
            return False
        now = datetime.now(UTC)
        return not (sun.is_up(self.hass, now - _NIGHT_GRACE) and sun.is_up(self.hass, now + _NIGHT_GRACE))

    def _update_connection_issue(self, unreachable: bool) -> None:
        """Raise/clear the 'datalogger unreachable' repair issue for this entry."""
        if self._entry_id is None:
            return
        issue_id = f"datalogger_unreachable_{self._entry_id}"
        if unreachable:
            if self._expected_offline_at_night():
                # Also clears an issue raised before dusk, so it doesn't linger
                # all night just because suppression only started applying now.
                if self._issue_raised is not False:
                    ir.async_delete_issue(self.hass, DOMAIN, issue_id)
                    self._issue_raised = False
                return
            self._issue_raised = True
            last = self.controller.last_modbus_success
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="datalogger_unreachable",
                translation_placeholders={
                    "host": str(self.controller.host),
                    "last_success": last.isoformat(timespec="seconds") if last else "unknown",
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            self._issue_raised = False

    def _update_not_ready_issue(self, not_ready: bool) -> None:
        """Raise/clear the 'inverter not ready' repair issue for prolonged exception 5 (#584)."""
        if self._entry_id is None:
            return
        issue_id = f"inverter_not_ready_{self._entry_id}"
        if not_ready:
            if self._expected_offline_at_night():
                if self._not_ready_issue_raised is not False:
                    ir.async_delete_issue(self.hass, DOMAIN, issue_id)
                    self._not_ready_issue_raised = False
                return
            if self._not_ready_issue_raised is True:
                return
            self._not_ready_issue_raised = True
            last = self.controller.last_modbus_success
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="inverter_not_ready",
                translation_placeholders={
                    "host": str(self.controller.host),
                    "slave": str(self.controller.slave),
                    "last_success": last.isoformat(timespec="seconds") if isinstance(last, datetime) else "unknown",
                },
            )
        elif self._not_ready_issue_raised is not False:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            self._not_ready_issue_raised = False

    async def _check_serial_slave_id(self) -> None:
        """Raise a repair issue when a serial inverter only answers at unit 1.

        Serial requests used to go to unit 1 whatever slave ID was configured, so
        an entry with the wrong slave ID kept working. Now that requests go to the
        configured slave, such an entry gets no data. While the configured slave
        has never answered, see whether unit 1 does.
        """
        if self._slave_id_checked or self._entry_id is None:
            return
        controller = self.controller
        issue_id = f"serial_slave_id_{self._entry_id}"
        if controller.connection_type != CONN_TYPE_SERIAL or controller.device_id == 1 or controller.has_answered:
            # Also clears the issue once the entry is reconfigured or its slave answers.
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            self._slave_id_checked = True
            return
        if any(other is not controller and other.connection_id == controller.connection_id and other.device_id == 1 for other in iter_controllers(self.hass)):
            # Unit 1 is another inverter configured on this bus; an answer proves nothing.
            # Not settled: that entry may be removed later.
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            self._slave_id_issue_raised = False
            return
        if self._slave_id_issue_raised:
            return
        if self._polling_since is None or time.monotonic() - self._polling_since < _SLAVE_PROBE_AFTER.total_seconds():
            return
        if not await controller.async_unit_answers(1):
            # Nothing at unit 1 either (asleep, wiring, ...); check again next time.
            return
        self._slave_id_issue_raised = True
        _LOGGER.warning(
            "(%s.%s) No answer from slave ID %s, but a device answers at slave ID 1. If that is this inverter, reconfigure the entry with slave ID 1.",
            controller.host,
            controller.slave,
            controller.device_id,
        )
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="serial_slave_id",
            translation_placeholders={"port": str(controller.connection_id), "slave": str(controller.device_id)},
        )

    async def check_connection(self, now=None):
        """Ensure the Modbus controller is connected, retrying on failure.

        This method checks if the controller is connected and attempts to reconnect
        if it's not. It also emits the controller status to the event bus.

        Args:
            now (datetime, optional): Current time, provided by the scheduler. Defaults to None.

        Returns:
            None
        """
        if self.connection_check:
            return

        # Re-entrancy guard: must be released on every exit path, otherwise the
        # periodic watchdog (and startup poll) silently stops reconnecting after
        # the first "already connected" tick — leaving the integration offline
        # until a manual reload. Use try/finally so it is always reset.
        self.connection_check = True
        try:
            await self._check_serial_slave_id()

            # Emit controller status (dispatcher — not persisted to recorder)
            notify_register_update(self.hass, self.controller, 90005, self.controller.enabled)

            if self.controller.connected():
                if self.first_poll:
                    await self.modbus_update_all()
                    self.first_poll = False
                if not self._link_is_stale():
                    self._update_connection_issue(False)
                    if self._not_ready_since is None:
                        self._update_not_ready_issue(False)
                    return
                if self._inverter_not_ready_recently():
                    # The HMI is actively answering Modbus frames with exception 5 (DSP not ready):
                    # the link itself is up, so don't tear it down or raise datalogger_unreachable (#584).
                    self._update_connection_issue(False)
                    _LOGGER.debug(
                        "(%s.%s) No successful read since %s, but the inverter recently replied with Modbus exception 5 "
                        "(HMI/DSP not ready); leaving the link open.",
                        self.controller.host,
                        self.controller.slave,
                        self.controller.last_modbus_success,
                    )
                    return
                # Exception 5 replies stopped arriving (link went silent): end the episode and
                # don't leave a stale inverter_not_ready repair alongside datalogger_unreachable.
                if self._not_ready_since is not None or self._not_ready_issue_raised is not False:
                    self._clear_inverter_not_ready(recovered=False)
                if self._link_answers_another_inverter():
                    # The link is alive: another inverter on it still answers. Only this one is quiet,
                    # so no "datalogger unreachable" issue: before #581 the close and reconnect
                    # cleared it in the same tick.
                    self._update_connection_issue(False)
                    _LOGGER.debug(
                        f"({self.controller.host}.{self.controller.slave}) No successful read since {self.controller.last_modbus_success}, "
                        f"but another inverter on {self.controller.connection_id} still answers; leaving the shared link open."
                    )
                    return
                # The socket claims to be connected but reads have stopped
                # succeeding — a half-open TCP link (e.g. the WiFi datalogger
                # slept overnight and the stack never noticed, issue #411).
                # Force-close so the loop below establishes a fresh connection.
                _LOGGER.log(
                    logging.DEBUG if self._expected_offline_at_night() else logging.WARNING,
                    f"⚠️({self.controller.host}.{self.controller.slave}) Modbus link looks half-open: "
                    f"no successful read since {self.controller.last_modbus_success}; forcing a reconnect.",
                )
                self._update_connection_issue(True)
                # Under the link lock, so the close can't cut a request another inverter has in flight.
                lock = self.controller.poll_lock
                if lock:
                    async with lock:
                        self._force_close_if_still_stale()
                else:
                    self._force_close_if_still_stale()

            retry_delay = 0.5
            while not self.controller.connected() and not self._stopping:
                try:
                    if await self.controller.connect():
                        _LOGGER.info(f"✅({self.controller.host}.{self.controller.slave}) Modbus controller connected successfully.")
                        self._update_connection_issue(False)
                        break
                    _LOGGER.debug(f"⚠️({self.controller.host}.{self.controller.slave}) Modbus connection failed, retrying in {retry_delay:.2f} seconds...")
                except Exception as e:
                    # Expected every retry overnight when the inverter is off; don't spam the log.
                    _LOGGER.log(
                        logging.DEBUG if self._expected_offline_at_night() else logging.ERROR,
                        f"❌({self.controller.host}.{self.controller.slave}) Connection error : {e}",
                    )

                # Persistent failure (not a single blip) -> surface a repair issue
                if self.controller.connect_failures >= _ISSUE_AFTER_FAILURES:
                    self._clear_inverter_not_ready(recovered=False)
                    self._update_connection_issue(True)

                if self._stopping:
                    break
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)
        finally:
            self.connection_check = False

    async def poll_controller(self, event=None):
        """Poll the Modbus controller for data, retrying until success.

        This method sets up periodic polling of the Modbus controller at different
        intervals based on the poll speed configuration. It also starts the write
        queue processing.

        Args:
            event (Event, optional): The Home Assistant started event. Defaults to None.

        Returns:
            None
        """
        # If this was triggered by the event, the listener is dead.
        # Clear the reference so async_stop doesn't try to remove it again.
        if event is not None:
            self._startup_unsub = None

        self._polling_since = time.monotonic()
        await self.check_connection()

        # Start periodic polling
        self._unsub_listeners.append(async_track_time_interval(self.hass, self.check_connection, timedelta(minutes=2)))
        self._unsub_listeners.append(
            async_track_time_interval(self.hass, self.modbus_update_fast, timedelta(seconds=self.controller.poll_speed.get(PollSpeed.FAST, 5)))
        )
        self._unsub_listeners.append(
            async_track_time_interval(
                self.hass,
                self.modbus_update_normal,
                timedelta(seconds=self.controller.poll_speed.get(PollSpeed.NORMAL, 15)),
            )
        )
        self._unsub_listeners.append(
            async_track_time_interval(
                self.hass,
                self.modbus_update_slow,
                timedelta(seconds=self.controller.poll_speed.get(PollSpeed.SLOW, 30)),
            )
        )

        # A background task, not a tracked one: process_write_queue() never ends on
        # its own, and HA waits for tracked tasks at shutdown ("was still running
        # after final writes shutdown stage", issue #546). HA cancels background
        # tasks when it stops; async_stop still cancels this one on unload/reload.
        self._write_task = self.hass.async_create_background_task(
            self.controller.process_write_queue(),
            f"{DOMAIN} write queue {self.controller.host}.{self.controller.slave}",
        )

    async def modbus_update_all(self):
        """Updates all sensor groups regardless of their poll speed.

        This method calls the update methods for fast, normal, and slow poll speeds
        to ensure all sensor groups are updated.

        Returns:
            None
        """
        await self.modbus_update_fast()
        await self.modbus_update_normal()
        await self.modbus_update_slow()

    async def modbus_update_fast(self, now=None):
        """Updates sensor groups with fast poll speed.

        This method retrieves data for all sensor groups with a fast poll speed
        and emits the last successful Modbus operation timestamp to the event bus.

        Args:
            now (datetime, optional): Current time, provided by the scheduler. Defaults to None.

        Returns:
            None
        """
        await self.get_modbus_updates([g for g in self.controller.sensor_groups if g.poll_speed == PollSpeed.FAST], PollSpeed.FAST)
        notify_register_update(self.hass, self.controller, 90006, self.controller.last_modbus_success)

    async def modbus_update_slow(self, now=None):
        """Updates sensor groups with slow poll speed.

        This method retrieves data for all sensor groups with a slow poll speed.

        Args:
            now (datetime, optional): Current time, provided by the scheduler. Defaults to None.

        Returns:
            None
        """
        await self.get_modbus_updates([g for g in self.controller.sensor_groups if g.poll_speed == PollSpeed.SLOW], PollSpeed.SLOW)

    async def modbus_update_normal(self, now=None):
        """Updates sensor groups with normal poll speed.

        This method retrieves data for all sensor groups with a normal poll speed
        or a one-time poll speed.

        Args:
            now (datetime, optional): Current time, provided by the scheduler. Defaults to None.

        Returns:
            None
        """
        await self.get_modbus_updates(
            [g for g in self.controller.sensor_groups if g.poll_speed in (PollSpeed.NORMAL, PollSpeed.ONCE)],
            PollSpeed.NORMAL,
        )

    async def get_modbus_updates(self, groups: list[SolisSensorGroup], speed: PollSpeed):
        """Read registers from the Modbus controller, ensuring no concurrent runs.

        This method reads register values for the specified sensor groups and
        updates the cache with the retrieved values. It also emits events for
        each register value that is read.

        Args:
            groups (List[SolisSensorGroup]): The sensor groups to read data for.
            speed (PollSpeed): The poll speed category for these groups.

        Returns:
            None
        """
        if not self._can_poll():
            # Covers a link that dropped outside a batch (e.g. a failed write).
            if self._not_ready_until is not None and not self.controller.connected():
                self._reset_not_ready_pause()
            self._request_reconnect()
            return

        if self._poll_paused_for_not_ready():
            return

        group_hash = frozenset({group.start_register for group in groups})

        if group_hash in self.poll_updating[speed]:
            _LOGGER.debug(f"⚠️({self.controller.host}.{self.controller.slave}) Skipping {speed.name} update: A previous instance is still running")
            return

        self.poll_updating[speed][group_hash] = True

        try:
            async with self.poll_lock:
                # Re-check after acquiring poll_lock in case a concurrent batch just entered backoff.
                if self._poll_paused_for_not_ready():
                    return

                total_start_time = time.perf_counter()
                total_registrars, total_groups = 0, 0
                self._poll_id += 1
                poll_id = self._poll_id
                marked_for_removal = []

                # A fresh link may front a datalogger that has just rebooted.
                connection = self.controller.connection_count
                if self._image_checked_on != connection:
                    blank = await self._image_is_blank()
                    if blank is None and self._inconclusive_image_probes >= _MAX_INCONCLUSIVE_IMAGE_PROBES:
                        _LOGGER.debug(
                            "(%s.%s) Model number unreadable after %s tries; polling without the blank image check.",
                            self.controller.host,
                            self.controller.slave,
                            self._inconclusive_image_probes,
                        )
                        self._inconclusive_image_probes = 0
                    elif blank is not False:
                        if not self._can_poll():
                            self._request_reconnect()
                        return
                    self._image_checked_on = connection
                image_checked = False
                batch_succeeded = False
                batch_hit_not_ready = False

                for sensor_group in groups:
                    start_register = sensor_group.start_register
                    count = sensor_group.registrar_count
                    end_register = start_register + count - 1
                    total_registrars += count
                    total_groups += 1

                    _LOGGER.debug(f"Group {start_register} starting for ({self.controller.host}.{self.controller.slave})")

                    is_holding = start_register >= 40000
                    values, exc_code = await self._read_register_block_with_exception(start_register, count, is_holding)

                    if values is None:
                        if exc_code == MODBUS_ACKNOWLEDGE:
                            self._note_inverter_not_ready()
                            batch_hit_not_ready = True
                            break
                        if exc_code in RECOVERABLE_REGISTER_READ_EXCEPTIONS:
                            last_not_ready = self._last_not_ready
                            recovered = await self._recover_sensor_group_after_modbus_failure(
                                sensor_group, start_register, count, is_holding, marked_for_removal
                            )
                            if recovered:
                                if self._last_not_ready == last_not_ready:
                                    batch_succeeded = True
                                else:
                                    batch_hit_not_ready = True
                                for rg, block_values in recovered:
                                    self._apply_register_read_to_cache(rg, block_values, marked_for_removal, poll_id)
                            else:
                                _LOGGER.debug(
                                    f"⚠️ Received None for register {start_register} - {end_register}, "
                                    f"for ({self.controller.host}.{self.controller.slave}), skipping."
                                )
                            if self._is_backed_off():
                                batch_hit_not_ready = True
                                break
                        else:
                            _LOGGER.debug(
                                f"⚠️ Received None for register {start_register} - {end_register}, "
                                f"for ({self.controller.host}.{self.controller.slave}), skipping."
                            )
                        if not self._can_poll() or self.controller.last_read_unanswered is True:
                            # A failed read closes the link; on serial an unanswered read leaves
                            # the port open for the other inverters on it, so connected() alone
                            # wouldn't stop the batch. Reading the remaining groups would each
                            # fail again (issue #478); leave reconnection to check_connection,
                            # started now when the link is down (issue #556).
                            if self._not_ready_until is not None:
                                self._reset_not_ready_pause()
                            _LOGGER.debug(
                                f"⚠️ Link to ({self.controller.host}.{self.controller.slave}) down or stopping, skipping remaining {speed.name} groups."
                            )
                            self._request_reconnect()
                            break
                        continue
                    if len(values) != count:
                        _LOGGER.debug(
                            f"⚠️ Modbus read mismatch: Received {len(values)} values, expected {count} from ({self.controller.host}.{self.controller.slave}) "
                            f"for register {start_register} - {end_register}. Skipping because linking them is uncertain."
                        )
                        continue

                    if not image_checked and not any(values) and any(cache_get(self.hass, self.controller, start_register + i) for i in range(count)):
                        # A block that read non-zero before is all zeros now: real
                        # (PV at dusk) or a blank image. Check at most once a batch.
                        image_checked = True
                        if await self._image_is_blank() is not False:
                            # Blank or unknown: re-check before the next batch applies anything.
                            self._image_checked_on = None
                            if self._is_backed_off():
                                batch_hit_not_ready = True
                            break

                    batch_succeeded = True
                    self._apply_register_read_to_cache(sensor_group, values, marked_for_removal, poll_id)

                if batch_succeeded and not batch_hit_not_ready:
                    if self._not_ready_since is not None:
                        self._clear_inverter_not_ready(recovered=True)
                    elif self._not_ready_issue_raised is not False:
                        self._update_not_ready_issue(False)

                # Remove "ONCE" poll speed groups
                self.controller._sensor_groups = [g for g in self.controller.sensor_groups if g not in marked_for_removal]

                total_duration = time.perf_counter() - total_start_time
                _LOGGER.debug(f"✅ {speed.name} update completed in {total_duration:.4f}s")
        except Exception:
            _LOGGER.warning("(%s.%s) Unexpected error during %s poll", self.controller.host, self.controller.slave, speed.name, exc_info=True)
        finally:
            del self.poll_updating[speed][group_hash]  # ✅ Reset only this group set

    # https://github.com/Pho3niX90/solis_modbus/issues/138
    def spike_filtering(self, register: int, value: int):
        """Filter short-lived implausible readings for known noisy registers."""
        cached_value = cache_get(self.hass, self.controller, register)
        if register not in self._spike_counter:
            self._spike_counter[register] = 0

        # 33139 / 34278 Battery 1 / 2 SOC: readings stuck at hard edge can briefly spike.
        if register in (33139, 34278):
            if value not in (0, 100):
                self._spike_counter[register] = 0
                return value

            self._spike_counter[register] += 1
            if self._spike_counter[register] < 3:
                _LOGGER.debug(
                    f"Ignoring short spike value {value} for battery SOC sensor; "
                    f"retaining previous value {cached_value} (counter={self._spike_counter[register]})"
                )
                return cached_value if cached_value is not None else value

            _LOGGER.debug(f"Accepting persistent spike value {value} for battery SOC sensor after {self._spike_counter[register]} cycles")
            self._spike_counter[register] = 0
            return value

        # 33148 Backup load power (U16): parallel inverter setups can briefly
        # report wrap-around/sentinel-like values (for example 65526).
        if register == 33148:
            wattage = getattr(self.controller.inverter_config, "wattage_chosen", 0) or 0
            plausible_max = int(max(10000, wattage * 2))
            is_implausible = value >= 65000 or value > plausible_max

            if not is_implausible:
                self._spike_counter[register] = 0
                return value

            self._spike_counter[register] += 1
            if self._spike_counter[register] < 3:
                _LOGGER.debug(
                    f"Ignoring transient backup load outlier {value}W (max={plausible_max}W); "
                    f"retaining previous value {cached_value} (counter={self._spike_counter[register]})"
                )
                return cached_value if cached_value is not None else value

            _LOGGER.debug(f"Accepting persistent backup load outlier {value}W after {self._spike_counter[register]} cycles (max={plausible_max}W)")
            self._spike_counter[register] = 0
            return value

        return value
