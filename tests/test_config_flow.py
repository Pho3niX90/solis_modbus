from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solis_modbus.const import CONN_TYPE_TCP, DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.mark.asyncio
async def test_flow_user_success(hass: HomeAssistant):
    """Test user initialized flow with success."""
    with (
        patch(
            "custom_components.solis_modbus.modbus_controller.ModbusController.connect",
            return_value=True,
        ) as mock_connect,
        patch(
            "custom_components.solis_modbus.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        # Step 1: Select connection type
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={"connection_type": CONN_TYPE_TCP})

        # Step 2: Configure connection details
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "config"

        config_input = {
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1,
            "model": "S6-EH1P",
            "connection": "S2_WL_ST",
            "has_v2": True,
            "has_pv": True,
            "has_ac_coupling": False,
            "has_battery": True,
            "has_hv_battery": False,
            "has_generator": False,
            "inverter_serial": "sn123",  # Lowercase input
        }

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=config_input)

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        # CHANGED: The title is now based on the serial number
        assert result["title"] == "Solis: SN123"

        # Verify data
        assert result["data"]["connection_type"] == CONN_TYPE_TCP

        # CHANGED: Verify Serial was converted to UPPERCASE
        assert result["data"]["inverter_serial"] == "SN123"

        # Verify other fields
        assert result["data"]["host"] == "1.2.3.4"
        assert result["data"]["slave"] == 1

        mock_connect.assert_called()
        mock_setup_entry.assert_called_once()


@pytest.mark.asyncio
async def test_flow_user_connection_error(hass: HomeAssistant):
    """Test user initialized flow with connection error."""
    with patch(
        "custom_components.solis_modbus.modbus_controller.ModbusController.connect",
        return_value=False,
    ):
        # Step 1: Select connection type
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={"connection_type": CONN_TYPE_TCP})

        # Step 2: Configure connection details
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "config"

        config_input = {
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1,
            "model": "S6-EH1P",
            "connection": "S2_WL_ST",
            "has_v2": True,
            "has_pv": True,
            "has_ac_coupling": False,
            "has_battery": True,
            "has_hv_battery": False,
            "has_generator": False,
            "inverter_serial": "sn123",
        }

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=config_input)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "Cannot connect to Modbus device. Please check your configuration."}


@pytest.mark.asyncio
async def test_flow_user_duplicates(hass: HomeAssistant):
    """Test user initialized flow with duplicate entry."""

    # CHANGED: Setup existing entry with SERIAL NUMBER as unique_id
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN123",  # Matches uppercase serial
        data={"host": "1.2.3.4", "slave": 1, "connection_type": CONN_TYPE_TCP, "inverter_serial": "SN123"},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.solis_modbus.modbus_controller.ModbusController.connect",
        return_value=True,
    ):
        # Step 1: Select connection type
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={"connection_type": CONN_TYPE_TCP})

        # Step 2: Configure connection details (duplicate config)
        config_input = {
            "host": "1.2.3.4",  # Even if host is same
            "port": 502,
            "slave": 1,
            "model": "S6-EH1P",
            "connection": "S2_WL_ST",
            "has_generator": False,
            "inverter_serial": "sn123",  # Try adding same serial (lowercase)
        }

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=config_input)

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_options_flow_suggestions_use_merged_data_and_options(hass: HomeAssistant):
    """Feature toggles live in entry.data until options are saved; the form must pre-fill from data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SNOPT1",
        version=3,
        data={
            "connection_type": CONN_TYPE_TCP,
            "inverter_serial": "SNOPT1",
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1,
            "model": "S6-EH1P",
            "connection": "S2_WL_ST",
            "has_v2": True,
            "has_pv": True,
            "has_ac_coupling": True,
            "has_battery": True,
            "has_hv_battery": False,
            "has_generator": True,
            "poll_interval_fast": 10,
            "poll_interval_normal": 15,
            "poll_interval_slow": 30,
        },
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    schema = result["data_schema"]
    ac_key = next(k for k in schema.schema if getattr(k, "schema", None) == "has_ac_coupling")
    gen_key = next(k for k in schema.schema if getattr(k, "schema", None) == "has_generator")
    assert (ac_key.description or {}).get("suggested_value") is True
    assert (gen_key.description or {}).get("suggested_value") is True

    user_input = {
        "poll_interval_fast": 10,
        "poll_interval_normal": 15,
        "poll_interval_slow": 30,
        "model": "S6-EH1P",
        "connection": "S2_WL_ST",
        "has_v2": True,
        "has_pv": True,
        "has_ac_coupling": True,
        "has_battery": True,
        "has_hv_battery": False,
        "has_generator": True,
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input=user_input)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options["has_ac_coupling"] is True
    assert entry.options["has_generator"] is True
