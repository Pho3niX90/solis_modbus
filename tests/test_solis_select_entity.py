import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from custom_components.solis_modbus.sensors.solis_select_entity import (
    SolisSelectEntity,
    set_bit,
)

@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.connected.return_value = True
    controller.host = "10.0.0.1"
    controller.identification = "abc"
    controller.model = "S6"
    controller.device_identification = "XYZ"
    controller.sw_version = "1.0"
    controller.async_write_holding_register = AsyncMock()
    return controller

@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.create_task = MagicMock()
    return hass

@pytest.mark.asyncio
async def test_set_register_bit_enforces_conflicts_and_requires(mock_hass, mock_controller):
    register = 43110
    entity_def = {
        "register": register,
        "name": "Work Mode",
        "entities": [
            { "bit_position": 0, "name": "Self-Use", "conflicts_with": (6, 11) },
            { "bit_position": 1, "name": "Self-Use + TOU", "requires": (0,) }
        ]
    }

    # 6 and 11 are on
    with patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=set_bit(set_bit(0, 6, True), 11, True)), \
            patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_save"):

        entity = SolisSelectEntity(mock_hass, mock_controller, entity_def)
        entity.set_register_bit(None, bit_position=0, conflicts_with=(6, 11), requires=None)

        expected = set_bit(set_bit(set_bit(0, 6, False), 11, False), 0, True)

        mock_hass.create_task.assert_called_once()
        task = mock_hass.create_task.call_args[0][0]
        await task  # trigger the coroutine
        mock_controller.async_write_holding_register.assert_awaited_once_with(register, expected)

@pytest.mark.asyncio
async def test_set_register_bit_with_requires(mock_hass, mock_controller):
    register = 43110
    with patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=0), \
            patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_save"):

        entity = SolisSelectEntity(mock_hass, mock_controller, {
            "register": register,
            "name": "Work Mode",
            "entities": []
        })

        entity.set_register_bit(None, bit_position=1, conflicts_with=None, requires=[0])

        expected = set_bit(set_bit(0, 0, True), 1, True)

        mock_hass.create_task.assert_called_once()
        task = mock_hass.create_task.call_args[0][0]
        await task
        mock_controller.async_write_holding_register.assert_awaited_once_with(register, expected)
