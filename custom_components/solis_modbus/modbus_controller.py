import asyncio
import logging

from pymodbus.client import AsyncModbusTcpClient

_LOGGER = logging.getLogger(__name__)


class ModbusController:
    def __init__(self, host, port=502):
        self.host = host
        self.port = port
        self.client: AsyncModbusTcpClient = AsyncModbusTcpClient(self.host, port=self.port)
        self.connect_failures = 0
        self._lock = asyncio.Lock()

    async def connect(self):
        try:
            if self.client.connected:
                return True

            _LOGGER.debug('connecting')

            if not await self.client.connect():
                self.connect_failures += 1
                _LOGGER.warning(
                    f"Failed to connect to Modbus device. Will retry, failures = {self.connect_failures}")
                return False  # Return False if connection fails
            else:
                self.connect_failures = 0
                return True

        except ConnectionError as e:
            _LOGGER.debug(f"Failed to connect to Modbus device. Will retry. Exception: {str(e)}")
            return False  # Return False if an exception occurs


    async def async_read_input_register(self, register, count=1):
        try:
            await self.connect()
            async with self._lock:
                result = await self.client.read_input_registers(register, count, slave=1)
                _LOGGER.debug(f'register value, register = {register}, result = {result.registers}')
            return result.registers
        except Exception as e:
            _LOGGER.debug(f"Failed to read Modbus holding register: {str(e)}")
            return None

    async def async_read_holding_register(self, register: int, count=1):
        try:
            await self.connect()
            async with self._lock:
                result = await self.client.read_holding_registers(register, count, slave=1)
                _LOGGER.debug(f'holding register value, register = {register}, result = {result.registers}')
            return result.registers
        except Exception as e:
            _LOGGER.debug(f"Failed to read Modbus holding register: {str(e)}")
            return None

    async def async_write_holding_register(self, register: int, value):
        try:
            await self.connect()
            async with self._lock:
                result = await self.client.write_register(register, value, slave=1)
            return result
        except Exception as e:
            _LOGGER.debug(f"Failed to write Modbus holding register ({register}): {str(e)}")
            return None

    async def async_write_holding_registers(self, start_register: int, values: list[int]):
        try:
            await self.connect()
            async with self._lock:
                result = await self.client.write_registers(start_register, values, slave=1)
            return result
        except Exception as e:
            _LOGGER.debug(
                f"Failed to write Modbus holding registers ({start_register}), values = {values}: {str(e)}")
            return None

    def close_connection(self):
        self.client.close()

    def connected(self):
        return self.client.connected
