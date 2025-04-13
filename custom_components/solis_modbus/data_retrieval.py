import asyncio
import logging
import time
from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from typing_extensions import List

from custom_components.solis_modbus.const import REGISTER, VALUE, DOMAIN, CONTROLLER
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
            PollSpeed.SLOW: {}
        }

        if self.hass.is_running:
            self.hass.create_task(self.poll_controller())
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.poll_controller)

    async def check_connection(self, now=None):
        """Ensure the Modbus controller is connected, retrying on failure."""
        if self.connection_check:
            return

        self.connection_check = True

        # Emit controller status
        self.hass.bus.async_fire(DOMAIN,
                                 {REGISTER: 90005, VALUE: self.controller.enabled, CONTROLLER: self.controller.host})

        if self.controller.connected():
            if self.first_poll:
                await self.modbus_update_all()
                self.first_poll = False
            return

        retry_delay = 0.5
        while not self.controller.connected():
            try:
                if await self.controller.connect():
                    _LOGGER.info("✅ Modbus controller connected successfully.")
                    break
                _LOGGER.debug(f"⚠️ Modbus connection failed, retrying in {retry_delay:.2f} seconds...")
            except Exception as e:
                _LOGGER.error(f"❌ Connection error: {e}")

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)

        self.connection_check = False

    async def poll_controller(self, event=None):
        """Poll the Modbus controller for data, retrying until success."""
        await self.check_connection()

        # Start periodic polling
        async_track_time_interval(self.hass, self.check_connection, timedelta(minutes=2))
        async_track_time_interval(self.hass, self.modbus_update_fast, timedelta(seconds=self.controller.poll_speed.get(PollSpeed.FAST, 5)))
        async_track_time_interval(self.hass, self.modbus_update_normal, timedelta(seconds=self.controller.poll_speed.get(PollSpeed.NORMAL, 15)))
        async_track_time_interval(self.hass, self.modbus_update_slow, timedelta(seconds=self.controller.poll_speed.get(PollSpeed.SLOW, 30)))

        self.hass.create_task(self.controller.process_write_queue())

    async def modbus_update_all(self):
        await self.get_modbus_updates(self.controller.sensor_groups, PollSpeed.STARTUP)

    async def modbus_update_fast(self, now):
        await self.get_modbus_updates([g for g in self.controller.sensor_groups if g.poll_speed == PollSpeed.FAST], PollSpeed.FAST)
        self.hass.bus.async_fire(DOMAIN, {REGISTER: 90006, VALUE: self.controller.last_modbus_success, CONTROLLER: self.controller.host})

    async def modbus_update_slow(self, now):
        await self.get_modbus_updates([g for g in self.controller.sensor_groups if g.poll_speed == PollSpeed.SLOW], PollSpeed.SLOW)

    async def modbus_update_normal(self, now):
        await self.get_modbus_updates([g for g in self.controller.sensor_groups if g.poll_speed in (PollSpeed.NORMAL, PollSpeed.ONCE)], PollSpeed.NORMAL)

    async def get_modbus_updates(self, groups: List[SolisSensorGroup], speed: PollSpeed):
        """Read registers from the Modbus controller, ensuring no concurrent runs."""
        if not self.controller.enabled or not self.controller.connected():
            return

        group_hash = frozenset({group.start_register for group in groups})

        if group_hash in self.poll_updating[speed]:
            _LOGGER.debug(f"⚠️ Skipping {speed.name} update: A previous instance is still running")
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

                    _LOGGER.debug(f"Group {start_register} starting")

                    values = await (
                        self.controller.async_read_holding_register(start_register, count)
                        if start_register >= 40000
                        else self.controller.async_read_input_register(start_register, count)
                    )

                    if values is None:
                        _LOGGER.debug(f"⚠️ Received None for register {start_register} - {start_register + count - 1}, skipping.")
                        continue
                    if len(values) != count:
                        _LOGGER.debug(
                            f"⚠️ Modbus read mismatch: Received {len(values)} values, expected {count} "
                            f"for register {start_register} - {start_register + count - 1}. Skipping because linking them is uncertain."
                        )
                        continue

                    for i, value in enumerate(values):
                        reg = start_register + i
                        _LOGGER.debug(f"block {start_register}, register {reg} has value {value}")
                        corrected_value = self.spike_filtering(reg, value)
                        cache_save(self.hass, reg, corrected_value)
                        self.hass.bus.async_fire(DOMAIN, {REGISTER: reg, VALUE: corrected_value, CONTROLLER: self.controller.host})

                    if sensor_group.poll_speed == PollSpeed.ONCE:
                        marked_for_removal.append(sensor_group)

                    self.controller._data_received = True

                # Remove "ONCE" poll speed groups
                self.controller._sensor_groups = [g for g in self.controller.sensor_groups if
                                                  g not in marked_for_removal]

                total_duration = time.perf_counter() - total_start_time
                _LOGGER.debug(f"✅ {speed.name} update completed in {total_duration:.4f}s")

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
