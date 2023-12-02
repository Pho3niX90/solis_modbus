import logging

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException

_LOGGER = logging.getLogger(__name__)


class ModbusController:
    def __init__(self, host, port=502):
        self.host = host
        self.port = port
        self.client = ModbusTcpClient(self.host, port=self.port)

    def connect(self):
        _LOGGER.debug('connecting')
        try:
            if not self.client.connect():
                raise ConnectionError("Failed to connect to Modbus device.")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Modbus device: {str(e)}")

    def read_input_register(self, register, count=1):
        try:
            result = self.client.read_input_registers(register, count, slave=1)
            if result.isError():
                raise ValueError(f"Failed to read Modbus register ({register}): {result}")
            _LOGGER.debug(f'register value, register = {register}, result = {result.registers}')
            if count > 1:
                return result.registers
            return result.registers[0]
        except ModbusIOException as e:
            raise ValueError(f"Failed to read Modbus register: {str(e)}")

    def read_holding_register(self, register, count=1):
        try:
            result = self.client.read_holding_registers(register, count, slave=1)
            if result.isError():
                raise ValueError(f"Failed to read Modbus register ({register}): {result}")
            _LOGGER.debug(f'holding register value, register = {register}, result = {result.registers}')
            if count > 1:
                return result.registers
            return result.registers[0]
        except ModbusIOException as e:
            raise ValueError(f"Failed to read Modbus holding register: {str(e)}")

    def write_holding_register(self, register, value):
        try:
            result = self.client.write_register(register, value, slave=1)
            if result.isError():
                raise ValueError(f"Failed to write Modbus holding register ({register}): {result}")
            return result
        except ModbusIOException as e:
            raise ValueError(f"Failed to write Modbus register: {str(e)}")

    def close_connection(self):
        self.client.close()

    def connected(self):
        return self.client.connected
