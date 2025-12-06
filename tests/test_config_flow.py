from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from custom_components.solis_modbus.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield

@pytest.mark.asyncio
async def test_flow_user_success(hass: HomeAssistant):
    """Test user initialized flow with success."""
    with patch(
        "custom_components.solis_modbus.modbus_controller.ModbusController.connect",
        return_value=True,
    ) as mock_connect, patch(
        "custom_components.solis_modbus.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        
        # Valid input
        user_input = {
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1
        }
        
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "Solis: Host 1.2.3.4, Modbus Address 1"
        for key, value in user_input.items():
            assert result["data"][key] == value
        
        mock_connect.assert_called()
        mock_setup_entry.assert_called_once()

@pytest.mark.asyncio
async def test_flow_user_connection_error(hass: HomeAssistant):
    """Test user initialized flow with connection error."""
    with patch(
        "custom_components.solis_modbus.modbus_controller.ModbusController.connect",
        return_value=False,
    ) as mock_connect:
        
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        
        user_input = {
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1
        }
        
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "Cannot connect to Modbus device. Please check your configuration."}

@pytest.mark.asyncio
async def test_flow_user_duplicates(hass: HomeAssistant):
    """Test user initialized flow with duplicate entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4_1",
        data={"host": "1.2.3.4", "slave": 1}
    )
    entry.add_to_hass(hass)
    
    with patch(
        "custom_components.solis_modbus.modbus_controller.ModbusController.connect",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        
        user_input = {
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1
        }
        
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"
