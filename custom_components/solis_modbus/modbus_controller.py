import asyncio
import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusIOException

_LOGGER = logging.getLogger(__name__)


class ModbusController:
    def __init__(self, host, port=502):
        self.host = host
        self.port = port
        self.client: AsyncModbusTcpClient = AsyncModbusTcpClient(self.host, port=self.port)
        self.connect_failures = 0
        self._lock = asyncio.Lock()

    async def connect(self):
        _LOGGER.debug('connecting')
        try:
            async with self._lock:
                if not await self.client.connect():
                    self.connect_failures += 1
                    raise _LOGGER.warning(f"Failed to connect to Modbus device. Will retry, failures = {self.connect_failures}")
                else:
                    self.connect_failures = 0
            return True
        except Exception as e:
            raise _LOGGER.error(f"Failed to connect to Modbus device. Will retry")

    async def async_read_input_register(self, register, count=1):
        try:
            async with self._lock:
                result = await self.client.read_input_registers(register, count, slave=1)
                _LOGGER.debug(f'register value, register = {register}, result = {result.registers}')
            return result.registers
        except ModbusIOException as e:
            raise ValueError(f"Failed to read Modbus register: {str(e)}")

    async def async_read_holding_register(self, register: int, count=1):
        try:
            async with self._lock:
                result = await self.client.read_holding_registers(register, count, slave=1)
                _LOGGER.debug(f'holding register value, register = {register}, result = {result.registers}')
            return result.registers
        except ModbusIOException as e:
            raise ValueError(f"Failed to read Modbus holding register: {str(e)}")

    def write_holding_register(self, register: int, value):
        try:
            result = self.client.write_register(register, value, slave=1)
            if result.isError():
                raise ValueError(f"Failed to write Modbus holding register ({register}): {result}")
            return result
        except ModbusIOException as e:
            raise ValueError(f"Failed to write Modbus register: {str(e)}")

    def write_holding_registers(self, start_register: int, values: list[int]):
        try:
            result = self.client.write_registers(start_register, values, slave=1)
            if result.isError():
                raise ValueError(f"Failed to write Modbus holding registers ({start_register}), values = {values}: {result}")
            return result
        except ModbusIOException as e:
            raise ValueError(f"Failed to write Modbus registers: {str(e)}")

    def close_connection(self):
        self.client.close()

    def connected(self):
        return self.client.connected
