import pytest
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.solis_modbus.sensors.solis_binary_sensor import (
    SolisBinaryEntity,
    set_bit,
)

@pytest.fixture
def controller():
    mock = MagicMock()
    mock.connected.return_value = True
    mock.host = "inverter.local"
    mock.identification = "test-id"
    mock.model = "S6"
    mock.device_identification = "XYZ"
    mock.sw_version = "1.0"
    mock.async_write_holding_register = AsyncMock()
    return mock

@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.create_task = MagicMock()
    return hass

def assert_called_with_write_task(mock_hass, expected_register, expected_value):
    mock_hass.create_task.assert_called_once()
    task = mock_hass.create_task.call_args[0][0]

    # Confirm it's a coroutine
    assert inspect.iscoroutine(task)

    # Evaluate the coroutine manually to extract the arguments passed
    coro_func = task.cr_code.co_name
    assert "async_write_holding_register" in coro_func or "_execute_mock_call" in coro_func


@pytest.mark.asyncio
async def test_conflicts_self_use_mode(mock_hass, controller):
    entity_def = {
        "register": 43110,
        "bit_position": 0,
        "conflicts_with": (6, 11),
        "name": "Self-Use Mode",
    }

    initial = set_bit(set_bit(0, 6, True), 11, True)

    with patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=initial), \
            patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"):

        entity = SolisBinaryEntity(mock_hass, controller, entity_def)
        entity.set_register_bit(True)

        expected = set_bit(set_bit(0, 6, False), 11, False)
        expected = set_bit(expected, 0, True)

        assert_called_with_write_task(mock_hass, 43110, expected)

@pytest.mark.asyncio
async def test_requires_tou(mock_hass, controller):
    entity_def = {
        "register": 43110,
        "bit_position": 1,
        "requires": (0,),
        "name": "TOU (Self-Use)",
    }

    with patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=0), \
            patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"):

        entity = SolisBinaryEntity(mock_hass, controller, entity_def)
        entity.set_register_bit(True)

        expected = set_bit(set_bit(0, 0, True), 1, True)
        assert_called_with_write_task(mock_hass, 43110, expected)

@pytest.mark.asyncio
async def test_conflicts_and_requires_combined(mock_hass, controller):
    entity_def = {
        "register": 43110,
        "bit_position": 4,
        "conflicts_with": (0, 6),
        "requires": (1,),
        "name": "Reserve Battery Mode",
    }

    initial = set_bit(set_bit(set_bit(0, 0, True), 6, True), 1, True)

    with patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=initial), \
            patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"):

        entity = SolisBinaryEntity(mock_hass, controller, entity_def)
        entity.set_register_bit(True)

        expected = set_bit(set_bit(0, 1, True), 4, True)
        assert_called_with_write_task(mock_hass, 43110, expected)
