import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from unittest import IsolatedAsyncioTestCase
import asyncio
from datetime import datetime, UTC

from custom_components.solis_modbus.modbus_controller import ModbusController
from custom_components.solis_modbus.const import (
    CONN_TYPE_TCP, CONN_TYPE_SERIAL,
    DEFAULT_BAUDRATE, DEFAULT_BYTESIZE, DEFAULT_PARITY, DEFAULT_STOPBITS
)
from custom_components.solis_modbus.data.enums import PollSpeed


class TestModbusControllerTCP(IsolatedAsyncioTestCase):
    """Test the ModbusController class with TCP connection."""

    def setUp(self):
        """Set up test fixtures."""
        self.hass = MagicMock()
        self.hass.bus.async_fire = MagicMock()

        # Mock the inverter config
        self.inverter_config = MagicMock()
        self.inverter_config.model = "Test Model"

        # Create a patcher for ModbusClientManager
        self.manager_patcher = patch('custom_components.solis_modbus.modbus_controller.ModbusClientManager')
        self.mock_manager_class = self.manager_patcher.start()
        self.mock_manager = MagicMock()
        self.mock_manager_class.get_instance.return_value = self.mock_manager

        # Mock TCP Client
        self.mock_client = MagicMock()
        self.mock_manager.get_tcp_client.return_value = self.mock_client

        # Mock Lock
        self.mock_lock = MagicMock()
        self.mock_lock.__aenter__ = AsyncMock(return_value=None)
        self.mock_lock.__aexit__ = AsyncMock(return_value=None)
        self.mock_manager.get_client_lock.return_value = self.mock_lock

        # Create the controller with TCP connection
        self.controller = ModbusController(
            hass=self.hass,
            connection_type=CONN_TYPE_TCP,
            host="192.168.1.100",
            port=502,
            inverter_config=self.inverter_config,
            device_id=1,
            fast_poll=5,
            normal_poll=15,
            slow_poll=30
        )

    def tearDown(self):
        """Tear down test fixtures."""
        self.manager_patcher.stop()

    async def test_connect_success(self):
        """Test successful connection."""
        async def connect_side_effect():
            self.mock_client.connected = True
            return True

        self.mock_client.connect = AsyncMock(side_effect=connect_side_effect)
        self.mock_client.connected = False

        result = await self.controller.connect()

        self.assertTrue(result)
        self.mock_client.connect.assert_called_once()
        self.assertEqual(0, self.controller.connect_failures)

    async def test_connect_failure(self):
        """Test connection failure."""
        self.mock_client.connect = AsyncMock(return_value=False)
        self.mock_client.connected = False

        result = await self.controller.connect()

        self.assertFalse(result)
        self.mock_client.connect.assert_called_once()
        self.assertEqual(1, self.controller.connect_failures)

    async def test_connect_already_connected(self):
        """Test connection when already connected."""
        self.mock_client.connect = AsyncMock()
        self.mock_client.connected = True

        result = await self.controller.connect()

        self.assertTrue(result)
        self.mock_client.connect.assert_not_called()

    async def test_async_read_input_register_success(self):
        """Test successful read of input register."""
        self.mock_client.connected = True
        mock_result = MagicMock()
        mock_result.registers = [42]
        mock_result.isError = MagicMock(return_value=False)
        self.mock_client.read_input_registers = AsyncMock(return_value=mock_result)

        result = await self.controller.async_read_input_register(100, 1)

        self.assertEqual([42], result)
        self.mock_client.read_input_registers.assert_called_once_with(address=100, count=1, slave=1)

    async def test_async_read_input_register_failure(self):
        """Test failed read of input register."""
        self.mock_client.connected = True
        self.mock_client.read_input_registers = AsyncMock(side_effect=Exception("Test error"))

        result = await self.controller.async_read_input_register(100, 1)

        self.assertIsNone(result)

    async def test_async_read_holding_register_success(self):
        """Test successful read of holding register."""
        self.mock_client.connected = True
        mock_result = MagicMock()
        mock_result.registers = [42]
        mock_result.isError = MagicMock(return_value=False)
        self.mock_client.read_holding_registers = AsyncMock(return_value=mock_result)

        result = await self.controller.async_read_holding_register(100, 1)

        self.assertEqual([42], result)
        self.mock_client.read_holding_registers.assert_called_once_with(address=100, count=1, slave=1)

    async def test_async_read_holding_register_failure(self):
        """Test failed read of holding register."""
        self.mock_client.connected = True
        self.mock_client.read_holding_registers = AsyncMock(side_effect=Exception("Test error"))

        result = await self.controller.async_read_holding_register(100, 1)

        self.assertIsNone(result)

    async def test_async_write_holding_register(self):
        """Test queuing a write to a holding register."""
        # Mock the write queue
        self.controller.write_queue = MagicMock()
        self.controller.write_queue.put = AsyncMock()

        await self.controller.async_write_holding_register(100, 42)

        self.controller.write_queue.put.assert_called_once_with((100, 42, False))

    async def test_async_write_holding_registers(self):
        """Test queuing a write to multiple holding registers."""
        # Mock the write queue
        self.controller.write_queue = MagicMock()
        self.controller.write_queue.put = AsyncMock()

        await self.controller.async_write_holding_registers(100, [42, 43])

        self.controller.write_queue.put.assert_called_once_with((100, [42, 43], True))

    def test_poll_speed(self):
        """Test the poll_speed property."""
        expected = {
            PollSpeed.FAST: 5,
            PollSpeed.NORMAL: 15,
            PollSpeed.SLOW: 30
        }
        self.assertEqual(expected, self.controller.poll_speed)

    def test_model(self):
        """Test the model property."""
        self.assertEqual("Test Model", self.controller.model)

    def test_connected(self):
        """Test the connected method."""
        self.mock_client.connected = True
        self.assertTrue(self.controller.connected())

        self.mock_client.connected = False
        self.assertFalse(self.controller.connected())

    def test_disable_connection(self):
        """Test disabling the connection."""
        self.controller.disable_connection()
        self.assertFalse(self.controller.enabled)

    async def test_enable_connection(self):
        """Test enabling the connection."""
        self.controller.enable_connection()
        self.assertTrue(self.controller.enabled)


class TestModbusControllerSerial(IsolatedAsyncioTestCase):
    """Test the ModbusController class with Serial connection."""

    def setUp(self):
        """Set up test fixtures."""
        self.hass = MagicMock()
        self.hass.bus.async_fire = MagicMock()

        # Mock the inverter config
        self.inverter_config = MagicMock()
        self.inverter_config.model = "Test Model"

        # Create a patcher for ModbusClientManager
        self.manager_patcher = patch('custom_components.solis_modbus.modbus_controller.ModbusClientManager')
        self.mock_manager_class = self.manager_patcher.start()
        self.mock_manager = MagicMock()
        self.mock_manager_class.get_instance.return_value = self.mock_manager

        # Mock Serial Client
        self.mock_client = MagicMock()
        self.mock_manager.get_serial_client.return_value = self.mock_client

        # Mock Lock
        self.mock_lock = MagicMock()
        self.mock_lock.__aenter__ = AsyncMock(return_value=None)
        self.mock_lock.__aexit__ = AsyncMock(return_value=None)
        self.mock_manager.get_client_lock.return_value = self.mock_lock

        # Create the controller with Serial connection
        self.controller = ModbusController(
            hass=self.hass,
            connection_type=CONN_TYPE_SERIAL,
            serial_port="/dev/ttyUSB0",
            baudrate=DEFAULT_BAUDRATE,
            bytesize=DEFAULT_BYTESIZE,
            parity=DEFAULT_PARITY,
            stopbits=DEFAULT_STOPBITS,
            inverter_config=self.inverter_config,
            device_id=1,
            fast_poll=5,
            normal_poll=15,
            slow_poll=30
        )

    def tearDown(self):
        """Tear down test fixtures."""
        self.manager_patcher.stop()

    def test_serial_port_attribute(self):
        """Test that serial port is set correctly."""
        self.assertEqual("/dev/ttyUSB0", self.controller.serial_port)
        self.assertEqual("/dev/ttyUSB0", self.controller.connection_id)

    def test_serial_parameters(self):
        """Test that serial parameters are set correctly."""
        self.assertEqual(DEFAULT_BAUDRATE, self.controller.baudrate)
        self.assertEqual(DEFAULT_BYTESIZE, self.controller.bytesize)
        self.assertEqual(DEFAULT_PARITY, self.controller.parity)
        self.assertEqual(DEFAULT_STOPBITS, self.controller.stopbits)

    def test_connection_id_serial(self):
        """Test that connection_id is set to serial_port for Serial connections."""
        self.assertEqual("/dev/ttyUSB0", self.controller.connection_id)

    async def test_connect_success(self):
        """Test successful connection."""
        async def connect_side_effect():
            self.mock_client.connected = True
            return True

        self.mock_client.connect = AsyncMock(side_effect=connect_side_effect)
        self.mock_client.connected = False

        result = await self.controller.connect()

        self.assertTrue(result)
        self.mock_client.connect.assert_called_once()
        self.assertEqual(0, self.controller.connect_failures)

    async def test_connect_failure(self):
        """Test connection failure."""
        self.mock_client.connect = AsyncMock(return_value=False)
        self.mock_client.connected = False

        result = await self.controller.connect()

        self.assertFalse(result)
        self.mock_client.connect.assert_called_once()
        self.assertEqual(1, self.controller.connect_failures)

    async def test_connect_already_connected(self):
        """Test connection when already connected."""
        self.mock_client.connect = AsyncMock()
        self.mock_client.connected = True

        result = await self.controller.connect()

        self.assertTrue(result)
        self.mock_client.connect.assert_not_called()

    async def test_async_read_input_register_success(self):
        """Test successful read of input register."""
        self.mock_client.connected = True
        mock_result = MagicMock()
        mock_result.registers = [42]
        mock_result.isError = MagicMock(return_value=False)
        self.mock_client.read_input_registers = AsyncMock(return_value=mock_result)

        result = await self.controller.async_read_input_register(100, 1)

        self.assertEqual([42], result)
        self.mock_client.read_input_registers.assert_called_once_with(address=100, count=1, slave=1)

    async def test_async_read_input_register_failure(self):
        """Test failed read of input register."""
        self.mock_client.connected = True
        self.mock_client.read_input_registers = AsyncMock(side_effect=Exception("Test error"))

        result = await self.controller.async_read_input_register(100, 1)

        self.assertIsNone(result)

    async def test_async_read_holding_register_success(self):
        """Test successful read of holding register."""
        self.mock_client.connected = True
        mock_result = MagicMock()
        mock_result.registers = [42]
        mock_result.isError = MagicMock(return_value=False)
        self.mock_client.read_holding_registers = AsyncMock(return_value=mock_result)

        result = await self.controller.async_read_holding_register(100, 1)

        self.assertEqual([42], result)
        self.mock_client.read_holding_registers.assert_called_once_with(address=100, count=1, slave=1)

    async def test_async_read_holding_register_failure(self):
        """Test failed read of holding register."""
        self.mock_client.connected = True
        self.mock_client.read_holding_registers = AsyncMock(side_effect=Exception("Test error"))

        result = await self.controller.async_read_holding_register(100, 1)

        self.assertIsNone(result)

    async def test_async_write_holding_register(self):
        """Test queuing a write to a holding register."""
        # Mock the write queue
        self.controller.write_queue = MagicMock()
        self.controller.write_queue.put = AsyncMock()

        await self.controller.async_write_holding_register(100, 42)

        self.controller.write_queue.put.assert_called_once_with((100, 42, False))

    async def test_async_write_holding_registers(self):
        """Test queuing a write to multiple holding registers."""
        # Mock the write queue
        self.controller.write_queue = MagicMock()
        self.controller.write_queue.put = AsyncMock()

        await self.controller.async_write_holding_registers(100, [42, 43])

        self.controller.write_queue.put.assert_called_once_with((100, [42, 43], True))

    def test_poll_speed(self):
        """Test the poll_speed property."""
        expected = {
            PollSpeed.FAST: 5,
            PollSpeed.NORMAL: 15,
            PollSpeed.SLOW: 30
        }
        self.assertEqual(expected, self.controller.poll_speed)

    def test_model(self):
        """Test the model property."""
        self.assertEqual("Test Model", self.controller.model)

    def test_connected(self):
        """Test the connected method."""
        self.mock_client.connected = True
        self.assertTrue(self.controller.connected())

        self.mock_client.connected = False
        self.assertFalse(self.controller.connected())

    def test_disable_connection(self):
        """Test disabling the connection."""
        self.controller.disable_connection()
        self.assertFalse(self.controller.enabled)

    async def test_enable_connection(self):
        """Test enabling the connection."""
        self.controller.enable_connection()
        self.assertTrue(self.controller.enabled)


class TestModbusControllerInitialization(unittest.TestCase):
    """Test ModbusController initialization for different connection types."""

    def setUp(self):
        """Set up test fixtures."""
        self.hass = MagicMock()
        self.inverter_config = MagicMock()
        self.inverter_config.model = "Test Model"

        # Patch ModbusClientManager
        self.manager_patcher = patch('custom_components.solis_modbus.modbus_controller.ModbusClientManager')
        self.mock_manager_class = self.manager_patcher.start()
        self.mock_manager = MagicMock()
        self.mock_manager_class.get_instance.return_value = self.mock_manager

        # Mock clients
        self.mock_tcp_client = MagicMock()
        self.mock_serial_client = MagicMock()
        self.mock_manager.get_tcp_client.return_value = self.mock_tcp_client
        self.mock_manager.get_serial_client.return_value = self.mock_serial_client
        self.mock_manager.get_client_lock.return_value = MagicMock()

    def tearDown(self):
        """Tear down test fixtures."""
        self.manager_patcher.stop()

    def test_tcp_client_initialization(self):
        """Test that TCP client is initialized correctly."""
        controller = ModbusController(
            hass=self.hass,
            connection_type=CONN_TYPE_TCP,
            host="192.168.1.100",
            port=502,
            inverter_config=self.inverter_config
        )

        self.assertEqual(CONN_TYPE_TCP, controller.connection_type)
        self.assertEqual("192.168.1.100", controller.host)
        self.assertEqual(502, controller.port)
        self.assertEqual("192.168.1.100:502", controller.connection_id)
        self.mock_manager.get_tcp_client.assert_called_once_with("192.168.1.100", 502)

    def test_serial_client_initialization(self):
        """Test that Serial client is initialized correctly."""
        controller = ModbusController(
            hass=self.hass,
            connection_type=CONN_TYPE_SERIAL,
            serial_port="/dev/ttyUSB0",
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1,
            inverter_config=self.inverter_config
        )

        self.assertEqual(CONN_TYPE_SERIAL, controller.connection_type)
        self.assertEqual("/dev/ttyUSB0", controller.serial_port)
        self.assertEqual(9600, controller.baudrate)
        self.assertEqual("/dev/ttyUSB0", controller.connection_id)
        self.mock_manager.get_serial_client.assert_called_once_with("/dev/ttyUSB0", 9600, 8, 'N', 1)

    def test_tcp_without_host_raises_error(self):
        """Test that TCP connection without host raises ValueError."""
        with self.assertRaises(ValueError) as context:
            ModbusController(
                hass=self.hass,
                connection_type=CONN_TYPE_TCP,
                port=502,
                inverter_config=self.inverter_config
            )
        self.assertIn("host is required", str(context.exception))

    def test_serial_without_port_raises_error(self):
        """Test that Serial connection without serial_port raises ValueError."""
        with self.assertRaises(ValueError) as context:
            ModbusController(
                hass=self.hass,
                connection_type=CONN_TYPE_SERIAL,
                baudrate=9600,
                inverter_config=self.inverter_config
            )
        self.assertIn("serial_port is required", str(context.exception))


if __name__ == "__main__":
    unittest.main()
