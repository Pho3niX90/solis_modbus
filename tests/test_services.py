from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.solis_modbus.const import DOMAIN


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
        await hass.services.async_call(DOMAIN, "solis_write_holding_register", {"address": 123, "value": 456, "host": "1.2.3.4"}, blocking=True)

        mock_controller.async_write_holding_register.assert_called_with(123, 456)


@pytest.mark.asyncio
async def test_service_write_holding_register_no_host(hass: HomeAssistant, mock_controller):
    """Test solis_write_holding_register service without host (broadcast to all)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.solis_modbus.runtime import SolisRuntimeData

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.runtime_data = SolisRuntimeData(controller=mock_controller)

    from custom_components.solis_modbus import async_setup

    await async_setup(hass, {})

    await hass.services.async_call(DOMAIN, "solis_write_holding_register", {"address": 123, "value": 456}, blocking=True)

    mock_controller.async_write_holding_register.assert_called_with(123, 456)


@pytest.mark.asyncio
async def test_service_set_time(hass: HomeAssistant):
    """Test solis_write_time service."""
    from datetime import time

    mock_entity = MagicMock()
    mock_entity.entity_id = "time.test_time"
    mock_entity.async_set_value = MagicMock(return_value=None)

    # async_set_value must be awaitable
    async def async_set_value(val):
        pass

    mock_entity.async_set_value = MagicMock(side_effect=async_set_value)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.solis_modbus.runtime import SolisRuntimeData

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.runtime_data = SolisRuntimeData(controller=MagicMock())
    entry.runtime_data.entities["time"] = [mock_entity]

    from custom_components.solis_modbus import async_setup

    await async_setup(hass, {})

    await hass.services.async_call(DOMAIN, "solis_write_time", {"entity_id": "time.test_time", "time": "12:30:00"}, blocking=True)

    # Check if called with correct time object
    mock_entity.async_set_value.assert_called()
    call_args = mock_entity.async_set_value.call_args
    assert call_args[0][0] == time(12, 30, 0)


@pytest.mark.asyncio
async def test_service_accepts_documented_slave_field(hass: HomeAssistant, mock_controller):
    """services.yaml documents `slave`, so the schema must accept it.

    Regression: SCHEME_HOLDING_REGISTER omitted the key, and voluptuous rejects
    undeclared keys — so every call passing a slave failed validation before it
    ever reached the handler that reads it.
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.solis_modbus import async_setup
    from custom_components.solis_modbus.runtime import SolisRuntimeData

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.runtime_data = SolisRuntimeData(controller=mock_controller)

    await async_setup(hass, {})

    await hass.services.async_call(
        DOMAIN,
        "solis_write_holding_register",
        {"address": 123, "value": 456, "slave": 1},
        blocking=True,
    )

    mock_controller.async_write_holding_register.assert_called_with(123, 456)


@pytest.mark.asyncio
async def test_service_slave_filters_targets(hass: HomeAssistant, mock_controller):
    """An explicit slave should only write to matching controllers."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.solis_modbus import async_setup
    from custom_components.solis_modbus.runtime import SolisRuntimeData

    other = MagicMock()
    other.host = "5.6.7.8"
    other.device_id = 2
    other.async_write_holding_register = AsyncMock(return_value=None)

    for controller in (mock_controller, other):
        entry = MockConfigEntry(domain=DOMAIN, data={}, entry_id=f"entry_{controller.device_id}")
        entry.add_to_hass(hass)
        entry.runtime_data = SolisRuntimeData(controller=controller)

    await async_setup(hass, {})

    await hass.services.async_call(
        DOMAIN,
        "solis_write_holding_register",
        {"address": 1, "value": 2, "slave": 2},
        blocking=True,
    )

    other.async_write_holding_register.assert_called_with(1, 2)
    mock_controller.async_write_holding_register.assert_not_called()


@pytest.mark.asyncio
async def test_service_unknown_host_raises(hass: HomeAssistant):
    """An unmatched host must raise, not dereference None."""
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.solis_modbus import async_setup

    await async_setup(hass, {})

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "solis_write_holding_register",
            {"address": 1, "value": 2, "host": "no.such.host"},
            blocking=True,
        )
