import asyncio
import logging
import time
from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus.helpers import (
    cache_get,
    cache_save,
    mark_platform_entities_unavailable_for_base_sensors,
    notify_register_update,
)

from .data.enums import PollSpeed
from .modbus_controller import RECOVERABLE_REGISTER_READ_EXCEPTIONS, ModbusController
from .sensors.solis_base_sensor import SolisSensorGroup, cluster_sensors_by_contiguous_registers

_LOGGER = logging.getLogger(__name__)

_MAX_REGISTER_RECOVERY_DEPTH = 24


class DataRetrieval:
    def __init__(self, hass: HomeAssistant, controller: ModbusController):
        self._spike_counter = {}
        self.controller: ModbusController = controller
        self.hass = hass
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

        if self.hass.is_running:
            self.hass.create_task(self.poll_controller())
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
            _LOGGER.debug(f"block {start_register}, register {reg} has value {value}")
            corrected_value = self.spike_filtering(reg, value)
            cache_save(self.hass, reg, corrected_value)
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
        """Cancel all listeners."""
        # Clean up the startup listener only if it hasn't fired yet
        if self._startup_unsub:
            self._startup_unsub()
            self._startup_unsub = None

        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners = []
        self.connection_check = False  # Stop connection loop logic if any

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

        self.connection_check = True

        # Emit controller status (dispatcher — not persisted to recorder)
        notify_register_update(self.hass, self.controller, 90005, self.controller.enabled)

        if self.controller.connected():
            if self.first_poll:
                await self.modbus_update_all()
                self.first_poll = False
            return

        retry_delay = 0.5
        while not self.controller.connected():
            try:
                if await self.controller.connect():
                    _LOGGER.info(f"✅({self.controller.host}.{self.controller.slave}) Modbus controller connected successfully.")
                    break
                _LOGGER.debug(f"⚠️({self.controller.host}.{self.controller.slave}) Modbus connection failed, retrying in {retry_delay:.2f} seconds...")
            except Exception as e:
                _LOGGER.error(f"❌({self.controller.host}.{self.controller.slave}) Connection error : {e}")

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)

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

        self.hass.create_task(self.controller.process_write_queue())

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
                            else:
                                _LOGGER.debug(
                                    f"⚠️ Received None for register {start_register} - {end_register}, for ({self.controller.host}.{self.controller.slave}), skipping."
                                )
                        else:
                            _LOGGER.debug(
                                f"⚠️ Received None for register {start_register} - {end_register}, for ({self.controller.host}.{self.controller.slave}), skipping."
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
                self.controller._sensor_groups = [g for g in self.controller.sensor_groups if g not in marked_for_removal]

                total_duration = time.perf_counter() - total_start_time
                _LOGGER.debug(f"✅ {speed.name} update completed in {total_duration:.4f}s")
        except Exception as e:
            _LOGGER.debug("exception caught: %s", e)
        finally:
            del self.poll_updating[speed][group_hash]  # ✅ Reset only this group set

    # https://github.com/Pho3niX90/solis_modbus/issues/138
    def spike_filtering(self, register: int, value: int):
        """Filter short-lived implausible readings for known noisy registers."""
        cached_value = cache_get(self.hass, register)
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
