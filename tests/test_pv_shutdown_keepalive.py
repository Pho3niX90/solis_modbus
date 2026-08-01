"""PV Shutdown keep-alive (issue #409): register 44280 self-reverts after the
RC timeout (43282), so the switch re-writes the bit inside that window while ON.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS
from custom_components.solis_modbus.sensor_data.switch_sensors import get_switch_sensors
from custom_components.solis_modbus.sensors.solis_binary_sensor import SolisBinaryEntity


def make_entity(cache=None):
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.device_id = 1
    controller.connected.return_value = True
    controller.async_write_holding_register = AsyncMock()
    definition = {"name": "PV Shutdown", "bit_position": 4, "register": 44280, "write_register": None, "keep_alive": True}
    entity = SolisBinaryEntity(MagicMock(), controller, definition)
    return entity, controller, cache if cache is not None else {44280: 0, 43282: 5}


def cache_get_side_effect(cache):
    return lambda hass, controller, register: cache.get(register)


def test_pv_shutdown_definition_has_keep_alive():
    hybrid = next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH1P")
    groups = get_switch_sensors(hybrid)
    pv = next(e for g in groups for e in g["entities"] if e["name"] == "PV Shutdown")
    assert pv.get("keep_alive") is True


@pytest.mark.asyncio
async def test_turn_on_writes_and_schedules_keep_alive():
    entity, controller, cache = make_entity()
    with (
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", side_effect=cache_get_side_effect(cache)),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.async_call_later") as mock_later,
    ):
        await entity.async_turn_on()
    controller.async_write_holding_register.assert_awaited_once_with(44280, 16)  # bit 4 set
    mock_later.assert_called_once()
    # RC timeout 5 min -> refresh at 240 s (a minute inside the window)
    assert mock_later.call_args.args[1] == 240.0


@pytest.mark.asyncio
async def test_refresh_force_writes_even_when_cache_matches():
    """Device reverted to 0 but our cache still says 16 — refresh must write anyway."""
    entity, controller, cache = make_entity(cache={44280: 16, 43282: 5})
    entity._attr_is_on = True
    with (
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", side_effect=cache_get_side_effect(cache)),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.async_call_later") as mock_later,
    ):
        await entity._keep_alive_refresh(None)
    controller.async_write_holding_register.assert_awaited_once_with(44280, 16)
    mock_later.assert_called_once()  # reschedules itself


@pytest.mark.asyncio
async def test_turn_off_cancels_keep_alive_and_clears_bit():
    entity, controller, cache = make_entity(cache={44280: 16, 43282: 5})
    unsub = MagicMock()
    entity._keep_alive_unsub = unsub
    with (
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", side_effect=cache_get_side_effect(cache)),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"),
    ):
        await entity.async_turn_off()
    unsub.assert_called_once()
    assert entity._keep_alive_unsub is None
    controller.async_write_holding_register.assert_awaited_once_with(44280, 0)


@pytest.mark.asyncio
async def test_refresh_noop_when_switch_off():
    entity, controller, cache = make_entity()
    entity._attr_is_on = False
    with patch("custom_components.solis_modbus.sensors.solis_binary_sensor.async_call_later") as mock_later:
        await entity._keep_alive_refresh(None)
    controller.async_write_holding_register.assert_not_awaited()
    mock_later.assert_not_called()


def test_keep_alive_interval_bounds():
    entity, _, _ = make_entity()
    with patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=1):
        assert entity._keep_alive_interval() == 30.0  # 1-min timeout -> floor 30 s
    with patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=None):
        assert entity._keep_alive_interval() == 240.0  # default 5 min
    with patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", return_value=30):
        assert entity._keep_alive_interval() == 1740.0  # 30-min timeout
