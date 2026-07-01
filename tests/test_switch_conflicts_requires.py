from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.solis_modbus.sensors.solis_binary_sensor import (
    SolisBinaryEntity,
    set_bit,
)


@pytest.fixture
def controller():
    mock = MagicMock()
    mock.connected.return_value = True
    mock.host = "inverter.local"
    mock.device_id = 1
    mock.identification = "test-id"
    mock.model = "S6"
    mock.device_identification = "XYZ"
    mock.sw_version = "1.0"
    mock.async_write_holding_register = AsyncMock()
    mock.async_read_holding_register = AsyncMock()
    return mock


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.create_task = MagicMock()
    return hass


@pytest.mark.asyncio
async def test_conflicts_self_use_mode(mock_hass, controller):
    entity_def = {
        "register": 43110,
        "bit_position": 0,
        "conflicts_with": (6, 11),
        "name": "Self-Use Mode",
    }

    initial = set_bit(set_bit(0, 6, True), 11, True)

    with (
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=initial),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"),
    ):
        entity = SolisBinaryEntity(mock_hass, controller, entity_def)
        await entity.set_register_bit(True)

        expected = set_bit(set_bit(0, 6, False), 11, False)
        expected = set_bit(expected, 0, True)

        controller.async_write_holding_register.assert_awaited_once_with(43110, expected)


@pytest.mark.asyncio
async def test_requires_tou(mock_hass, controller):
    entity_def = {
        "register": 43110,
        "bit_position": 1,
        "requires": (0,),
        "name": "TOU (Self-Use)",
    }

    with (
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=0),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"),
    ):
        entity = SolisBinaryEntity(mock_hass, controller, entity_def)
        await entity.set_register_bit(True)

        expected = set_bit(set_bit(0, 0, True), 1, True)
        controller.async_write_holding_register.assert_awaited_once_with(43110, expected)


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

    with (
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=initial),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"),
    ):
        entity = SolisBinaryEntity(mock_hass, controller, entity_def)
        await entity.set_register_bit(True)

        expected = set_bit(set_bit(0, 1, True), 4, True)
        controller.async_write_holding_register.assert_awaited_once_with(43110, expected)


@pytest.mark.asyncio
async def test_cold_cache_reads_live_value_and_preserves_bits(mock_hass, controller):
    """Issue #402: toggling a bit before the register has been polled must not
    start the read-modify-write from 0 (which clears every other bit). The live
    register value must be read from the inverter first."""
    entity_def = {
        "register": 43110,
        "bit_position": 1,
        "name": "TOU (Self-Use)",
    }

    live_value = set_bit(set_bit(0, 0, True), 4, True)  # bits 0 and 4 already set on the device
    controller.async_read_holding_register.return_value = [live_value]

    with (
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=None),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"),
    ):
        entity = SolisBinaryEntity(mock_hass, controller, entity_def)
        await entity.set_register_bit(True)

        controller.async_read_holding_register.assert_awaited_once_with(43110, 1)
        expected = set_bit(live_value, 1, True)  # other bits preserved
        controller.async_write_holding_register.assert_awaited_once_with(43110, expected)


@pytest.mark.asyncio
async def test_cold_cache_failed_live_read_skips_write(mock_hass, controller):
    """Issue #402: if the cache is empty and the live read fails, do not write
    anything rather than risk clearing the other bits in the register."""
    entity_def = {
        "register": 43110,
        "bit_position": 1,
        "name": "TOU (Self-Use)",
    }

    controller.async_read_holding_register.return_value = None

    with (
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=None),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"),
    ):
        entity = SolisBinaryEntity(mock_hass, controller, entity_def)
        await entity.set_register_bit(True)

        controller.async_read_holding_register.assert_awaited_once_with(43110, 1)
        controller.async_write_holding_register.assert_not_awaited()
