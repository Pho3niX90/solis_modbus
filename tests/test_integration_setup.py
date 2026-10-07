from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solis_modbus.const import DOMAIN


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
            "poll_interval_slow": 30,
        },
        title="Solis Inverter",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.connect", return_value=True),
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.connected", return_value=True),
        patch(
            "custom_components.solis_modbus.modbus_controller.ModbusController.async_read_input_register",
            return_value=[1, 2, 3],
        ),
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.process_write_queue"),
        patch(
            "custom_components.solis_modbus.modbus_controller.ModbusController.async_read_holding_register",
            return_value=[1, 2, 3],
        ),
    ):
        # Setup the config entry
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify Config Entry is Loaded
        assert config_entry.state.value == "loaded"

        # Verify per-entry runtime data holds the controller and the entity lists
        assert DOMAIN in hass.data
        runtime = config_entry.runtime_data
        assert runtime is not None
        assert runtime.controller is not None
        assert runtime.data_retrieval is not None
        assert len(runtime.entities.get("sensor", [])) > 0

        # Test unload
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        # HA clears runtime_data after unload
        assert getattr(config_entry, "runtime_data", None) is None


@pytest.mark.asyncio
async def test_setup_entry_missing_serial_raises_error(hass: HomeAssistant):
    """Test setup failure when serial is missing (ConfigEntryError)."""
    # Create an entry WITHOUT a serial number
    # We set version=4 to SKIP migration and force it to hit async_setup_entry
    config_entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4", "port": 502, "slave": 1, "model": "S6-EH1P"}, version=4)
    config_entry.add_to_hass(hass)

    # Now this will run async_setup_entry, fail the validation, and raise ConfigEntryError
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # ConfigEntryError results in 'setup_error'
    assert config_entry.state.value == "setup_error"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data_value", "options", "expected"),
    [
        (True, {}, True),
        (False, {"suppress_night_offline_issue": True}, True),
        # Options win over data, e.g. enabled at setup and later disabled in options.
        (True, {"suppress_night_offline_issue": False}, False),
    ],
)
async def test_setup_entry_passes_night_suppression_flag(hass: HomeAssistant, data_value, options, expected):
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN123456",
        data={
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1,
            "inverter_serial": "SN123456",
            "model": "S6-EH1P",
            "poll_interval_fast": 10,
            "poll_interval_normal": 15,
            "poll_interval_slow": 30,
            "suppress_night_offline_issue": data_value,
        },
        options=options,
        title="Solis Inverter",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.connect", return_value=True),
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.connected", return_value=True),
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.async_read_input_register", return_value=[1, 2, 3]),
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.process_write_queue"),
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.async_read_holding_register", return_value=[1, 2, 3]),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.runtime_data.data_retrieval._suppress_night_issue is expected
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data", "options", "expected"),
    [
        # Entries from before the option existed keep syncing.
        ({}, {}, True),
        ({"clock_sync": False}, {}, False),
        ({"clock_sync": True}, {"clock_sync": False}, False),
    ],
)
async def test_setup_entry_clock_sync_option_controls_clock_sensor(hass: HomeAssistant, data, options, expected):
    """Disabling clock sync drops the derived sensor that writes the RTC (#516)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN123456",
        data={
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1,
            "inverter_serial": "SN123456",
            "model": "S6-EH1P",
            "poll_interval_fast": 10,
            "poll_interval_normal": 15,
            "poll_interval_slow": 30,
            **data,
        },
        options=options,
        title="Solis Inverter",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.connect", return_value=True),
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.connected", return_value=True),
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.async_read_input_register", return_value=[1, 2, 3]),
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.process_write_queue"),
        patch("custom_components.solis_modbus.modbus_controller.ModbusController.async_read_holding_register", return_value=[1, 2, 3]),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        derived = config_entry.runtime_data.controller._derived_sensors
        assert any(90007 in sensor.registrars for sensor in derived) is expected
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
