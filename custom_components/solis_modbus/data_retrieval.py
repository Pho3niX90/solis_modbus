import asyncio
import logging
from datetime import timedelta

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

        for sensor_group in self.controller.sensor_groups:
            start_register = sensor_group.start_register
            count = sensor_group.registrar_count

            values = await (
                self.controller.async_read_holding_register(start_register, count)
                if start_register >= 40000
                else self.controller.async_read_input_register(start_register, count)
            )
            _LOGGER.warning(f"Reading values {start_register} to {start_register + count}, values are {values}")

            if values is None:
                continue

            for i, value in enumerate(values):
                register_key = f"{start_register + i}"
                cache_save(self.hass, register_key, value)

                # 🔥 Fire event when new data is available
                # todo consider sensors with multiple registers
                self.hass.bus.async_fire(DOMAIN, {REGISTER: register_key, VALUE: value, CONTROLLER: self.controller.host})

            self.controller._data_received = True