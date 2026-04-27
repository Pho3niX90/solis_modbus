import asyncio
import logging
from datetime import UTC, datetime

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.template import is_number
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient

from custom_components.solis_modbus.client_manager import ModbusClientManager
from custom_components.solis_modbus.const import (
    CONN_TYPE_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
    MANUFACTURER,
)
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.data.solis_config import InverterConfig
from custom_components.solis_modbus.helpers import cache_save, notify_register_update
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

_LOGGER = logging.getLogger(__name__)

# Modbus exception codes we treat as address/map issues worth splitting reads (see data_retrieval recovery).
RECOVERABLE_REGISTER_READ_EXCEPTIONS = frozenset({2, 3})


def _exception_code_from_modbus_result(result) -> int | None:
    """Best-effort Modbus exception code from a pymodbus response object."""
    return getattr(result, "exception_code", None)


class ModbusController:
    def __init__(
        self,
        hass,
        inverter_config: InverterConfig,
        sensor_groups: list[SolisSensorGroup] = None,
        derived_sensors: list[SolisDerivedSensor] = None,
        device_id=1,
        fast_poll=5,
        normal_poll=15,
        slow_poll=30,
        connection_type=CONN_TYPE_TCP,
        # TCP parameters
        host=None,
        port=502,
        identification=None,
        # Serial parameters
        serial_port=None,
        baudrate=DEFAULT_BAUDRATE,
        bytesize=DEFAULT_BYTESIZE,
        parity=DEFAULT_PARITY,
        stopbits=DEFAULT_STOPBITS,
        serial_number=None,
    ):
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
        self.serial_number = serial_number
        self.identification = identification

        # Use ModbusClientManager to get shared client, lock, and per-link timing shared by all slaves.
        self._client_manager = ModbusClientManager.get_instance()
        manager = self._client_manager

        # Connection-specific setup
        if connection_type == CONN_TYPE_TCP:
            if not host:
                raise ValueError("host is required for TCP connection")
            self.host = host
            self.port = port
            self.connection_id = f"{host}:{port}"
            self.client: AsyncModbusTcpClient | AsyncModbusSerialClient = manager.get_tcp_client(host, port)
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
            self.client: AsyncModbusTcpClient | AsyncModbusSerialClient = manager.get_serial_client(serial_port, baudrate, bytesize, parity, stopbits)
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
            if not await self.connect():
                _LOGGER.debug(
                    "(%s.%s) Skipping write holding register %s: Modbus client not connected",
                    self.host,
                    self.device_id,
                    register,
                )
                return None
            async with self.poll_lock:
                await self.inter_frame_wait(is_write=True)  # Delay before write
                int_value = int(value)
                int_register = register if is_number(register) else int(register)

                # Different pymodbus APIs for TCP vs Serial
                if self.connection_type == CONN_TYPE_TCP:
                    result = await self.client.write_register(address=int_register, value=int_value, device_id=self.device_id)
                else:
                    self.client.slave = self.device_id
                    result = await self.client.write_register(address=int_register, value=int_value)
                _LOGGER.debug(
                    f"({self.host}.{self.device_id}) Write Holding Register register = {int_register}, value = {value}, int_value = {int_value}: {result}"
                )

                if result.isError():
                    _LOGGER.error(f"({self.host}.{self.device_id}) Failed to write holding register {register} with value {value}: {result}")
                    return None

                cache_save(self.hass, self, int_register, result.registers[0])
                notify_register_update(self.hass, self, int_register, result.registers[0])

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
            if not await self.connect():
                _LOGGER.debug(
                    "(%s.%s) Skipping write holding registers %s-%s: Modbus client not connected",
                    self.host,
                    self.device_id,
                    start_register,
                    start_register + len(values) - 1,
                )
                return None
            async with self.poll_lock:
                await self.inter_frame_wait(is_write=True)  # Delay before write

                # Different pymodbus APIs for TCP vs Serial
                if self.connection_type == CONN_TYPE_TCP:
                    result = await self.client.write_registers(address=start_register, values=values, device_id=self.device_id)
                else:
                    self.client.slave = self.device_id
                    result = await self.client.write_registers(address=start_register, values=values)
                _LOGGER.debug(
                    f"({self.host}.{self.device_id}) Write Holding Register block for {len(values)} registers starting at register = {start_register}"
                )

                if result.isError():
                    _LOGGER.error(f"({self.host}.{self.device_id}) Write block failed: {result}")
                    return None

                for i, value in enumerate(values):
                    reg_addr = start_register + i
                    cache_save(self.hass, self, reg_addr, value)
                    notify_register_update(self.hass, self, reg_addr, value)
                return result
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Failed to write holding registers {start_register}-{start_register + len(values) - 1}: {str(e)}")
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
        """Spacing between Modbus frames on this link (shared across parallel inverters on the same host:port)."""
        await self._client_manager.inter_frame_wait(self.connection_id, is_write=is_write)

    async def _async_read_input_register_raw_detailed(self, register: int, count: int, *, quiet: bool = False) -> tuple[list[int] | None, int | None]:
        """Read input registers under poll_lock. Returns (registers, None) or (None, exception_code|None)."""
        async with self.poll_lock:
            await self.inter_frame_wait()

            if self.connection_type == CONN_TYPE_TCP:
                result = await self.client.read_input_registers(address=register, count=count, device_id=self.device_id)
            else:
                self.client.slave = self.device_id
                result = await self.client.read_input_registers(address=register, count=count)

            _LOGGER.debug(f"({self.host}.{self.device_id}) Read Input Registers: register = {register}, count = {count}")

            if result.isError():
                exc = _exception_code_from_modbus_result(result)
                log_fn = _LOGGER.debug if quiet else _LOGGER.error
                log_fn(f"({self.host}.{self.device_id}) Failed to read input registers starting at {register}: {result}")
                return None, exc

            self._last_modbus_success = datetime.now(UTC)
            return result.registers, None

    async def _async_read_input_register_raw(self, register, count):
        """Raw read input registers without connection check (internal use)."""
        registers, _err = await self._async_read_input_register_raw_detailed(register, count, quiet=False)
        return registers

    async def async_read_input_registers_with_exception(self, register: int, count: int) -> tuple[list[int] | None, int | None]:
        """Like async_read_input_register but returns (registers, exception_code) for recoverable-read logic."""
        try:
            if not await self.connect():
                _LOGGER.debug(
                    "(%s.%s) Skipping input read %s-%s: Modbus client not connected",
                    self.host,
                    self.device_id,
                    register,
                    register + count - 1,
                )
                return None, None
            return await self._async_read_input_register_raw_detailed(register, count, quiet=False)
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Exception while reading input registers starting at {register} (count={count}): {str(e)}")
            return None, None

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
            if not await self.connect():
                _LOGGER.debug(
                    "(%s.%s) Skipping input read %s-%s: Modbus client not connected",
                    self.host,
                    self.device_id,
                    register,
                    register + count - 1,
                )
                return None
            return await self._async_read_input_register_raw(register, count)
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Exception while reading input registers starting at {register} (count={count}): {str(e)}")
            return None

    async def _async_read_holding_register_raw_detailed(self, register: int, count: int, *, quiet: bool = False) -> tuple[list[int] | None, int | None]:
        """Read holding registers under poll_lock. Returns (registers, None) or (None, exception_code|None)."""
        async with self.poll_lock:
            await self.inter_frame_wait()

            if self.connection_type == CONN_TYPE_TCP:
                result = await self.client.read_holding_registers(address=register, count=count, device_id=self.device_id)
            else:
                self.client.slave = self.device_id
                result = await self.client.read_holding_registers(address=register, count=count)

            _LOGGER.debug(f"({self.host}.{self.device_id}) Read Holding Registers: register = {register}, count = {count}")

            if result.isError():
                exc = _exception_code_from_modbus_result(result)
                log_fn = _LOGGER.debug if quiet else _LOGGER.error
                log_fn(f"({self.host}.{self.device_id}) Failed to read holding registers starting at {register}: {result}")
                return None, exc

            self._last_modbus_success = datetime.now(UTC)
            return result.registers, None

    async def _async_read_holding_register_raw(self, register, count):
        registers, _err = await self._async_read_holding_register_raw_detailed(register, count, quiet=False)
        return registers

    async def async_read_holding_registers_with_exception(self, register: int, count: int) -> tuple[list[int] | None, int | None]:
        """Like async_read_holding_register but returns (registers, exception_code) for recoverable-read logic."""
        try:
            if not await self.connect():
                _LOGGER.debug(
                    "(%s.%s) Skipping holding read %s-%s: Modbus client not connected",
                    self.host,
                    self.device_id,
                    register,
                    register + count - 1,
                )
                return None, None
            return await self._async_read_holding_register_raw_detailed(register, count, quiet=False)
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Exception while reading holding registers starting at {register} (count={count}): {str(e)}")
            return None, None

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
            if not await self.connect():
                _LOGGER.debug(
                    "(%s.%s) Skipping holding read %s-%s: Modbus client not connected",
                    self.host,
                    self.device_id,
                    register,
                    register + count - 1,
                )
                return None
            return await self._async_read_holding_register_raw(register, count)
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Exception while reading holding registers starting at {register} (count={count}): {str(e)}")
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

        async def _try_connect() -> bool:
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
                self.connect_failures += 1
                _LOGGER.debug(f"⚠️ ({self.host}:{self.port}.{self.device_id}) Connection attempt {self.connect_failures} failed")
                return False
            except Exception as e:
                self.connect_failures += 1
                _LOGGER.debug(f"❌ ({self.host}.{self.device_id}) Connection error (attempt {self.connect_failures}): {e}")
                return False

        lock = self.poll_lock
        if lock:
            async with lock:
                if self.connected():
                    return True
                return await _try_connect()
        return await _try_connect()

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
            PollSpeed.SLOW: self._poll_interval_slow,
        }

    @property
    def sw_version(self):
        """Returns the software version of the inverter."""
        return self._sw_version

    def replace_sensor_group(self, old_group: SolisSensorGroup, new_groups: list[SolisSensorGroup]) -> None:
        """Replace one sensor group with several (or none) at the same list index."""
        try:
            idx = self._sensor_groups.index(old_group)
        except ValueError:
            _LOGGER.warning("(%s.%s) Sensor group to replace not found in controller list", self.host, self.device_id)
            return
        self._sensor_groups = self._sensor_groups[:idx] + new_groups + self._sensor_groups[idx + 1 :]

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
            float: Shared per-link timestamp from time.perf_counter() after the last inter-frame wait.
        """
        return self._client_manager.get_last_modbus_request(self.connection_id)

    @property
    def last_modbus_success(self):
        """Returns the timestamp of the last successful Modbus operation."""
        return self._last_modbus_success

    @property
    def device_serial_number(self):
        """Gets the device serial number."""
        return self.serial_number

    @property
    def device_identification(self):
        """Gets the device identification string.

        Returns:
            str: The device identification string, or an empty string if not available.
        """
        return self.identification

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
