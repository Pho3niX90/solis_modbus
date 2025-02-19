import asyncio
import logging
from datetime import timedelta
import time

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from typing_extensions import List

from .data.enums import PollSpeed
from .modbus_controller import ModbusController
from custom_components.solis_modbus.const import REGISTER, VALUE, DOMAIN, CONTROLLER
from custom_components.solis_modbus.helpers import cache_save
from .sensors.solis_base_sensor import SolisSensorGroup

_LOGGER = logging.getLogger(__name__)

class DataRetrieval:
    def __init__(self, hass: HomeAssistant, controller: ModbusController):
        self.controller: ModbusController = controller
        self.hass = hass
        self.poll_lock = asyncio.Lock()
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
        # Emit controller status
        self.hass.bus.async_fire(DOMAIN, {REGISTER: 5, VALUE: self.controller.enabled, CONTROLLER: self.controller.host})

        if self.controller.connected():
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
            retry_delay = min(retry_delay * 2, 30)  # ✅ Proper exponential backoff

    async def poll_controller(self, event=None):
        """Poll the Modbus controller for data, retrying until success."""
        await self.check_connection()

        # Start periodic polling
        async_track_time_interval(self.hass, self.check_connection, timedelta(seconds=60))
        async_track_time_interval(self.hass, self.modbus_update_fast, timedelta(seconds=self.controller.poll_speed.get(PollSpeed.FAST, 5)))
        async_track_time_interval(self.hass, self.modbus_update_normal, timedelta(seconds=self.controller.poll_speed.get(PollSpeed.NORMAL, 15)))
        async_track_time_interval(self.hass, self.modbus_update_slow, timedelta(seconds=self.controller.poll_speed.get(PollSpeed.SLOW, 30)))

        self.hass.create_task(self.controller.process_write_queue())

    async def modbus_update_fast(self, now):
        await self.get_modbus_updates([g for g in self.controller.sensor_groups if g.poll_speed == PollSpeed.FAST], PollSpeed.FAST)

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
                        continue

                    for i, value in enumerate(values):
                        reg = start_register + i
                        _LOGGER.debug(f"register {reg} has value {value}")
                        cache_save(self.hass, reg, value)
                        self.hass.bus.async_fire(DOMAIN, {REGISTER: reg, VALUE: value, CONTROLLER: self.controller.host})

                    if sensor_group.poll_speed == PollSpeed.ONCE:
                        marked_for_removal.append(sensor_group)

                    self.controller._data_received = True

                # Remove "ONCE" poll speed groups
                self.controller._sensor_groups = [g for g in self.controller.sensor_groups if g not in marked_for_removal]

                total_duration = time.perf_counter() - total_start_time
                _LOGGER.debug(f"✅ {speed.name} update completed in {total_duration:.4f}s")

        finally:
            del self.poll_updating[speed][group_hash]  # ✅ Reset only this group set
