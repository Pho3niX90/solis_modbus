from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST
from custom_components.solis_modbus.const import DOMAIN
from tests.test_integration_setup import auto_enable_custom_integrations

@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.device_id = 1
    controller.async_write_holding_register = AsyncMock(return_value=None)
    return controller

@pytest.mark.asyncio
async def test_service_write_holding_register(hass: HomeAssistant, mock_controller):
    """Test solis_write_holding_register service."""
    from custom_components.solis_modbus.const import CONTROLLER
    
    # Store controller
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][CONTROLLER] = {"1.2.3.4_1": mock_controller}
    
    with patch("custom_components.solis_modbus.get_controller", return_value=mock_controller):
             
        # Register the services (requires setting up the integration or manually registering)
        from custom_components.solis_modbus import async_setup
        await async_setup(hass, {})
        
        # Call service
        await hass.services.async_call(
            DOMAIN,
            "solis_write_holding_register",
            {"address": 123, "value": 456, "host": "1.2.3.4"},
            blocking=True
        )
        
        mock_controller.async_write_holding_register.assert_called_with(123, 456)

@pytest.mark.asyncio
async def test_service_write_holding_register_no_host(hass: HomeAssistant, mock_controller):
    """Test solis_write_holding_register service without host (broadcast to all)."""
    from custom_components.solis_modbus.const import CONTROLLER
    
    # Store controller in hass.data
    hass.data[DOMAIN] = {CONTROLLER: {"1.2.3.4_1": mock_controller}}
    
    from custom_components.solis_modbus import async_setup
    await async_setup(hass, {})
    
    await hass.services.async_call(
        DOMAIN,
        "solis_write_holding_register",
        {"address": 123, "value": 456},
        blocking=True
    )
    
    mock_controller.async_write_holding_register.assert_called_with(123, 456)

@pytest.mark.asyncio
async def test_service_set_time(hass: HomeAssistant):
    """Test solis_write_time service."""
    from custom_components.solis_modbus.const import TIME_ENTITIES
    from datetime import time
    
    mock_entity = MagicMock()
    mock_entity.entity_id = "time.test_time"
    mock_entity.async_set_value = MagicMock(return_value=None)
    # async_set_value must be awaitable
    async def async_set_value(val):
        pass
    mock_entity.async_set_value = MagicMock(side_effect=async_set_value)
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][TIME_ENTITIES] = [mock_entity]
    
    from custom_components.solis_modbus import async_setup
    await async_setup(hass, {})
    
    await hass.services.async_call(
        DOMAIN,
        "solis_write_time",
        {"entity_id": "time.test_time", "time": "12:30:00"},
        blocking=True
    )
    
    # Check if called with correct time object
    mock_entity.async_set_value.assert_called()
    call_args = mock_entity.async_set_value.call_args
    assert call_args[0][0] == time(12, 30, 0)
