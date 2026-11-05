"""Power limit switch on string inverters (#538).

The switch writes 0xAA/0x55 to holding 3069 and reads its state from the input
feedback register 3089. Some models (S5-GR1P) never fill 3089, which flipped the
switch back to off on every poll while the limit stayed active.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.solis_modbus.const import CONTROLLER, MODBUS_ILLEGAL_DATA_ADDRESS, REGISTER, SLAVE, VALUE
from custom_components.solis_modbus.modbus_controller import WRITE_MAX_AGE
from custom_components.solis_modbus.sensors.solis_binary_sensor import SolisBinaryEntity

POWER_LIMIT = {"read_register": 3089, "write_register": 3069, "on_value": 0xAA, "off_value": 0x55, "name": "Enable power limit feature"}


@pytest.fixture
def controller():
    mock = MagicMock()
    mock.connected.return_value = True
    mock.host = "inverter.local"
    mock.device_id = 1
    mock.async_write_holding_register = AsyncMock()
    mock.async_read_holding_registers_with_exception = AsyncMock()
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
    controller.async_read_holding_registers_with_exception.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_feedback_falls_back_to_write_register(mock_hass, controller):
    controller.async_read_holding_registers_with_exception.return_value = ([0xAA], None)
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))
    entity._attr_is_on = False

    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)

    controller.async_read_holding_registers_with_exception.assert_awaited_once_with(3069, 1)
    assert entity.is_on is True


@pytest.mark.asyncio
async def test_temporary_read_failure_keeps_state_and_retries_at_next_poll(mock_hass, controller):
    read = controller.async_read_holding_registers_with_exception
    read.return_value = (None, None)
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))
    entity._attr_is_on = True

    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)
    assert entity.is_on is True

    read.return_value = ([0x55], None)
    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)
    assert read.await_count == 2
    assert entity.is_on is False


@pytest.mark.asyncio
async def test_rejected_address_keeps_state_and_stops_retrying(mock_hass, controller):
    read = controller.async_read_holding_registers_with_exception
    read.return_value = (None, MODBUS_ILLEGAL_DATA_ADDRESS)
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))
    entity._attr_is_on = True

    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)
    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)

    read.assert_awaited_once()
    assert entity.is_on is True


@pytest.mark.asyncio
async def test_write_register_without_state_keeps_last_state_and_retries(mock_hass, controller):
    read = controller.async_read_holding_registers_with_exception
    read.return_value = ([0], None)
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))
    entity._attr_is_on = True

    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)
    assert entity.is_on is True

    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)
    assert read.await_count == 2


async def _turn_on(entity):
    with (
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=0),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"),
    ):
        await entity.set_register_bit(True)


@pytest.mark.asyncio
async def test_toggle_during_fallback_read_is_not_undone(mock_hass, controller):
    release = asyncio.Event()

    async def slow_read(_register, _count):
        await release.wait()
        return [0x55], None  # read before the queued enable reached the inverter

    controller.async_read_holding_registers_with_exception.side_effect = slow_read
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))
    entity._attr_is_on = False

    _update(entity, 3089, 0)
    in_flight = asyncio.ensure_future(mock_hass.tasks.pop(0))
    await asyncio.sleep(0)

    await _turn_on(entity)
    release.set()
    await in_flight

    assert entity.is_on is True


@pytest.mark.asyncio
async def test_read_started_while_write_is_queued_is_ignored(mock_hass, controller):
    controller.async_read_holding_registers_with_exception.return_value = ([0x55], None)
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))

    await _turn_on(entity)
    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)

    assert entity.is_on is True


@pytest.mark.asyncio
async def test_read_is_trusted_once_the_write_can_no_longer_be_pending(mock_hass, controller):
    controller.async_read_holding_registers_with_exception.return_value = ([0x55], None)
    entity = SolisBinaryEntity(mock_hass, controller, dict(POWER_LIMIT))

    await _turn_on(entity)
    entity._last_write_queued = time.monotonic() - WRITE_MAX_AGE - 1  # sent or dropped by now
    _update(entity, 3089, 0)
    await _run_tasks(mock_hass)

    assert entity.is_on is False


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
