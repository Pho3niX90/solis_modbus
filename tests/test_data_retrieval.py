import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from datetime import datetime, UTC

from custom_components.solis_modbus.data_retrieval import DataRetrieval
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup


class TestDataRetrieval(unittest.TestCase):
    """Test the DataRetrieval class."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Home Assistant
        self.hass = MagicMock()
        self.hass.is_running = True
        self.hass.bus.async_fire = MagicMock()
        self.hass.create_task = MagicMock()
        
        # Mock the ModbusController
        self.controller = MagicMock()
        self.controller.host = "192.168.1.100"
        self.controller.slave = 1
        self.controller.enabled = True
        self.controller.connected = MagicMock(return_value=True)
        self.controller.poll_speed = {
            PollSpeed.FAST: 5,
            PollSpeed.NORMAL: 15,
            PollSpeed.SLOW: 30
        }
        
        # Create sensor groups for testing
        self.fast_group = MagicMock(spec=SolisSensorGroup)
        self.fast_group.poll_speed = PollSpeed.FAST
        self.fast_group.start_register = 1000
        self.fast_group.registrar_count = 10
        
        self.normal_group = MagicMock(spec=SolisSensorGroup)
        self.normal_group.poll_speed = PollSpeed.NORMAL
        self.normal_group.start_register = 2000
        self.normal_group.registrar_count = 10
        
        self.slow_group = MagicMock(spec=SolisSensorGroup)
        self.slow_group.poll_speed = PollSpeed.SLOW
        self.slow_group.start_register = 3000
        self.slow_group.registrar_count = 10
        
        self.once_group = MagicMock(spec=SolisSensorGroup)
        self.once_group.poll_speed = PollSpeed.ONCE
        self.once_group.start_register = 4000
        self.once_group.registrar_count = 10
        
        # Set up the controller's sensor groups
        self.controller.sensor_groups = [
            self.fast_group,
            self.normal_group,
            self.slow_group,
            self.once_group
        ]
        
        # Create the DataRetrieval instance
        with patch('custom_components.solis_modbus.data_retrieval.async_track_time_interval') as self.mock_track_time:
            self.data_retrieval = DataRetrieval(self.hass, self.controller)
    
    async def test_check_connection_already_connected(self):
        """Test check_connection when already connected."""
        self.data_retrieval.connection_check = False
        self.controller.connected.return_value = True
        
        await self.data_retrieval.check_connection()
        
        self.hass.bus.async_fire.assert_called_once()
        self.controller.connected.assert_called_once()
        # Should not attempt to connect if already connected
        self.controller.connect.assert_not_called()
    
    async def test_check_connection_not_connected(self):
        """Test check_connection when not connected."""
        self.data_retrieval.connection_check = False
        self.controller.connected.return_value = False
        self.controller.connect = AsyncMock(return_value=True)
        
        await self.data_retrieval.check_connection()
        
        self.hass.bus.async_fire.assert_called_once()
        self.controller.connected.assert_called()
        self.controller.connect.assert_called_once()
    
    async def test_poll_controller(self):
        """Test poll_controller method."""
        # Mock the check_connection method
        self.data_retrieval.check_connection = AsyncMock()
        
        # Call the method
        await self.data_retrieval.poll_controller()
        
        # Verify check_connection was called
        self.data_retrieval.check_connection.assert_called_once()
        
        # Verify time interval tracking was set up
        self.assertEqual(3, self.mock_track_time.call_count)
        
        # Verify controller's process_write_queue was started
        self.hass.create_task.assert_called_once_with(self.controller.process_write_queue())
    
    async def test_modbus_update_all(self):
        """Test modbus_update_all method."""
        # Mock the update methods
        self.data_retrieval.modbus_update_fast = AsyncMock()
        self.data_retrieval.modbus_update_normal = AsyncMock()
        self.data_retrieval.modbus_update_slow = AsyncMock()
        
        # Call the method
        await self.data_retrieval.modbus_update_all()
        
        # Verify all update methods were called
        self.data_retrieval.modbus_update_fast.assert_called_once()
        self.data_retrieval.modbus_update_normal.assert_called_once()
        self.data_retrieval.modbus_update_slow.assert_called_once()
    
    async def test_modbus_update_fast(self):
        """Test modbus_update_fast method."""
        # Mock the get_modbus_updates method
        self.data_retrieval.get_modbus_updates = AsyncMock()
        
        # Call the method
        await self.data_retrieval.modbus_update_fast()
        
        # Verify get_modbus_updates was called with fast groups
        self.data_retrieval.get_modbus_updates.assert_called_once()
        args, kwargs = self.data_retrieval.get_modbus_updates.call_args
        self.assertEqual(PollSpeed.FAST, args[1])
        
        # Verify event was fired
        self.hass.bus.async_fire.assert_called_once()
    
    async def test_modbus_update_normal(self):
        """Test modbus_update_normal method."""
        # Mock the get_modbus_updates method
        self.data_retrieval.get_modbus_updates = AsyncMock()
        
        # Call the method
        await self.data_retrieval.modbus_update_normal()
        
        # Verify get_modbus_updates was called with normal groups
        self.data_retrieval.get_modbus_updates.assert_called_once()
        args, kwargs = self.data_retrieval.get_modbus_updates.call_args
        self.assertEqual(PollSpeed.NORMAL, args[1])
    
    async def test_modbus_update_slow(self):
        """Test modbus_update_slow method."""
        # Mock the get_modbus_updates method
        self.data_retrieval.get_modbus_updates = AsyncMock()
        
        # Call the method
        await self.data_retrieval.modbus_update_slow()
        
        # Verify get_modbus_updates was called with slow groups
        self.data_retrieval.get_modbus_updates.assert_called_once()
        args, kwargs = self.data_retrieval.get_modbus_updates.call_args
        self.assertEqual(PollSpeed.SLOW, args[1])
    
    async def test_get_modbus_updates_controller_disabled(self):
        """Test get_modbus_updates when controller is disabled."""
        self.controller.enabled = False
        
        await self.data_retrieval.get_modbus_updates([self.fast_group], PollSpeed.FAST)
        
        # Should return early without doing anything
        self.controller.async_read_holding_register.assert_not_called()
        self.controller.async_read_input_register.assert_not_called()
    
    async def test_get_modbus_updates_controller_not_connected(self):
        """Test get_modbus_updates when controller is not connected."""
        self.controller.enabled = True
        self.controller.connected.return_value = False
        
        await self.data_retrieval.get_modbus_updates([self.fast_group], PollSpeed.FAST)
        
        # Should return early without doing anything
        self.controller.async_read_holding_register.assert_not_called()
        self.controller.async_read_input_register.assert_not_called()
    
    async def test_get_modbus_updates_success(self):
        """Test successful get_modbus_updates."""
        # Set up the controller to return register values
        self.controller.async_read_holding_register = AsyncMock(return_value=[42, 43])
        self.controller.async_read_input_register = AsyncMock(return_value=[44, 45])
        
        # Call the method with a holding register group
        self.fast_group.start_register = 40000  # Holding register
        await self.data_retrieval.get_modbus_updates([self.fast_group], PollSpeed.FAST)
        
        # Verify the correct read method was called
        self.controller.async_read_holding_register.assert_called_once()
        self.controller.async_read_input_register.assert_not_called()
        
        # Call the method with an input register group
        self.controller.async_read_holding_register.reset_mock()
        self.controller.async_read_input_register.reset_mock()
        self.fast_group.start_register = 30000  # Input register
        await self.data_retrieval.get_modbus_updates([self.fast_group], PollSpeed.FAST)
        
        # Verify the correct read method was called
        self.controller.async_read_holding_register.assert_not_called()
        self.controller.async_read_input_register.assert_called_once()


if __name__ == "__main__":
    unittest.main()