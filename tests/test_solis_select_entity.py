from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.solis_modbus.sensors.solis_select_entity import (
    SolisSelectEntity,
    set_bit,
)


@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.connected.return_value = True
    controller.host = "10.0.0.1"
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


def test_set_bit_treats_none_as_zero():
    assert set_bit(None, 2, True) == 4
    assert set_bit(None, 2, False) == 0


@pytest.mark.asyncio
async def test_set_register_bit_with_uncached_register(mock_hass, mock_controller):
    """Selecting a bit option before the first poll must not crash (cache is empty)."""
    register = 43110
    with (
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=None),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_save"),
    ):
        entity = SolisSelectEntity(mock_hass, mock_controller, {"register": register, "name": "Work Mode", "entities": []})
        entity.set_register_bit(None, bit_position=0, conflicts_with=None, requires=None)

        mock_hass.create_task.assert_called_once()
        task = mock_hass.create_task.call_args[0][0]
        await task
        mock_controller.async_write_holding_register.assert_awaited_once_with(register, 1)


@pytest.mark.asyncio
async def test_set_register_bit_enforces_conflicts_and_requires(mock_hass, mock_controller):
    register = 43110
    entity_def = {
        "register": register,
        "name": "Work Mode",
        "entities": [
            {"bit_position": 0, "name": "Self-Use", "conflicts_with": (6, 11)},
            {"bit_position": 1, "name": "Self-Use + TOU", "requires": (0,)},
        ],
    }

    # 6 and 11 are on
    with (
        patch(
            "custom_components.solis_modbus.sensors.solis_select_entity.cache_get",
            return_value=set_bit(set_bit(0, 6, True), 11, True),
        ),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_save"),
    ):
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
    with (
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=0),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_save"),
    ):
        entity = SolisSelectEntity(mock_hass, mock_controller, {"register": register, "name": "Work Mode", "entities": []})

        entity.set_register_bit(None, bit_position=1, conflicts_with=None, requires=[0])

        expected = set_bit(set_bit(0, 0, True), 1, True)

        mock_hass.create_task.assert_called_once()
        task = mock_hass.create_task.call_args[0][0]
        await task
        mock_controller.async_write_holding_register.assert_awaited_once_with(register, expected)


@pytest.mark.asyncio
async def test_companion_writes_after_on_value_select(mock_hass, mock_controller):
    """After writing the primary register, companion registers must be re-written from cache, in order.

    Solis firmware requires Forced Charge/Discharge (43135) to be enabled BEFORE the
    related setpoints (43129, 43136) and RC Timeout (43282) are written for the values
    to latch (issue #352).
    """
    primary_register = 43135
    cached = {
        43136: 1500,
        43129: 1200,
        43282: 30,
    }

    def fake_cache_get(_hass, _controller, register):
        return cached.get(register)

    with patch(
        "custom_components.solis_modbus.sensors.solis_select_entity.cache_get",
        side_effect=fake_cache_get,
    ):
        entity = SolisSelectEntity(
            mock_hass,
            mock_controller,
            {
                "register": primary_register,
                "name": "RC Force Charge/Discharge",
                "companion_writes": [43136, 43129, 43282],
                "entities": [
                    {"name": "None", "on_value": 0},
                    {"name": "Solis RC Force Battery Charge", "on_value": 1},
                ],
            },
        )
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("Solis RC Force Battery Charge")

        assert mock_controller.async_write_holding_register.await_args_list == [
            ((primary_register, 1), {}),
            ((43136, cached[43136]), {}),
            ((43129, cached[43129]), {}),
            ((43282, cached[43282]), {}),
        ]


@pytest.mark.asyncio
async def test_companion_writes_skip_individual_uncached_registers(mock_hass, mock_controller):
    """Companion writes only fire for registers that already have a cached value."""
    primary_register = 43135
    cached = {
        43136: 1500,
        # 43129 not yet polled
        43282: 30,
    }

    def fake_cache_get(_hass, _controller, register):
        return cached.get(register)

    with patch(
        "custom_components.solis_modbus.sensors.solis_select_entity.cache_get",
        side_effect=fake_cache_get,
    ):
        entity = SolisSelectEntity(
            mock_hass,
            mock_controller,
            {
                "register": primary_register,
                "name": "RC Force Charge/Discharge",
                "companion_writes": [43136, 43129, 43282],
                "entities": [
                    {"name": "None", "on_value": 0},
                    {"name": "Solis RC Force Battery Charge", "on_value": 1},
                ],
            },
        )
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("Solis RC Force Battery Charge")

        assert mock_controller.async_write_holding_register.await_args_list == [
            ((primary_register, 1), {}),
            ((43136, cached[43136]), {}),
            ((43282, cached[43282]), {}),
        ]


@pytest.mark.asyncio
async def test_companion_writes_skipped_when_cache_empty(mock_hass, mock_controller):
    """Companion writes should be skipped if the cached value isn't available yet."""
    primary_register = 43135
    companion_register = 43282

    with patch(
        "custom_components.solis_modbus.sensors.solis_select_entity.cache_get",
        return_value=None,
    ):
        entity = SolisSelectEntity(
            mock_hass,
            mock_controller,
            {
                "register": primary_register,
                "name": "RC Force Charge/Discharge",
                "companion_writes": [companion_register],
                "entities": [
                    {"name": "None", "on_value": 0},
                    {"name": "Solis RC Force Battery Charge", "on_value": 1},
                ],
            },
        )
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("Solis RC Force Battery Charge")

        mock_controller.async_write_holding_register.assert_awaited_once_with(primary_register, 1)
