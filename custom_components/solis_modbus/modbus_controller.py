import logging
import time

from pymodbus.client import AsyncModbusTcpClient
from typing_extensions import List

from custom_components.solis_modbus.const import MODEL
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

_LOGGER = logging.getLogger(__name__)

class ModbusController:
    def __init__(self, host, sensor_groups: List[SolisSensorGroup] = None, derived_sensors: List[SolisDerivedSensor] = None, port=502, poll_interval=15):
        self.host = host
        self.port = port
        self.client: AsyncModbusTcpClient = AsyncModbusTcpClient(host=self.host, port=self.port, retries=10, timeout=10, reconnect_delay=10)
        self.connect_failures = 0
        self._data_received = False
        self._poll_interval = poll_interval
        self._model = MODEL
        self._sw_version = "N/A"
        self.enabled = True
        self._last_attempt = 0  # Track last connection attempt time
        self._sensor_groups = sensor_groups
        self._derived_sensors = derived_sensors



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
            return True

        except Exception as e:
            _LOGGER.error(f"Connection error: {e}")
            return False

    async def async_read_input_register(self, register, count=1):
        """Reads an input register asynchronously without locking."""
        try:
            await self.connect()
            result = await self.client.read_input_registers(address=register, count=count, slave=1)
            _LOGGER.debug(f"Register {register}: {result.registers}")
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
            return result.registers
        except Exception as e:
            _LOGGER.error(f"Failed to read holding register {register}: {str(e)}")
            return None

    async def async_write_holding_register(self, register, value):
        """Writes a single holding register asynchronously."""
        try:
            await self.connect()
            return await self.client.write_register(address=register, value=value, slave=1)
        except Exception as e:
            _LOGGER.error(f"Failed to write holding register {register}: {str(e)}")
            return None

    async def async_write_holding_registers(self, start_register, values):
        """Writes multiple holding registers asynchronously."""
        try:
            await self.connect()
            return await self.client.write_registers(address=start_register, values=values, slave=1)
        except Exception as e:
            _LOGGER.error(f"Failed to write holding registers {start_register}: {str(e)}")
            return None

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

    @property
    def sensor_groups(self):
        return self._sensor_groups

    @property
    def sensor_derived_groups(self):
        return self._derived_sensors
