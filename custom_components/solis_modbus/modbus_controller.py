import asyncio
import logging
import time
from pymodbus.client import AsyncModbusTcpClient

from custom_components.solis_modbus.const import MODEL

_LOGGER = logging.getLogger(__name__)

class ModbusController:
    def __init__(self, host, port=502, poll_interval=15):
        self.host = host
        self.port = port
        self.client: AsyncModbusTcpClient = AsyncModbusTcpClient(self.host, port=self.port)
        self.connect_failures = 0
        self._lock = asyncio.Lock()
        self._data_received = False
        self._poll_interval = poll_interval
        self._model = MODEL
        self._sw_version = "N/A"
        self.enabled = True
        self._last_attempt = 0  # Track last connection attempt time

    async def connect(self):
        async with self._lock:
            now = time.monotonic()
            if now - self._last_attempt < 1:
                return False  # Skip execution if called too soon

            self._last_attempt = now  # Update last attempt time

            try:
                if self.client.connected:
                    return True

                _LOGGER.debug('connecting')

                if not await self.client.connect():
                    self.connect_failures += 1
                    fail_msg = f"Failed to connect to Modbus device. Will retry, failures = {self.connect_failures}"
                    if self.connect_failures > 50:
                        _LOGGER.warning(fail_msg)
                    elif self.connect_failures > 30:
                        _LOGGER.info(fail_msg)
                    else:
                        _LOGGER.debug(fail_msg)
                    return False

                else:
                    self.connect_failures = 0
                    return True

            except ConnectionError as e:
                _LOGGER.debug(f"Failed to connect to Modbus device. Will retry. Exception: {str(e)}")
                return False  # Return False if an exception occurs

    async def disconnect(self):
        if self.client.connected:
            self.client.close()

    async def async_read_input_register(self, register, count=1):
        try:
            await self.connect()
            async with self._lock:
                result = await self.client.read_input_registers(address=register, count=count, slave=1)
                _LOGGER.debug(f'register value, register = {register}, result = {result.registers}')
            return result.registers
        except Exception as e:
            _LOGGER.debug(f"Failed to read Modbus holding register: {str(e)}")
            return None

    async def async_read_holding_register(self, register: int, count=1):
        try:
            await self.connect()
            async with self._lock:
                result = await self.client.read_holding_registers(address=register, count=count, slave=1)
                _LOGGER.debug(f'holding register value, register = {register}, result = {result.registers}')
            return result.registers
        except Exception as e:
            _LOGGER.debug(f"Failed to read Modbus holding register: {str(e)}")
            return None

    async def async_write_holding_register(self, register: int, value):
        try:
            await self.connect()
            async with self._lock:
                result = await self.client.write_register(address=register, value=value, slave=1)
            return result
        except Exception as e:
            _LOGGER.debug(f"Failed to write Modbus holding register ({register}): {str(e)}")
            return None

    async def async_write_holding_registers(self, start_register: int, values: list[int]):
        try:
            await self.connect()
            async with self._lock:
                result = await self.client.write_registers(address=start_register, values=values, slave=1)
            return result
        except Exception as e:
            _LOGGER.debug(
                f"Failed to write Modbus holding registers ({start_register}), values = {values}: {str(e)}")
            return None

    def close_connection(self):
        self.client.close()

    def connected(self):
        return self.client.connected

    @property
    def poll_interval(self):
        return self._poll_interval

    @property
    def model(self):
        return self._model

    @property
    def sw_version(self):
        return self._sw_version

    @property
    def data_received(self):
        return self._data_received
