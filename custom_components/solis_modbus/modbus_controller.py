import asyncio
import logging
import time
from datetime import datetime, UTC
from typing import List

from homeassistant.helpers.template import is_number
from pymodbus.client import AsyncModbusTcpClient

from custom_components.solis_modbus.client_manager import ModbusClientManager
from custom_components.solis_modbus.const import DOMAIN, REGISTER, VALUE, CONTROLLER, SLAVE
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.data.solis_config import InverterConfig
from custom_components.solis_modbus.helpers import cache_save
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

_LOGGER = logging.getLogger(__name__)


class ModbusController:
    def __init__(self, hass, host, inverter_config: InverterConfig, sensor_groups: List[SolisSensorGroup] = None,
                 derived_sensors: List[SolisDerivedSensor] = None, device_id=1, port=502, fast_poll=5, normal_poll=15, slow_poll=30, identification: str | None = None):
        self.hass = hass
        self.host = host
        self.port = port
        self.device_id = device_id
        # todo: quick fix, replace naming where applicable later.
        self.slave = device_id
        self.identification = identification
        manager = ModbusClientManager.get_instance()
        self.client: AsyncModbusTcpClient = manager.get_client(self.host, self.port)
        self.poll_lock = manager.get_client_lock(self.host, self.port)
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
        self._derived_sensors = derived_sensors
        # self.poll_lock = asyncio.Lock() # Replaced by shared lock from manager

        # Modbus Write Queue
        self.write_queue = asyncio.Queue()
        self._last_modbus_request = 0
        self._last_modbus_success = datetime.now(UTC)

    async def process_write_queue(self):
        """Process queued Modbus write requests sequentially.

        This method runs in an infinite loop, processing write requests from the queue.
        It ensures that write operations are executed one at a time, with appropriate
        delays between operations to avoid overwhelming the Modbus device.

        Returns:
            None
        """
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
        """Executes a single register write with interframe delay.

        Args:
            register (int): The register address to write to.
            value (int): The value to write to the register.

        Returns:
            result: The result of the write operation, or None if an error occurred.

        Raises:
            Exception: If there is an error during the write operation.
        """
        try:
            await self.connect()
            async with self.poll_lock:
                await self.inter_frame_wait(is_write=True)  # Delay before write
                int_value = int(value)
                int_register = register if is_number(register) else int(register)
                result = await self.client.write_register(address=int_register, value=int_value, device_id=self.device_id)
                _LOGGER.debug(
                    f"({self.host}.{self.device_id}) Write Holding Register register = {int_register}, value = {value}, int_value = {int_value}: {result}")

                if result.isError():
                    _LOGGER.error(f"({self.host}.{self.device_id}) Failed to write holding register {register} with value {value}: {result}")
                    return None

                cache_save(self.hass, int_register, result.registers[0])
                self.hass.bus.async_fire(DOMAIN,
                                         {REGISTER: int_register, VALUE: result.registers[0], CONTROLLER: self.host, SLAVE: self.device_id})

                return result
        except Exception as e:
            _LOGGER.error(f"Failed to write holding register {register}: {str(e)}")
            return None

    async def _execute_write_holding_registers(self, start_register, values):
        """Executes a multiple register write.

        Args:
            start_register (int): The starting register address to write to.
            values (list): A list of values to write to consecutive registers.

        Returns:
            result: The result of the write operation, or None if an error occurred.

        Raises:
            Exception: If there is an error during the write operation.
        """
        try:
            await self.connect()
            async with self.poll_lock:
                await self.inter_frame_wait(is_write=True)
                result = await self.client.write_registers(address=start_register, values=values, device_id=self.device_id)
                _LOGGER.debug(f"({self.host}.{self.device_id}) Write Holding Registers register = {start_register}, values = {values}: {result}")

                if result.isError():
                    _LOGGER.error(f"({self.host}.{self.device_id}) Failed to write holding registers {start_register} with values {values}: {result}")
                    return None

                response_values = getattr(result, "registers", None)
                if response_values is None:
                    response_values = values

                for offset, written_value in enumerate(response_values):
                    reg = start_register + offset
                    cache_save(self.hass, reg, written_value)
                    self.hass.bus.async_fire(
                        DOMAIN,
                        {REGISTER: reg, VALUE: written_value, CONTROLLER: self.host, SLAVE: self.device_id},
                    )

                return result
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Failed to write holding registers {start_register} with values {values}: {str(e)}")
            return None

    async def async_write_holding_register(self, register, value):
        """Queues a single holding register write asynchronously.

        This method adds a write request to the queue, which will be processed
        by the process_write_queue method.

        Args:
            register (int): The register address to write to.
            value (int): The value to write to the register.

        Returns:
            None
        """
        await self.write_queue.put((register, value, False))
        _LOGGER.debug(f"({self.host}.{self.device_id}) Queued Write Holding Register register = {register}, value = {value}")

    async def async_write_holding_registers(self, start_register, values):
        """Queues multiple holding registers write asynchronously.

        This method adds a write request for multiple registers to the queue,
        which will be processed by the process_write_queue method.

        Args:
            start_register (int): The starting register address to write to.
            values (list): A list of values to write to consecutive registers.

        Returns:
            None
        """
        await self.write_queue.put((start_register, values, True))
        _LOGGER.debug(f"({self.host}.{self.device_id}) Queued Write Holding Registers register = {start_register}, values = {values}")

    async def async_read_input_register(self, register, count=1):
        """Reads an input register asynchronously.

        Args:
            register (int): The register address to read from.
            count (int, optional): The number of registers to read. Defaults to 1.

        Returns:
            list: A list of register values, or None if an error occurred.

        Raises:
            Exception: If there is an error during the read operation.
        """
        try:
            async with self.poll_lock:
                await self.connect()
                result = await self.client.read_input_registers(address=register, count=count, device_id=self.device_id)
                _LOGGER.debug(f"({self.host}.{self.device_id}) Register {register}: {result.registers}")
                await self.inter_frame_wait()
            self._last_modbus_success = datetime.now(UTC)
            return result.registers
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Failed to read input register {register}: {str(e)}")
            return None

    async def async_read_holding_register(self, register, count=1):
        """Reads a holding register asynchronously.

        Args:
            register (int): The register address to read from.
            count (int, optional): The number of registers to read. Defaults to 1.

        Returns:
            list: A list of register values, or None if an error occurred.

        Raises:
            Exception: If there is an error during the read operation.
        """
        try:
            async with self.poll_lock:
                await self.connect()
                result = await self.client.read_holding_registers(address=register, count=count, device_id=self.device_id)
                _LOGGER.debug(f"({self.host}.{self.device_id}) Holding Register {register}: {result.registers}")
                await self.inter_frame_wait()
            self._last_modbus_success = datetime.now(UTC)
            return result.registers
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Failed to read holding register {register}: {str(e)}")
            return None

    async def inter_frame_wait(self, read_delay=0.3, write_delay=0.7, is_write=False):
        """Ensures the Modbus interframe delay is respected before the next request.

        This method calculates and waits for the appropriate delay between Modbus
        requests to avoid overwhelming the device.

        Args:
            read_delay (float, optional): The delay in seconds for read operations. Defaults to 0.3.
            write_delay (float, optional): The delay in seconds for write operations. Defaults to 0.7.
            is_write (bool, optional): Whether this is a write operation. Defaults to False.

        Returns:
            None
        """
        required_delay = write_delay if is_write else read_delay
        elapsed_time = time.monotonic() - self._last_modbus_request

        # Calculate remaining delay (if any)
        remaining_delay = max(0.0, required_delay - elapsed_time)
        _LOGGER.debug(f"({self.host}.{self.device_id}) inter_frame elapsed = {elapsed_time}, remaining_wait = {remaining_delay}")

        if remaining_delay > 0:
            await asyncio.sleep(remaining_delay)

        self._last_modbus_request = time.monotonic()  # Update last request time

    async def connect(self):
        """Ensure the Modbus TCP connection is active.

        This method attempts to establish a connection to the Modbus device
        if one doesn't already exist. It includes rate limiting to prevent
        excessive reconnection attempts.

        Returns:
            bool: True if the connection is established, False otherwise.

        Raises:
            Exception: If there is an error during the connection attempt.
        """
        if self.client.connected:
            return True  # Already connected

        now = time.monotonic()
        if now - self._last_attempt < 1:
            return False  # Prevent excessive reconnections

        self._last_attempt = now  # Update last attempt time

        try:
            _LOGGER.debug(f'({self.host}.{self.device_id}) Connecting to Modbus TCP...')
            if not await self.client.connect():
                self.connect_failures += 1
                _LOGGER.debug(f"({self.host}.{self.device_id}) Failed to connect (Attempt {self.connect_failures})")
                return False
            self.connect_failures = 0
            return True

        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Connection error: {e}")
            return False

    def disable_connection(self):
        """Disables the Modbus connection.

        This method sets the enabled flag to False and closes the connection.

        Returns:
            None
        """
        self.enabled = False
        self.close_connection()

    async def enable_connection(self):
        """Enables the Modbus connection.

        This method sets the enabled flag to True and attempts to establish a connection.

        Returns:
            None
        """
        self.enabled = True
        await self.connect()

    def close_connection(self):
        """Closes the Modbus connection.

        This method closes the connection to the Modbus device.

        Returns:
            None
        """
        ModbusClientManager.get_instance().release_client(self.host, self.port)

    def connected(self):
        """Checks if the Modbus connection is active.

        Returns:
            bool: True if the connection is active, False otherwise.
        """
        return self.client.connected

    @property
    def poll_speed(self):
        """Gets the polling speed configuration.

        Returns:
            dict: A dictionary mapping poll speed types to their interval values in seconds.
        """
        return {PollSpeed.FAST: self._poll_interval_fast, PollSpeed.NORMAL: self._poll_interval_normal,
                PollSpeed.SLOW: self._poll_interval_slow}

    @property
    def model(self):
        """Gets the model of the inverter.

        Returns:
            str: The model name of the inverter.
        """
        return self._model

    @property
    def sw_version(self):
        """Gets the software version of the inverter.

        Returns:
            str: The software version of the inverter.
        """
        return self._sw_version

    @property
    def data_received(self):
        """Checks if data has been received from the inverter.

        Returns:
            bool: True if data has been received, False otherwise.
        """
        return self._data_received

    @property
    def sensor_groups(self):
        """Gets the sensor groups associated with this controller.

        Returns:
            list: A list of SolisSensorGroup objects.
        """
        return self._sensor_groups

    @property
    def sensor_derived_groups(self):
        """Gets the derived sensor groups associated with this controller.

        Returns:
            list: A list of SolisDerivedSensor objects.
        """
        return self._derived_sensors

    @property
    def last_modbus_request(self):
        """Gets the timestamp of the last Modbus request.

        Returns:
            float: The timestamp of the last Modbus request (from time.monotonic()).
        """
        return self._last_modbus_request

    @property
    def last_modbus_success(self):
        """Gets the timestamp of the last successful Modbus operation.

        Returns:
            datetime: The timestamp of the last successful Modbus operation.
        """
        return self._last_modbus_success

    @property
    def device_identification(self):
        """Gets the device identification string.

        Returns:
            str: The device identification string, or an empty string if not available.
        """
        return f" {self.identification}" if self.identification else ""
