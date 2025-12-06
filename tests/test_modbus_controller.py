import unittest
from unittest.mock import MagicMock, patch, AsyncMock, call
from unittest import IsolatedAsyncioTestCase
import asyncio
from datetime import datetime, UTC

from custom_components.solis_modbus.modbus_controller import ModbusController
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.const import DOMAIN, VALUES, REGISTER, VALUE, CONTROLLER, SLAVE


class TestModbusController(IsolatedAsyncioTestCase):
    """Test the ModbusController class."""

    def setUp(self):
        """Set up test fixtures."""
        self.hass = MagicMock()
        self.hass.bus.async_fire = MagicMock()
        self.hass.data = {DOMAIN: {VALUES: {}}}
        
        # Mock the inverter config
        self.inverter_config = MagicMock()
        self.inverter_config.model = "Test Model"
        
        # Create a patcher for ModbusClientManager
        self.manager_patcher = patch('custom_components.solis_modbus.modbus_controller.ModbusClientManager')
        self.mock_manager_data = self.manager_patcher.start()
        self.mock_manager = MagicMock()
        self.mock_manager_data.get_instance.return_value = self.mock_manager
        
        # Mock Client
        self.mock_client = MagicMock()
        self.mock_manager.get_client.return_value = self.mock_client

        # Mock Lock
        self.mock_lock = MagicMock()
        self.mock_lock.__aenter__ = AsyncMock(return_value=None)
        self.mock_lock.__aexit__ = AsyncMock(return_value=None)
        self.mock_manager.get_client_lock.return_value = self.mock_lock
        
        # Create the controller
        self.controller = ModbusController(
            hass=self.hass,
            host="192.168.1.100",
            inverter_config=self.inverter_config,
            device_id=1,
            port=502,
            fast_poll=5,
            normal_poll=15,
            slow_poll=30
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.manager_patcher.stop()
    
    async def test_connect_success(self):
        """Test successful connection."""
        self.mock_client.connect = AsyncMock(return_value=True)
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
        self.mock_client.read_input_registers = AsyncMock(return_value=mock_result)
        
        result = await self.controller.async_read_input_register(100)
        
        self.assertEqual([42], result)
        self.mock_client.read_input_registers.assert_called_once_with(address=100, count=1, device_id=1)
    
    async def test_async_read_input_register_failure(self):
        """Test failed read of input register."""
        self.mock_client.connected = True
        self.mock_client.read_input_registers = AsyncMock(side_effect=Exception("Test error"))
        
        result = await self.controller.async_read_input_register(100)
        
        self.assertIsNone(result)
        self.mock_client.read_input_registers.assert_called_once_with(address=100, count=1, device_id=1)
    
    async def test_async_read_holding_register_success(self):
        """Test successful read of holding register."""
        self.mock_client.connected = True
        mock_result = MagicMock()
        mock_result.registers = [42]
        self.mock_client.read_holding_registers = AsyncMock(return_value=mock_result)
        
        result = await self.controller.async_read_holding_register(100)
        
        self.assertEqual([42], result)
        self.mock_client.read_holding_registers.assert_called_once_with(address=100, count=1, device_id=1)
    
    async def test_async_read_holding_register_failure(self):
        """Test failed read of holding register."""
        self.mock_client.connected = True
        self.mock_client.read_holding_registers = AsyncMock(side_effect=Exception("Test error"))
        
        result = await self.controller.async_read_holding_register(100)
        
        self.assertIsNone(result)
        self.mock_client.read_holding_registers.assert_called_once_with(address=100, count=1, device_id=1)
    
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

    async def test_execute_write_holding_registers_caches_response_values(self):
        """Ensure write responses update the cache and fire events."""
        self.mock_client.connected = True
        mock_result = MagicMock()
        mock_result.isError.return_value = False
        mock_result.registers = [10, 11]
        self.mock_client.write_registers = AsyncMock(return_value=mock_result)
        self.hass.bus.async_fire.reset_mock()

        await self.controller._execute_write_holding_registers(200, [10, 11])

        self.mock_client.write_registers.assert_awaited_once_with(address=200, values=[10, 11], device_id=1)
        self.assertEqual(self.hass.data[DOMAIN][VALUES]["200"], 10)
        self.assertEqual(self.hass.data[DOMAIN][VALUES]["201"], 11)
        self.assertEqual(
            self.hass.bus.async_fire.call_args_list,
            [
                call(DOMAIN, {REGISTER: 200, VALUE: 10, CONTROLLER: "192.168.1.100", SLAVE: 1}),
                call(DOMAIN, {REGISTER: 201, VALUE: 11, CONTROLLER: "192.168.1.100", SLAVE: 1}),
            ],
        )

    async def test_execute_write_holding_registers_falls_back_to_requested_values(self):
        """Fallback to the requested payload when the driver omits registers."""
        self.mock_client.connected = True
        mock_result = MagicMock()
        mock_result.isError.return_value = False
        mock_result.registers = None
        self.mock_client.write_registers = AsyncMock(return_value=mock_result)

        await self.controller._execute_write_holding_registers(300, [21])

        self.assertEqual(self.hass.data[DOMAIN][VALUES]["300"], 21)
        self.hass.bus.async_fire.assert_called_once_with(
            DOMAIN, {REGISTER: 300, VALUE: 21, CONTROLLER: "192.168.1.100", SLAVE: 1}
        )
    
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
        # Check that release_client was called on the manager
        self.mock_manager.release_client.assert_called_once_with("192.168.1.100", 502)
    
    async def test_enable_connection(self):
        """Test enabling the connection."""
        self.mock_client.connect = AsyncMock(return_value=True)
        self.mock_client.connected = False
        
        await self.controller.enable_connection()
        
        self.assertTrue(self.controller.enabled)
        self.mock_client.connect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
