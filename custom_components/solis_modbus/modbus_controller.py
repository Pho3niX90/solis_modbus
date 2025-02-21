import asyncio
import logging
import time
from typing import List

from pymodbus.client import AsyncModbusTcpClient

from custom_components.solis_modbus.const import DOMAIN, REGISTER, VALUE, CONTROLLER
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.data.solis_config import InverterConfig
from custom_components.solis_modbus.helpers import cache_save
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

_LOGGER = logging.getLogger(__name__)


class ModbusController:
    def __init__(self, hass, host, inverter_config: InverterConfig, sensor_groups: List[SolisSensorGroup] = None,
                 derived_sensors: List[SolisDerivedSensor] = None, port=502, fast_poll=5, normal_poll=15, slow_poll=30):
        self.hass = hass
        self.host = host
        self.port = port
        self.client: AsyncModbusTcpClient = AsyncModbusTcpClient(host=self.host, port=self.port, timeout=5, retries=5)
        self.connect_failures = 0
        self._data_received = False
        self._poll_interval_fast = fast_poll
        self._poll_interval_normal = normal_poll
        self._poll_interval_slow = slow_poll
        self._model = inverter_config.model
        self.inverter_config = inverter_config
        self._sw_version = "N/A"
        self.enabled = True
        self._last_attempt = 0  # Track last connection attempt time
        self._sensor_groups = sensor_groups
        self._derived_sensors = derived_sensors
        self.poll_lock = asyncio.Lock()

        # Modbus Write Queue
        self.write_queue = asyncio.Queue()
        self._last_modbus_request = 0

    async def process_write_queue(self):
        """Process queued Modbus write requests sequentially."""
        while True:
            if not self.connected():
                await asyncio.sleep(5)
                continue

            if self.write_queue.empty():
                await asyncio.sleep(0.2)
                continue

            write_request = await self.write_queue.get()
            register, value, multiple = write_request

            if multiple:
                await self._execute_write_holding_registers(register, value)
            else:
                await self._execute_write_holding_register(register, value)

            self.write_queue.task_done()

    async def _execute_write_holding_register(self, register, value):
        """Executes a single register write with interframe delay."""
        try:
            await self.connect()
            async with self.poll_lock:
                await self.inter_frame_wait(is_write=True)  # Delay before write
                int_value = int(value)
                int_register = int(register)
                result = await self.client.write_register(address=int_register, value=int_value, slave=1)
                _LOGGER.debug(
                    f"Write Holding Register register = {int_register}, value = {value}, int_value = {int_value}: {result}")

                if result.isError():
                    _LOGGER.error(f"Failed to write holding register {register} with value {value}: {result}")
                    return None

                cache_save(self.hass, int_register, result.registers[0])
                self.hass.bus.async_fire(DOMAIN,
                                         {REGISTER: int_register, VALUE: result.registers[0], CONTROLLER: self.host})

                return result
        except Exception as e:
            _LOGGER.error(f"Failed to write holding register {register}: {str(e)}")
            return None

    async def _execute_write_holding_registers(self, start_register, values):
        """Executes a multiple register write."""
        try:
            await self.connect()
            async with self.poll_lock:
                await self.inter_frame_wait(is_write=True)
                result = await self.client.write_registers(address=start_register, values=values, slave=1)
                _LOGGER.debug(f"Write Holding Registers register = {start_register}, values = {values}: {result}")

                if result.isError():
                    _LOGGER.error(f"Failed to write holding registers {start_register} with values {values}: {result}")
                    return None

                for i, value in result.registers:
                    reg = start_register + i
                    cache_save(self.hass, reg, value)
                    self.hass.bus.async_fire(DOMAIN, {REGISTER: reg, VALUE: value, CONTROLLER: self.host})

                return result
        except Exception as e:
            _LOGGER.error(f"Failed to write holding registers {start_register} with values {values}: {str(e)}")
            return None

    async def async_write_holding_register(self, register, value):
        """Queues a single holding register write asynchronously."""
        await self.write_queue.put((register, value, False))
        _LOGGER.debug(f"Queued Write Holding Register register = {register}, value = {value}")

    async def async_write_holding_registers(self, start_register, values):
        """Queues multiple holding registers write asynchronously."""
        await self.write_queue.put((start_register, values, True))

        _LOGGER.debug(f"Queued Write Holding Registers register = {start_register}, values = {values}")

    async def async_read_input_register(self, register, count=1):
        """Reads an input register asynchronously."""
        try:
            await self.connect()
            result = await self.client.read_input_registers(address=register, count=count, slave=1)
            _LOGGER.debug(f"Register {register}: {result.registers}")
            await self.inter_frame_wait()
            return result.registers
        except Exception as e:
            _LOGGER.error(f"Failed to read input register {register}: {str(e)}")
            return None

    async def async_read_holding_register(self, register, count=1):
        """Reads a holding register asynchronously."""
        try:
            await self.connect()
            result = await self.client.read_holding_registers(address=register, count=count, slave=1)
            _LOGGER.debug(f"Holding Register {register}: {result.registers}")
            await self.inter_frame_wait()
            return result.registers
        except Exception as e:
            _LOGGER.error(f"Failed to read holding register {register}: {str(e)}")
            return None

    async def inter_frame_wait(self, read_delay=0.3, write_delay=0.7, is_write=False):
        """Ensures the Modbus interframe delay is respected before the next request."""
        required_delay = write_delay if is_write else read_delay
        elapsed_time = time.monotonic() - self._last_modbus_request

        # Calculate remaining delay (if any)
        remaining_delay = max(0.0, required_delay - elapsed_time)
        _LOGGER.debug(f"inter_frame elapsed = {elapsed_time}, remaining_wait = {remaining_delay}")

        if remaining_delay > 0:
            await asyncio.sleep(remaining_delay)

        self._last_modbus_request = time.monotonic()  # Update last request time


    async def connect(self):
        """Ensure the Modbus TCP connection is active."""
        if self.client.connected:
            return True  # Already connected

        now = time.monotonic()
        if now - self._last_attempt < 1:
            return False  # Prevent excessive reconnections

        self._last_attempt = now  # Update last attempt time

        try:
            _LOGGER.debug('Connecting to Modbus TCP...')
            if not await self.client.connect():
                self.connect_failures += 1
                _LOGGER.debug(f"Failed to connect (Attempt {self.connect_failures})")
                return False
            self.connect_failures = 0
            return True

        except Exception as e:
            _LOGGER.error(f"Connection error: {e}")
            return False

    def disable_connection(self):
        self.enabled = False
        self.close_connection()

    async def enable_connection(self):
        self.enabled = True
        await self.connect()

    def close_connection(self):
        """Closes the Modbus connection."""
        self.client.close()

    def connected(self):
        return self.client.connected

    @property
    def poll_speed(self):
        return {PollSpeed.FAST: self._poll_interval_fast, PollSpeed.NORMAL: self._poll_interval_normal,
                PollSpeed.SLOW: self._poll_interval_slow}

    @property
    def model(self):
        return self._model

    @property
    def sw_version(self):
        return self._sw_version

    @property
    def data_received(self):
        return self._data_received

    @property
    def sensor_groups(self):
        return self._sensor_groups

    @property
    def sensor_derived_groups(self):
        return self._derived_sensors
