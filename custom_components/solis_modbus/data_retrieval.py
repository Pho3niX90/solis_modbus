import asyncio

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from typing_extensions import List

from custom_components.solis_modbus import ModbusController, DOMAIN, CONTROLLER
from custom_components.solis_modbus.const import REGISTER, VALUE
from custom_components.solis_modbus.helpers import cache_save


class DataRetrieval:
    def __init__(self, hass: HomeAssistant, controller: ModbusController):
        self.controller: ModbusController = controller
        self.hass = hass

        if self.hass.is_running:
            self.hass.create_task(self.poll_controller())
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.poll_controller)

    def get_controllers(self) -> List[ModbusController]:
        return list(self.hass.data[DOMAIN][CONTROLLER].values())

    async def poll_controller(self):
        """Poll the Modbus controller for data."""
        if not self.controller.connected():
            if not await self.controller.connect():
                return

        self.hass.create_task(self.get_modbus_updates(self.controller))

    async def get_modbus_updates(self, controller: ModbusController):
        """Read registers from the Modbus controller and store values."""

        if not controller.enabled:
            return

        for sensor_group in controller.sensor_groups:
            start_register = sensor_group.start_register
            count = sensor_group.sensors_count

            values = await (
                controller.async_read_holding_register(start_register, count)
                if start_register >= 40000
                else controller.async_read_input_register(start_register, count)
            )

            if values is None:
                continue

            for i, value in enumerate(values):
                register_key = f"{start_register + i}"
                cache_save(self.hass, register_key, value)

                # 🔥 Fire event when new data is available
                # todo consider sensors with multiple registers
                self.hass.bus.async_fire(DOMAIN, {REGISTER: register_key, VALUE: value, CONTROLLER: controller.host})

            controller._data_received = True