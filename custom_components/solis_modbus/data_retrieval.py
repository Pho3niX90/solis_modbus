import asyncio
import logging
import time
from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from typing_extensions import List

from custom_components.solis_modbus.const import REGISTER, VALUE, DOMAIN, CONTROLLER, SLAVE
from custom_components.solis_modbus.helpers import cache_save, cache_get
from .data.enums import PollSpeed
from .modbus_controller import ModbusController
from .sensors.solis_base_sensor import SolisSensorGroup

_LOGGER = logging.getLogger(__name__)

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

        # Emit controller status
        self.hass.bus.async_fire(DOMAIN,
                                 {REGISTER: 90005, VALUE: self.controller.enabled, CONTROLLER: self.controller.host,
                                  SLAVE: self.controller.slave})

        if self.controller.connected():
            if self.first_poll:
                await self.modbus_update_all()
                self.first_poll = False
            return

        retry_delay = 0.5
        while not self.controller.connected():
            try:
                if await self.controller.connect():
                    _LOGGER.info(
                        f"✅({self.controller.host}.{self.controller.slave}) Modbus controller connected successfully.")
                    break
                _LOGGER.debug(
                    f"⚠️({self.controller.host}.{self.controller.slave}) Modbus connection failed, retrying in {retry_delay:.2f} seconds...")
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
        self._unsub_listeners.append(async_track_time_interval(self.hass, self.modbus_update_fast, timedelta(
            seconds=self.controller.poll_speed.get(PollSpeed.FAST, 5))))
        self._unsub_listeners.append(async_track_time_interval(self.hass, self.modbus_update_normal, timedelta(
            seconds=self.controller.poll_speed.get(PollSpeed.NORMAL, 15))))
        self._unsub_listeners.append(async_track_time_interval(self.hass, self.modbus_update_slow, timedelta(
            seconds=self.controller.poll_speed.get(PollSpeed.SLOW, 30))))

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
        await self.get_modbus_updates([g for g in self.controller.sensor_groups if g.poll_speed == PollSpeed.FAST],
                                      PollSpeed.FAST)
        self.hass.bus.async_fire(DOMAIN, {REGISTER: 90006, VALUE: self.controller.last_modbus_success,
                                          CONTROLLER: self.controller.host, SLAVE: self.controller.slave})

    async def modbus_update_slow(self, now=None):
        """Updates sensor groups with slow poll speed.

        This method retrieves data for all sensor groups with a slow poll speed.

        Args:
            now (datetime, optional): Current time, provided by the scheduler. Defaults to None.

        Returns:
            None
        """
        await self.get_modbus_updates([g for g in self.controller.sensor_groups if g.poll_speed == PollSpeed.SLOW],
                                      PollSpeed.SLOW)

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
            PollSpeed.NORMAL)

    async def get_modbus_updates(self, groups: List[SolisSensorGroup], speed: PollSpeed):
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
            _LOGGER.debug(
                f"⚠️({self.controller.host}.{self.controller.slave}) Skipping {speed.name} update: A previous instance is still running")
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
                    total_registrars += count
                    total_groups += 1

                    _LOGGER.debug(
                        f"Group {start_register} starting for ({self.controller.host}.{self.controller.slave})")

                    values = await (
                        self.controller.async_read_holding_register(start_register, count)
                        if start_register >= 40000
                        else self.controller.async_read_input_register(start_register, count)
                    )

                    if values is None:
                        _LOGGER.debug(
                            f"⚠️ Received None for register {start_register} - {start_register + count - 1}, fro ({self.controller.host}.{self.controller.slave}), skipping.")
                        continue
                    if len(values) != count:
                        _LOGGER.debug(
                            f"⚠️ Modbus read mismatch: Received {len(values)} values, expected {count} from ({self.controller.host}.{self.controller.slave}) "
                            f"for register {start_register} - {start_register + count - 1}. Skipping because linking them is uncertain."
                        )
                        continue

                    for i, value in enumerate(values):
                        reg = start_register + i
                        _LOGGER.debug(f"block {start_register}, register {reg} has value {value}")
                        corrected_value = self.spike_filtering(reg, value)
                        cache_save(self.hass, reg, corrected_value)
                        self.hass.bus.async_fire(DOMAIN, {REGISTER: reg, VALUE: corrected_value,
                                                          CONTROLLER: self.controller.host,
                                                          SLAVE: self.controller.slave})

                    if sensor_group.poll_speed == PollSpeed.ONCE:
                        marked_for_removal.append(sensor_group)

                    self.controller._data_received = True

                # Remove "ONCE" poll speed groups
                self.controller._sensor_groups = [g for g in self.controller.sensor_groups if
                                                  g not in marked_for_removal]

                total_duration = time.perf_counter() - total_start_time
                _LOGGER.debug(f"✅ {speed.name} update completed in {total_duration:.4f}s")
        except Exception as e:
            _LOGGER.debug("exception caught: %s", e)
        finally:
            del self.poll_updating[speed][group_hash]  # ✅ Reset only this group set

    # https://github.com/Pho3niX90/solis_modbus/issues/138
    def spike_filtering(self, register: int, value: int):
        """Filters out short-lived spikes in battery SOC sensor readings.

        Readings between 0 and 100 (exclusive) are considered normal.
        Only values that are exactly 0 or exactly 100 are treated as potential spikes.
        """
        if register != 33139:
            return value  # Only filter for register 33139

        cached_value = cache_get(self.hass, register)

        if register not in self._spike_counter:
            self._spike_counter[register] = 0

        # If the reading is strictly between 0 and 100, it's valid.
        if value not in (0, 100):
            self._spike_counter[register] = 0  # Reset the counter on a normal reading
        else:
            # The reading is either 0 or 100 (extreme values)
            self._spike_counter[register] += 1
            if self._spike_counter[register] < 3:
                _LOGGER.debug(
                    f"Ignoring short spike value {value} for battery SOC sensor; "
                    f"retaining previous value {cached_value} (counter={self._spike_counter[register]})"
                )
                return cached_value if cached_value is not None else value
            else:
                _LOGGER.debug(
                    f"Accepting persistent spike value {value} for battery SOC sensor after {self._spike_counter[register]} cycles"
                )
                self._spike_counter[register] = 0

        return value
