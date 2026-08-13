import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus.helpers import (
    cache_get,
    cache_save,
    mark_platform_entities_unavailable_for_base_sensors,
    notify_register_update,
)

from .const import DOMAIN
from .data.enums import InverterFeature, InverterType, PollSpeed
from .modbus_controller import RECOVERABLE_REGISTER_READ_EXCEPTIONS, ModbusController
from .sensors.solis_base_sensor import SolisSensorGroup, cluster_sensors_by_contiguous_registers

_LOGGER = logging.getLogger(__name__)

_MAX_REGISTER_RECOVERY_DEPTH = 24

# Raise a repair issue once the reconnect loop has failed this many times
# (~the datalogger has been gone for a while, not a single blip).
_ISSUE_AFTER_FAILURES = 5

# String/grid EPM operating info (protocol §5.4, function 0x04). Holding settings
# start at 36500. Hybrid 360xx is a different "mapping" block — never treat it as EPM.
_EPM_OPERATING_MIN = 36000
_EPM_OPERATING_MAX = 36499
# V19 marks these as Reserve. Illegal-address on them alone is not proof the EPM
# is missing; a fitted EPM can still reject 36013-36014 while serving 36028/36050.
_EPM_RESERVED_REGISTERS = frozenset(range(36013, 36015)) | frozenset(range(36030, 36050))


def sensor_group_registers(group) -> set[int]:
    """Every register a sensor group currently covers."""
    regs: set[int] = set()
    for sensor in getattr(group, "sensors", []) or []:
        regs.update(getattr(sensor, "registrars", []) or [])
    return regs


def is_string_epm_operating_group(inverter_type, group) -> bool:
    """True for grid/string EPM 36xxx groups (not hybrid mapping registers)."""
    if inverter_type not in (InverterType.GRID, InverterType.STRING):
        return False
    regs = sensor_group_registers(group)
    return bool(regs) and all(_EPM_OPERATING_MIN <= r <= _EPM_OPERATING_MAX for r in regs)


def epm_group_is_absence_witness(group) -> bool:
    """True when a failed group contains implemented EPM registers, not only reserved ones."""
    return bool(sensor_group_registers(group) - _EPM_RESERVED_REGISTERS)


class DataRetrieval:
    def __init__(self, hass: HomeAssistant, controller: ModbusController, entry_id: str | None = None):
        self._spike_counter = {}
        self.controller: ModbusController = controller
        self.hass = hass
        self._entry_id = entry_id
        self.poll_lock = asyncio.Lock()
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
        self._stopping = False  # set on async_stop so in-flight reconnect loops exit
        self._epm_disabled = False
        self._epm_persist_pending = False
        self._epm_persist_started = False

        features = getattr(controller.inverter_config, "features", [])
        if entry_id and isinstance(features, (list, set, tuple, frozenset)) and InverterFeature.EPM in features:
            ir.async_delete_issue(hass, DOMAIN, f"epm_absent_{entry_id}")

        if self.hass.is_running:
            self._poll_task = self.hass.async_create_task(self.poll_controller())
        else:
            # Store the unsub function separately so we can manage its lifecycle
            self._startup_unsub = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.poll_controller)

    async def _read_register_block_with_exception(self, start_register: int, count: int, is_holding: bool) -> tuple[list[int] | None, int | None]:
        if is_holding:
            return await self.controller.async_read_holding_registers_with_exception(start_register, count)
        return await self.controller.async_read_input_registers_with_exception(start_register, count)

    async def _probe_register_block_quiet(self, start_register: int, count: int, is_holding: bool) -> tuple[bool, list[int] | None]:
        if count <= 0:
            return True, []
        if is_holding:
            vals, _err = await self.controller._async_read_holding_register_raw_detailed(start_register, count, quiet=True)
        else:
            vals, _err = await self.controller._async_read_input_register_raw_detailed(start_register, count, quiet=True)
        if vals is None or len(vals) != count:
            return False, None
        return True, vals

    async def _async_isolate_one_bad_register(self, start: int, count: int, is_holding: bool) -> int | None:
        if count <= 0:
            return None
        if count == 1:
            return start
        mid = count // 2
        if mid < 1:
            mid = 1
        left_ok, _ = await self._probe_register_block_quiet(start, mid, is_holding)
        if not left_ok:
            return await self._async_isolate_one_bad_register(start, mid, is_holding)
        right_ok, _ = await self._probe_register_block_quiet(start + mid, count - mid, is_holding)
        if not right_ok:
            return await self._async_isolate_one_bad_register(start + mid, count - mid, is_holding)
        for off in range(count):
            ok_one, _ = await self._probe_register_block_quiet(start + off, 1, is_holding)
            if not ok_one:
                return start + off
        return None

    def _apply_register_read_to_cache(self, sensor_group: SolisSensorGroup, values: list[int], marked_for_removal: list) -> None:
        start_register = sensor_group.start_register
        for i, value in enumerate(values):
            reg = start_register + i
            _LOGGER.debug("block %s, register %s has value %s", start_register, reg, value)
            corrected_value = self.spike_filtering(reg, value)
            cache_save(self.hass, self.controller, reg, corrected_value)
            notify_register_update(self.hass, self.controller, reg, corrected_value)

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
            elif exc in RECOVERABLE_REGISTER_READ_EXCEPTIONS:
                nested = await self._recover_sensor_group_after_modbus_failure(
                    g, g.start_register, g.registrar_count, is_holding, marked_for_removal, _depth=_depth + 1
                )
                if nested:
                    results.extend(nested)
        return results if results else None

    async def async_stop(self):
        """Cancel all listeners and background tasks."""
        # Signal any in-flight reconnect loop to exit (it may be mid-backoff while
        # the datalogger is offline — otherwise it keeps spinning after unload).
        self._stopping = True
        self._update_connection_issue(False)

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
        for task_attr in ("_poll_task", "_write_task"):
            task = getattr(self, task_attr)
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                setattr(self, task_attr, None)

    def _link_is_stale(self) -> bool:
        """True when the link claims to be connected but reads have stopped succeeding."""
        last = self.controller.last_modbus_success
        if last is None:
            return False
        stale_after = max(120.0, float(max(self.controller.poll_speed.values())) * 3)
        return (datetime.now(UTC) - last).total_seconds() > stale_after

    def _update_connection_issue(self, unreachable: bool) -> None:
        """Raise/clear the 'datalogger unreachable' repair issue for this entry."""
        if self._entry_id is None:
            return
        issue_id = f"datalogger_unreachable_{self._entry_id}"
        if unreachable:
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
            # Emit controller status (dispatcher — not persisted to recorder)
            notify_register_update(self.hass, self.controller, 90005, self.controller.enabled)

            if self.controller.connected():
                if self.first_poll:
                    await self.modbus_update_all()
                    self.first_poll = False
                if not self._link_is_stale():
                    self._update_connection_issue(False)
                    return
                # The socket claims to be connected but reads have stopped
                # succeeding — a half-open TCP link (e.g. the WiFi datalogger
                # slept overnight and the stack never noticed, issue #411).
                # Force-close so the loop below establishes a fresh connection.
                _LOGGER.warning(
                    f"⚠️({self.controller.host}.{self.controller.slave}) Modbus link looks half-open: "
                    f"no successful read since {self.controller.last_modbus_success}; forcing a reconnect."
                )
                self._update_connection_issue(True)
                self.controller.force_close()

            retry_delay = 0.5
            while not self.controller.connected() and not self._stopping:
                try:
                    if await self.controller.connect():
                        _LOGGER.info(f"✅({self.controller.host}.{self.controller.slave}) Modbus controller connected successfully.")
                        self._update_connection_issue(False)
                        break
                    _LOGGER.debug(f"⚠️({self.controller.host}.{self.controller.slave}) Modbus connection failed, retrying in {retry_delay:.2f} seconds...")
                except Exception as e:
                    _LOGGER.error(f"❌({self.controller.host}.{self.controller.slave}) Connection error : {e}")

                # Persistent failure (not a single blip) -> surface a repair issue
                if self.controller.connect_failures >= _ISSUE_AFTER_FAILURES:
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

        self._write_task = self.hass.async_create_task(self.controller.process_write_queue())
        # First-poll EPM autodisable must persist *after* this setup task finishes,
        # otherwise reload deadlocks waiting for poll_controller (issue #466).
        self._start_persist_epm_disabled_if_needed()

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
        if not self.controller.enabled or not self.controller.connected():
            return

        group_hash = frozenset({group.start_register for group in groups})

        if group_hash in self.poll_updating[speed]:
            _LOGGER.debug(f"⚠️({self.controller.host}.{self.controller.slave}) Skipping {speed.name} update: A previous instance is still running")
            return

        self.poll_updating[speed][group_hash] = True

        try:
            async with self.poll_lock:
                total_start_time = time.perf_counter()
                total_registrars, total_groups = 0, 0
                marked_for_removal = []

                for sensor_group in groups:
                    if self._epm_disabled and is_string_epm_operating_group(self.controller.inverter_config.type, sensor_group):
                        continue
                    start_register = sensor_group.start_register
                    count = sensor_group.registrar_count
                    end_register = start_register + count - 1
                    total_registrars += count
                    total_groups += 1

                    _LOGGER.debug(f"Group {start_register} starting for ({self.controller.host}.{self.controller.slave})")

                    is_holding = start_register >= 40000
                    values, exc_code = await self._read_register_block_with_exception(start_register, count, is_holding)

                    if values is None:
                        if exc_code in RECOVERABLE_REGISTER_READ_EXCEPTIONS:
                            recovered = await self._recover_sensor_group_after_modbus_failure(
                                sensor_group, start_register, count, is_holding, marked_for_removal
                            )
                            if recovered:
                                for rg, block_values in recovered:
                                    self._apply_register_read_to_cache(rg, block_values, marked_for_removal)
                            elif self._should_autodisable_epm(sensor_group):
                                self._disable_epm_runtime(start_register)
                            else:
                                _LOGGER.debug(
                                    f"⚠️ Received None for register {start_register} - {end_register}, "
                                    f"for ({self.controller.host}.{self.controller.slave}), skipping."
                                )
                        else:
                            _LOGGER.debug(
                                f"⚠️ Received None for register {start_register} - {end_register}, "
                                f"for ({self.controller.host}.{self.controller.slave}), skipping."
                            )
                        continue
                    if len(values) != count:
                        _LOGGER.debug(
                            f"⚠️ Modbus read mismatch: Received {len(values)} values, expected {count} from ({self.controller.host}.{self.controller.slave}) "
                            f"for register {start_register} - {end_register}. Skipping because linking them is uncertain."
                        )
                        continue

                    self._apply_register_read_to_cache(sensor_group, values, marked_for_removal)

                # Remove "ONCE" poll speed groups
                self.controller._sensor_groups = [g for g in self.controller._sensor_groups if g not in marked_for_removal]

                total_duration = time.perf_counter() - total_start_time
                _LOGGER.debug(f"✅ {speed.name} update completed in {total_duration:.4f}s")
        except Exception:
            _LOGGER.warning("(%s.%s) Unexpected error during %s poll", self.controller.host, self.controller.slave, speed.name, exc_info=True)
        finally:
            del self.poll_updating[speed][group_hash]  # ✅ Reset only this group set
            if not self.connection_check:
                self._start_persist_epm_disabled_if_needed()

    def _should_autodisable_epm(self, sensor_group: SolisSensorGroup) -> bool:
        """True when a wholly unreadable group means the EPM hardware is absent."""
        if self._epm_disabled:
            return False
        if not is_string_epm_operating_group(self.controller.inverter_config.type, sensor_group):
            return False
        return epm_group_is_absence_witness(sensor_group)

    def _disable_epm_runtime(self, trigger_register: int) -> None:
        """Stop polling every EPM group for this session and queue persisting has_epm=False."""
        if self._epm_disabled:
            return
        self._epm_disabled = True
        self.controller.inverter_config.disable_epm()

        disabled_sensors = []
        kept = []
        for group in self.controller._sensor_groups:
            if is_string_epm_operating_group(self.controller.inverter_config.type, group):
                for sensor in group.sensors:
                    sensor.enabled = False
                    disabled_sensors.append(sensor)
            else:
                kept.append(group)
        self.controller._sensor_groups = kept
        mark_platform_entities_unavailable_for_base_sensors(self.hass, disabled_sensors)

        _LOGGER.warning(
            "(%s.%s) No EPM at register %s (illegal data address); disabled EPM polling. "
            "Re-enable 'EPM / export power manager' in options if one is installed.",
            self.controller.host,
            self.controller.slave,
            trigger_register,
        )
        self._create_epm_absent_issue(trigger_register)
        self._epm_persist_pending = True

    def _create_epm_absent_issue(self, trigger_register: int) -> None:
        if self._entry_id is None:
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"epm_absent_{self._entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="epm_absent",
            translation_placeholders={
                "host": str(self.controller.host),
                "register": str(trigger_register),
            },
        )

    def _start_persist_epm_disabled_if_needed(self) -> None:
        """Persist has_epm=False after the current poll/setup task has finished.

        Must not run inside poll_controller: reloading the entry would deadlock
        waiting for that task (issue #466).
        """
        if not self._epm_persist_pending or self._epm_persist_started or self._entry_id is None:
            return
        if self.connection_check:
            return
        self._epm_persist_started = True

        def _start() -> None:
            self.hass.async_create_task(self._async_persist_epm_disabled())

        loop = getattr(self.hass, "loop", None)
        if loop is not None and hasattr(loop, "call_soon"):
            loop.call_soon(_start)
            return
        _start()

    async def _async_persist_epm_disabled(self) -> None:
        """Write has_epm=False so the next load skips 36xxx groups (options win over data)."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return
        merged = {**entry.data, **entry.options}
        if merged.get("has_epm") is False:
            return
        self.hass.config_entries.async_update_entry(entry, options={**entry.options, "has_epm": False})

    # https://github.com/Pho3niX90/solis_modbus/issues/138
    def spike_filtering(self, register: int, value: int):
        """Filter short-lived implausible readings for known noisy registers."""
        cached_value = cache_get(self.hass, self.controller, register)
        if register not in self._spike_counter:
            self._spike_counter[register] = 0

        # 33139 Battery SOC: readings stuck at hard edge can briefly spike.
        if register == 33139:
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
