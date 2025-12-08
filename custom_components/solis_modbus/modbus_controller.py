import asyncio
import logging
import time
from datetime import datetime, UTC
from typing import List, Union

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.template import is_number
from pymodbus.client import AsyncModbusTcpClient, AsyncModbusSerialClient

from custom_components.solis_modbus.client_manager import ModbusClientManager
from custom_components.solis_modbus.const import (
    DOMAIN, REGISTER, VALUE, CONTROLLER, SLAVE,
    CONN_TYPE_TCP, DEFAULT_BAUDRATE, DEFAULT_BYTESIZE, DEFAULT_PARITY, DEFAULT_STOPBITS, MANUFACTURER
)
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.data.solis_config import InverterConfig
from custom_components.solis_modbus.helpers import cache_save
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

_LOGGER = logging.getLogger(__name__)


class ModbusController:
    def __init__(self, hass, inverter_config: InverterConfig, sensor_groups: List[SolisSensorGroup] = None,
                 derived_sensors: List[SolisDerivedSensor] = None, device_id=1, fast_poll=5, normal_poll=15,
                 slow_poll=30, connection_type=CONN_TYPE_TCP,
                 # TCP parameters
                 host=None, port=502,
                 # Serial parameters
                 serial_port=None, baudrate=DEFAULT_BAUDRATE, bytesize=DEFAULT_BYTESIZE,
                 parity=DEFAULT_PARITY, stopbits=DEFAULT_STOPBITS, serial_number=None):
        """
        Initialize ModbusController with support for both TCP and Serial connections.

        Args:
            hass: Home Assistant instance
            inverter_config: Inverter configuration object
            connection_type: Either CONN_TYPE_TCP or CONN_TYPE_SERIAL

            TCP parameters:
                host: IP address or hostname for TCP connection
                port: Port number for TCP connection (default 502)

            Serial parameters:
                serial_port: Serial port path (e.g., /dev/ttyUSB0)
                baudrate: Serial baud rate (default 9600)
                bytesize: Number of data bits (default 8)
                parity: Parity setting - 'N', 'E', or 'O' (default 'N')
                stopbits: Number of stop bits (default 1)
        """
        self.hass = hass
        self.connection_type = connection_type
        self.device_id = device_id
        self.slave = device_id  # Alias for device_id
        print(f"DEBUG: Initializing ModbusController with serial_number='{serial_number}'")
        self.serial_number = serial_number

        # Use ModbusClientManager to get shared client and lock
        manager = ModbusClientManager.get_instance()

        # Connection-specific setup
        if connection_type == CONN_TYPE_TCP:
            if not host:
                raise ValueError("host is required for TCP connection")
            self.host = host
            self.port = port
            self.connection_id = f"{host}:{port}"
            self.client: Union[AsyncModbusTcpClient, AsyncModbusSerialClient] = manager.get_tcp_client(host, port)
            self.poll_lock = manager.get_client_lock(self.connection_id)
        else:  # CONN_TYPE_SERIAL
            if not serial_port:
                raise ValueError("serial_port is required for Serial connection")
            self.serial_port = serial_port
            self.baudrate = baudrate
            self.bytesize = bytesize
            self.parity = parity
            self.stopbits = stopbits
            self.connection_id = serial_port
            # For serial, set host to serial_port for backwards compatibility with logging
            self.host = serial_port
            self.client: Union[AsyncModbusTcpClient, AsyncModbusSerialClient] = manager.get_serial_client(
                serial_port, baudrate, bytesize, parity, stopbits
            )
            self.poll_lock = manager.get_client_lock(self.connection_id)

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

                # Different pymodbus APIs for TCP vs Serial
                if self.connection_type == CONN_TYPE_TCP:
                    result = await self.client.write_register(address=int_register, value=int_value,
                                                              device_id=self.device_id)
                else:
                    self.client.slave = self.device_id
                    result = await self.client.write_register(address=int_register, value=int_value)
                _LOGGER.debug(
                    f"({self.host}.{self.device_id}) Write Holding Register register = {int_register}, value = {value}, int_value = {int_value}: {result}")

                if result.isError():
                    _LOGGER.error(
                        f"({self.host}.{self.device_id}) Failed to write holding register {register} with value {value}: {result}")
                    return None

                cache_save(self.hass, int_register, result.registers[0])
                self.hass.bus.async_fire(DOMAIN,
                                         {REGISTER: int_register, VALUE: result.registers[0], CONTROLLER: self.host,
                                          SLAVE: self.device_id})

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
                await self.inter_frame_wait(is_write=True)  # Delay before write

                # Different pymodbus APIs for TCP vs Serial
                if self.connection_type == CONN_TYPE_TCP:
                    result = await self.client.write_registers(address=start_register, values=values,
                                                               device_id=self.device_id)
                else:
                    self.client.slave = self.device_id
                    result = await self.client.write_registers(address=start_register, values=values)
                _LOGGER.debug(
                    f"({self.host}.{self.device_id}) Write Holding Register block for {len(values)} registers starting at register = {start_register}")

                if result.isError():
                    _LOGGER.error(f"({self.host}.{self.device_id}) Write block failed: {result}")
                    return None

                for i, value in enumerate(values):
                    cache_save(self.hass, start_register + i, value)
                    self.hass.bus.async_fire(DOMAIN,
                                             {REGISTER: start_register + i, VALUE: value, CONTROLLER: self.host,
                                              SLAVE: self.device_id})
                return result
        except Exception as e:
            _LOGGER.error(
                f"({self.host}.{self.device_id}) Failed to write holding registers {start_register}-{start_register + len(values) - 1}: {str(e)}")
            return None

    async def async_write_holding_register(self, register, value):
        """Queues a write request to the Modbus device (write single register).

        Args:
            register (int): The register address to write to.
            value (int): The value to write to the register.

        Returns:
            None
        """
        await self.write_queue.put((register, value, False))

    async def async_write_holding_registers(self, start_register, values):
        """Queues a write request to the Modbus device (write multiple registers).

        Args:
            start_register (int): The starting register address to write to.
            values (list): A list of values to write to consecutive registers.

        Returns:
            None
        """
        await self.write_queue.put((start_register, values, True))

    async def inter_frame_wait(self, is_write=False):
        """Implements inter-frame delay to respect Modbus timing requirements.

        This method calculates the time since the last Modbus request and adds
        a delay if necessary to ensure proper spacing between operations.

        Args:
            is_write (bool): If True, uses a longer delay for write operations.

        Returns:
            None
        """
        # Minimum delay between Modbus operations (milliseconds)
        # Write operations get slightly longer delays for safety
        delay_ms = 100 if is_write else 50

        current_time = time.perf_counter()
        elapsed = (current_time - self._last_modbus_request) * 1000  # Convert to ms

        if elapsed < delay_ms:
            sleep_time = (delay_ms - elapsed) / 1000
            await asyncio.sleep(sleep_time)

        self._last_modbus_request = time.perf_counter()

    async def _async_read_input_register_raw(self, register, count):
        """Raw read input registers without connection check (internal use)."""
        async with self.poll_lock:
            await self.inter_frame_wait()

            # Different pymodbus APIs for TCP vs Serial
            if self.connection_type == CONN_TYPE_TCP:
                # TCP: pass slave as parameter
                result = await self.client.read_input_registers(address=register, count=count, device_id=self.device_id)
            else:
                # Serial: set slave on client, then call without slave parameter
                self.client.slave = self.device_id
                result = await self.client.read_input_registers(address=register, count=count)

            _LOGGER.info(
                f"({self.host}.{self.device_id}) Read Input Registers: register = {register}, count = {count}")

            if result.isError():
                _LOGGER.error(
                    f"({self.host}.{self.device_id}) Failed to read input registers starting at {register}: {result}")
                return None

            self._last_modbus_success = datetime.now(UTC)
            return result.registers

    async def async_read_input_register(self, register, count):
        """Reads input registers from the Modbus device.

        Args:
            register (int): The starting register address to read from.
            count (int): The number of registers to read.

        Returns:
            list: A list of register values if successful, or None if an error occurred.

        Raises:
            Exception: If there is an error during the read operation.
        """
        try:
            await self.connect()
            return await self._async_read_input_register_raw(register, count)
        except Exception as e:
            _LOGGER.error(
                f"({self.host}.{self.device_id}) Exception while reading input registers starting at {register} (count={count}): {str(e)}")
            return None

    async def async_read_holding_register(self, register, count):
        """Reads holding registers from the Modbus device.

        Args:
            register (int): The starting register address to read from.
            count (int): The number of registers to read.

        Returns:
            list: A list of register values if successful, or None if an error occurred.

        Raises:
            Exception: If there is an error during the read operation.
        """
        try:
            await self.connect()
            async with self.poll_lock:
                await self.inter_frame_wait()

                # Different pymodbus APIs for TCP vs Serial
                if self.connection_type == CONN_TYPE_TCP:
                    # TCP: pass slave as parameter
                    result = await self.client.read_holding_registers(address=register, count=count,
                                                                      device_id=self.device_id)
                else:
                    # Serial: set slave on client, then call without slave parameter
                    self.client.slave = self.device_id
                    result = await self.client.read_holding_registers(address=register, count=count)

                _LOGGER.debug(
                    f"({self.host}.{self.device_id}) Read Holding Registers: register = {register}, count = {count}")

                if result.isError():
                    _LOGGER.error(
                        f"({self.host}.{self.device_id}) Failed to read holding registers starting at {register}: {result}")
                    return None

                self._last_modbus_success = datetime.now(UTC)
                return result.registers
        except Exception as e:
            _LOGGER.error(
                f"({self.host}.{self.device_id}) Exception while reading holding registers starting at {register} (count={count}): {str(e)}")
            return None

    async def connect(self):
        """Establishes a connection to the Modbus device.

        Returns:
            bool: True if the connection was successful or already established, False otherwise.

        Raises:
            Exception: If there is an error during the connection attempt.
        """
        if self.connected():
            return True

        try:
            await self.client.connect()
            if self.connected():
                _LOGGER.info(f"✅ ({self.host}.{self.device_id}) Connected to Modbus device")
                self.connect_failures = 0

                if self.serial_number is None:
                    _LOGGER.info(f"serial got from device: {self.serial_number}")
                else:
                    _LOGGER.info(f"serial got from cache: {self.serial_number}")

                return True
            else:
                self.connect_failures += 1
                print(f"DEBUG: Connect failure incremented (connected=False). Count: {self.connect_failures}")
                _LOGGER.debug(
                    f"⚠️ ({self.host}:{self.port}.{self.device_id}) Connection attempt {self.connect_failures} failed")
                return False
        except Exception as e:
            self.connect_failures += 1
            print(f"DEBUG: Connect failure incremented (Exception). Count: {self.connect_failures}")
            _LOGGER.debug(f"❌ ({self.host}.{self.device_id}) Connection error (attempt {self.connect_failures}): {e}")
            return False

    def connected(self):
        """Checks if the Modbus client is currently connected.

        Returns:
            bool: True if the client is connected, False otherwise.
        """
        return self.client.connected if self.client else False

    def disable_connection(self):
        """Disables the Modbus connection.

        This method sets the enabled flag to False, which will cause future
        read/write operations to be skipped.

        Returns:
            None
        """
        self.enabled = False
        _LOGGER.info(f"({self.host}.{self.device_id}) Modbus connection disabled")

    def enable_connection(self):
        """Enables the Modbus connection.

        This method sets the enabled flag to True, allowing read/write operations
        to proceed normally.

        Returns:
            None
        """
        self.enabled = True
        _LOGGER.info(f"({self.host}.{self.device_id}) Modbus connection enabled")

    def close_connection(self):
        """Closes the Modbus connection and releases the client from the manager.

        This method releases the client reference in the ModbusClientManager.
        When all references are released, the manager will close the actual connection.

        Returns:
            None
        """
        manager = ModbusClientManager.get_instance()
        manager.release_client(self.connection_id)
        _LOGGER.info(f"({self.host}.{self.device_id}) Modbus connection closed")

    @property
    def model(self):
        """Returns the inverter model."""
        return self._model

    @property
    def poll_speed(self):
        """Returns a dictionary of poll intervals for different speed categories."""
        return {
            PollSpeed.FAST: self._poll_interval_fast,
            PollSpeed.NORMAL: self._poll_interval_normal,
            PollSpeed.SLOW: self._poll_interval_slow
        }

    @property
    def sw_version(self):
        """Returns the software version of the inverter."""
        return self._sw_version

    @property
    def sensor_groups(self):
        """Returns the list of sensor groups."""
        return self._sensor_groups

    @property
    def derived_sensors(self):
        """Returns the list of derived sensors."""
        return self._derived_sensors

    @property
    def sensor_derived_groups(self):
        """Gets the derived sensor groups associated with this controller."""
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
        """Returns the timestamp of the last successful Modbus operation."""
        return self._last_modbus_success

    @property
    def device_serial_number(self):
        """Gets the device serial number."""
        return self.serial_number

    @property
    def device_info(self):
        """Return device info."""
        # Fallback identifier if serial isn't ready yet

        name = f"{MANUFACTURER} {self.model}"

        return DeviceInfo(
            identifiers={(DOMAIN, self.serial_number)},
            manufacturer=MANUFACTURER,
            model=self.model,
            serial_number=self.serial_number,
            name=name,
            sw_version=self.sw_version,
        )
