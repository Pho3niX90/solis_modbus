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
        _LOGGER.warning('connecting')
        try:
            if not self.client.connect():
                raise ConnectionError("Failed to connect to Modbus device.")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Modbus device: {str(e)}")

    def read_register(self, register, count=1):
        try:
            result = self.client.read_input_registers(register, count, slave=1)
            _LOGGER.warning(f'register value, register = {register}, result = {result.registers}')
            if result.isError():
                raise ValueError(f"Failed to read Modbus register ({register}): {result}")
            if count > 1:
                return result.registers
            return result.registers[0]
        except ModbusIOException as e:
            raise ValueError(f"Failed to read Modbus register: {str(e)}")

    def close_connection(self):
        self.client.close()

    def connected(self):
        return self.client.connected
