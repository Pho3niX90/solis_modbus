import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from custom_components.solis_modbus.modbus_controller import ModbusController
from custom_components.solis_modbus.data.solis_config import InverterConfig
from custom_components.solis_modbus.data.enums import InverterType

def test_fetch_serial_on_connect():
    async def _test_logic():
        # Mock hass
        hass = MagicMock()
        
        # Mock enums
        mock_inverter_type = MagicMock()
        mock_inverter_type.HYBRID = 1
        
        # Mock InverterConfig
        config = InverterConfig(
            model="Solis-1P5K-4G", 
            wattage=[5000],
            phases=1,
            type=mock_inverter_type.HYBRID
        )

        # Mock ModbusClientManager to avoid singleton issues and actual connections
        with patch("custom_components.solis_modbus.modbus_controller.ModbusClientManager") as MockManager:
            mock_manager_instance = MockManager.get_instance.return_value
            mock_client = AsyncMock()
            mock_manager_instance.get_tcp_client.return_value = mock_client
            mock_manager_instance.get_client_lock.return_value = asyncio.Lock()
            
            # Instantiate controller
            controller = ModbusController(hass, config, host="1.2.3.4", connection_type="tcp")
            
            # Setup mock client behavior
            mock_client.connected = False
            
            async def side_effect_connect():
                mock_client.connected = True
                return True
                
            mock_client.connect = AsyncMock(side_effect=side_effect_connect)
            
            # Mock read_input_registers for serial number
            # Simulate "1402..." -> [12596, 12338, ...]
            # 12596 = 0x3134 ('14')
            # 12338 = 0x3032 ('02')
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            mock_response.registers = [12596, 12338] + [0]*14
            
            mock_client.read_input_registers = AsyncMock(return_value=mock_response)

            # Act: Connect
            print(f"Connecting...")
            connected = await controller.connect()
            print(f"Connected: {connected}")
            print(f"Identification: {controller.identification}")
            print(f"Connected Check: {controller.connected()}")
            
            # Assert
            assert connected is True
            assert controller.serial_number == "1402"
            assert controller.identification == "1402"
            
            # Verify call args
            mock_client.read_input_registers.assert_called_with(address=33004, count=16, device_id=1)

    asyncio.run(_test_logic())

def test_fetch_serial_on_reuse_connection():
    async def _test_logic():
        # Mock hass
        hass = MagicMock()
        
        # Mock enums
        mock_inverter_type = MagicMock()
        mock_inverter_type.HYBRID = 1
        
        # Mock InverterConfig
        config = InverterConfig(
            model="Solis-1P5K-4G", 
            wattage=[5000],
            phases=1,
            type=mock_inverter_type.HYBRID
        )

        # Mock ModbusClientManager
        with patch("custom_components.solis_modbus.modbus_controller.ModbusClientManager") as MockManager:
            mock_manager_instance = MockManager.get_instance.return_value
            mock_client = AsyncMock()
            mock_manager_instance.get_tcp_client.return_value = mock_client
            mock_manager_instance.get_client_lock.return_value = asyncio.Lock()
            
            # Instantiate controller
            controller = ModbusController(hass, config, host="1.2.3.4", connection_type="tcp")
            
            # Setup mock client behavior - ALREADY CONNECTED
            mock_client.connected = True
            mock_client.connect = AsyncMock(return_value=True)
            
            # Mock read_input_registers for serial number
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            mock_response.registers = [12596, 12338] + [0]*14
            mock_client.read_input_registers = AsyncMock(return_value=mock_response)

            # Act: Connect
            connected = await controller.connect()
            
            # Assert
            assert connected is True
            assert controller.serial_number == "1402"
            assert controller.identification == "1402"
            
            # Verify call args - should still be called
            mock_client.read_input_registers.assert_called_with(address=33004, count=16, device_id=1)

    asyncio.run(_test_logic())

def test_fetch_grid_serial_on_connect():
    async def _test_logic():
        # Mock hass
        hass = MagicMock()
        
        # Define mock enum values to match what the controller will see
        # We need to make sure the controller sees these values.
        # Since we are importing ModbusController, it imports InverterType from source.
        # If we didn't mock that module, it's using the real one.
        # So we should generally use the real one or mock it in sys.modules BEFORE import.
        # But we already imported ModbusController at top level.
        # Check if we can just use the real Enum values.
        
        # But wait, looking at the top of this file, we didn't mock 'custom_components.solis_modbus.data.enums'.
        # So it should be using the real one.
        from custom_components.solis_modbus.data.enums import InverterType
        
        # Mock InverterConfig
        config = InverterConfig(
            model="Solis-Grid-10K", 
            wattage=[10000],
            phases=3,
            type=InverterType.GRID
        )
        # Force the type to be GRID just in case
        config.type = InverterType.GRID

        # Mock ModbusClientManager
        with patch("custom_components.solis_modbus.modbus_controller.ModbusClientManager") as MockManager:
            mock_manager_instance = MockManager.get_instance.return_value
            mock_client = AsyncMock()
            mock_manager_instance.get_tcp_client.return_value = mock_client
            mock_manager_instance.get_client_lock.return_value = asyncio.Lock()
            
            # Instantiate controller
            controller = ModbusController(hass, config, host="1.2.3.4", connection_type="tcp")
            
            # Setup mock client behavior
            mock_client.connected = False
            async def side_effect_connect():
                mock_client.connected = True
                return True
            mock_client.connect = AsyncMock(side_effect=side_effect_connect)
            
            # Mock read_input_registers for Grid serial number (3061-3064)
            # Registers: [0x4321, 0x8765, 0xCBA9, 0x0FED]
            # Expected: "123456789ABCDEF0"
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            mock_response.registers = [0x4321, 0x8765, 0xCBA9, 0x0FED]
            mock_client.read_input_registers = AsyncMock(return_value=mock_response)

            # Act: Connect
            connected = await controller.connect()
            
            # Assert
            assert connected is True
            assert controller.serial_number == "123456789ABCDEF0"
            assert controller.identification == "123456789ABCDEF0"
            
            # Verify call args
            mock_client.read_input_registers.assert_called_with(address=3061, count=4, device_id=1)

    asyncio.run(_test_logic())
