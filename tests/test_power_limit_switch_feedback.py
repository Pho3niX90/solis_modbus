"""Power limit switch on string inverters (#538).

The switch writes 0xAA/0x55 to holding 3069 and reads its state from the input
feedback register 3089. Some models (S5-GR1P) never fill 3089, which flipped the
switch back to off on every poll while the limit stayed active.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.solis_modbus.const import CONTROLLER, REGISTER, SLAVE, VALUE
from custom_components.solis_modbus.sensors.solis_binary_sensor import SolisBinaryEntity

POWER_LIMIT = {"read_register": 3089, "write_register": 3069, "on_value": 0xAA, "off_value": 0x55, "name": "Enable power limit feature"}


@pytest.fixture
def controller():
    mock = MagicMock()
    mock.connected.return_value = True
    mock.host = "inverter.local"
    mock.device_id = 1
    mock.async_write_holding_register = AsyncMock()
    mock.async_read_holding_register = AsyncMock()
    return mock


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.tasks = []
    hass.async_create_task = MagicMock(side_effect=hass.tasks.append)
    return hass


def _update(entity, register, value):
    entity.handle_modbus_update({REGISTER: register, VALUE: value, CONTROLLER: "inverter.local", SLAVE: 1})


async def _run_tasks(hass):
    while hass.tasks:
        await hass.tasks.pop(0)


@pytest.mark.asyncio
async def test_feedback_on_and_off_values_are_trusted(mock_hass, controller):
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))

    _update(entity, 3089, 0xAA)
    assert entity.is_on is True
    _update(entity, 3089, 0x55)
    assert entity.is_on is False

    mock_hass.async_create_task.assert_not_called()
    controller.async_read_holding_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_feedback_falls_back_to_write_register(mock_hass, controller):
    controller.async_read_holding_register.return_value = [0xAA]
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))
    entity._attr_is_on = False

    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)

    controller.async_read_holding_register.assert_awaited_once_with(3069, 1)
    assert entity.is_on is True


@pytest.mark.asyncio
async def test_unreadable_write_register_keeps_last_state_and_stops_retrying(mock_hass, controller):
    controller.async_read_holding_register.return_value = None
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))
    entity._attr_is_on = True  # just turned on from HA

    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)
    assert entity.is_on is True

    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)
    controller.async_read_holding_register.assert_awaited_once()
    assert entity.is_on is True


@pytest.mark.asyncio
async def test_write_register_without_state_keeps_last_state(mock_hass, controller):
    controller.async_read_holding_register.return_value = [0]
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))
    entity._attr_is_on = True

    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)

    assert entity.is_on is True


@pytest.mark.asyncio
async def test_single_register_switch_keeps_state_on_unknown_value(mock_hass, controller):
    entity = SolisBinaryEntity(mock_hass, controller, {"register": 43070, "on_value": 170, "off_value": 85, "name": "Output Limit Gate"})
    entity._attr_is_on = True

    _update(entity, 43070, 0)

    assert entity.is_on is True
    mock_hass.async_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_switch_without_off_value_still_treats_other_values_as_off(mock_hass, controller):
    entity = SolisBinaryEntity(mock_hass, controller, {"register": 43135, "on_value": 1, "name": "RC Force Battery Charge"})
    entity._attr_is_on = True

    _update(entity, 43135, 2)

    assert entity.is_on is False
