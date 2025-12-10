from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solis_modbus.const import DOMAIN, CONTROLLER


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.mark.asyncio
async def test_setup_entry(hass: HomeAssistant):
    """Test setting up the integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN123456",  # Match the serial to skip deferred migration logic
        data={
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1,
            "inverter_serial": "SN123456",
            "model": "S6-EH1P",
            "poll_interval_fast": 10,
            "poll_interval_normal": 15,
            "poll_interval_slow": 30
        },
        title="Solis Inverter"
    )
    config_entry.add_to_hass(hass)

    with patch("custom_components.solis_modbus.modbus_controller.ModbusController.connect", return_value=True), \
            patch("custom_components.solis_modbus.modbus_controller.ModbusController.connected", return_value=True), \
            patch("custom_components.solis_modbus.modbus_controller.ModbusController.async_read_input_register",
                  return_value=[1, 2, 3]), \
            patch("custom_components.solis_modbus.modbus_controller.ModbusController.process_write_queue"), \
            patch("custom_components.solis_modbus.modbus_controller.ModbusController.async_read_holding_register",
                  return_value=[1, 2, 3]):
        # Setup the config entry
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify Config Entry is Loaded
        assert config_entry.state.value == "loaded"

        # Verify controller is stored using Entry ID
        assert DOMAIN in hass.data
        assert CONTROLLER in hass.data[DOMAIN]
        assert config_entry.entry_id in hass.data[DOMAIN][CONTROLLER]
        assert hass.data[DOMAIN][CONTROLLER][config_entry.entry_id] is not None

        # Test unload
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify controller is removed from hass.data
        assert config_entry.entry_id not in hass.data[DOMAIN][CONTROLLER]


@pytest.mark.asyncio
async def test_setup_entry_missing_serial_raises_error(hass: HomeAssistant):
    """Test setup failure when serial is missing (ConfigEntryError)."""
    # Create an entry WITHOUT a serial number (simulating an old broken config)
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "port": 502, "slave": 1, "model": "S6-EH1P"},  # No Serial
    )
    config_entry.add_to_hass(hass)

    # In your __init__.py, missing serial raises ConfigEntryError immediately
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state.value == "setup_error"
