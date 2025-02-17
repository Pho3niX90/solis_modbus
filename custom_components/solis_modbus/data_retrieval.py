import asyncio
import logging
from datetime import timedelta
import time
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .modbus_controller import ModbusController
from custom_components.solis_modbus.const import REGISTER, VALUE, DOMAIN, CONTROLLER
from custom_components.solis_modbus.helpers import cache_save

_LOGGER = logging.getLogger(__name__)


class DataRetrieval:
    def __init__(self, hass: HomeAssistant, controller: ModbusController):
        self.controller: ModbusController = controller
        self.hass = hass

        if self.hass.is_running:
            self.hass.create_task(self.poll_controller())
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.poll_controller)

    async def poll_controller(self, event=None):
        """Poll the Modbus controller for data, retrying until success."""
        retry_delay = 1  # Start with 1-second delay

        while not self.controller.connected():
            if await self.controller.connect():
                _LOGGER.info("Modbus controller connected successfully.")
                break

            _LOGGER.warning(f"Modbus connection failed, retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)

        # Once connected, start polling data
        self._unsub_timer = async_track_time_interval(
            self.hass, self.get_modbus_updates, timedelta(seconds=self.controller.poll_interval)
        )

    async def get_modbus_updates(self, now):
        """Read registers from the Modbus controller and store values."""

        if not self.controller.enabled:
            return

        total_start_time = time.perf_counter()
        group_times = {}
        total_registrars = 0
        total_groups  = 0

        for sensor_group in self.controller.sensor_groups:
            group_start_time = time.perf_counter()

            start_register = sensor_group.start_register
            count = sensor_group.registrar_count
            group_name = f"(Registers {start_register} to {start_register + count - 1})"
            total_registrars += count
            total_groups += 1

            values = await (
                self.controller.async_read_holding_register(start_register, count)
                if start_register >= 40000
                else self.controller.async_read_input_register(start_register, count)
            )

            group_end_time = time.perf_counter()
            group_duration = group_end_time - group_start_time
            group_times[group_name] = group_duration

            _LOGGER.debug(
                f"Modbus Group '{group_name}' read in {group_duration:.4f}s "
            )

            if values is None:
                continue

            for i, value in enumerate(values):
                register_key = f"{start_register + i}"
                cache_save(self.hass, register_key, value)

                # 🔥 Fire event when new data is available
                # todo consider sensors with multiple registers
                self.hass.bus.async_fire(DOMAIN, {REGISTER: register_key, VALUE: value, CONTROLLER: self.controller.host})

            self.controller._data_received = True

            total_end_time = time.perf_counter()
            total_duration = total_end_time - total_start_time

            avg_time = total_duration / len(self.controller.sensor_groups) if self.controller.sensor_groups else 0

            diff = self.controller.poll_interval - total_duration
            if diff <= 0:
                _LOGGER.warning(f"🚨 Modbus total update time: {total_duration:.4f}s (Avg per group: {avg_time:.4f}s). {total_registrars} registrars read, which consists of {total_groups}")
            else:
                _LOGGER.warning(f"✅ Modbus total update time: {total_duration:.4f}s (Avg per group: {avg_time:.4f}s). {total_registrars} registrars read, which consists of {total_groups}")