"""Remote Dispatch services (44100 block) — live-verified write sequences."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solis_modbus import _dispatch_function_value, _s32_words
from custom_components.solis_modbus.const import DOMAIN
from custom_components.solis_modbus.data.enums import InverterType
from custom_components.solis_modbus.runtime import SolisRuntimeData


def test_s32_words():
    assert _s32_words(-600) == [0xFFFF, 0xFDA8]  # import 6 kW (x10 W)
    assert _s32_words(500) == [0x0000, 0x01F4]
    assert _s32_words(0) == [0, 0]


def test_function_value_pairs():
    assert _dispatch_function_value(None, None, None) == 0
    assert _dispatch_function_value(True, None, None) == 2  # PV shutdown on
    assert _dispatch_function_value(False, None, None) == 1  # PV shutdown off
    assert _dispatch_function_value(None, True, None) == 1 << 4  # grid charge allowed
    assert _dispatch_function_value(None, False, None) == 2 << 4  # not allowed
    assert _dispatch_function_value(None, None, True) == 2 << 10  # discharge disabled
    assert _dispatch_function_value(True, True, True) == 2 | (1 << 4) | (2 << 10)


@pytest.fixture
def controller():
    c = MagicMock()
    c.host = "1.2.3.4"
    c.device_id = 1
    c.inverter_config.type = InverterType.HYBRID
    c.async_read_input_register = AsyncMock(return_value=[0xAA55])
    c.async_write_holding_register = AsyncMock()
    c.async_write_holding_registers = AsyncMock()
    return c


async def setup_services(hass, controller):
    from custom_components.solis_modbus import async_setup

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.runtime_data = SolisRuntimeData(controller=controller)
    await async_setup(hass, {})
    return entry


def single_writes(controller):
    return [c.args for c in controller.async_write_holding_register.await_args_list]


@pytest.mark.asyncio
async def test_dispatch_grid_import_sequence(hass: HomeAssistant, controller):
    """The exact live-verified order: failsafe, master on, power pair, function, mode LAST."""
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", return_value=None):
        await hass.services.async_call(
            DOMAIN,
            "solis_dispatch",
            {"mode": "grid_import", "power_watts": 6000, "pv_shutdown": True, "failsafe_minutes": 30},
            blocking=True,
        )
    # Two atomic FC16 chunks: global (44100-44104) then realtime (44105-44112)
    blocks = [c.args for c in controller.async_write_holding_registers.await_args_list]
    assert blocks == [
        (44100, [1, 30, 0, 0xFFFF, 0xFFFF]),
        (44105, [3, 0xFFFF, 0xFDA8, 2, 0, 100, 0, 0]),
    ]
    assert single_writes(controller) == []


@pytest.mark.asyncio
async def test_dispatch_battery_charge_positive_sign(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", return_value=0xAA55):
        await hass.services.async_call(DOMAIN, "solis_dispatch", {"mode": "battery_charge", "power_watts": 3000}, blocking=True)
    blocks = [c.args for c in controller.async_write_holding_registers.await_args_list]
    # battery_charge => mode 2, positive power 3000 W -> raw 300
    assert blocks[0] == (44100, [1, 30, 0, 0xFFFF, 0xFFFF])
    assert blocks[1] == (44105, [2, 0, 300, 0, 0, 100, 0, 0])


@pytest.mark.asyncio
async def test_dispatch_rejected_without_capability(hass: HomeAssistant, controller):
    controller.async_read_input_register = AsyncMock(return_value=[0])
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", return_value=None):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(DOMAIN, "solis_dispatch", {"mode": "grid_import", "power_watts": 1000}, blocking=True)
    controller.async_write_holding_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_stop_verified_revert(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    await hass.services.async_call(DOMAIN, "solis_dispatch_stop", {}, blocking=True)
    assert single_writes(controller) == [(44105, 1), (44108, 1), (44100, 0)]


@pytest.mark.asyncio
async def test_dispatch_schedule_period_block(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", return_value=0xAA55):
        await hass.services.async_call(
            DOMAIN,
            "solis_dispatch_schedule",
            {
                "period": 2,
                "enabled": True,
                "start_time": "08:30",
                "end_time": "16:00",
                "mode": "grid_import",
                "power_watts": 6000,
                "pv_shutdown": True,
                "soc_max": 100,
            },
            blocking=True,
        )
    # period 2 base = 44116 + 14 = 44130
    controller.async_write_holding_registers.assert_awaited_once_with(44130, [1, (8 << 8) | 30, 16 << 8, 3, 0xFFFF, 0xFDA8, 2, 0, 100, 0, 0])
    # enabled -> long failsafe + master on
    assert (44101, 1440) in single_writes(controller)
    assert (44100, 1) in single_writes(controller)


@pytest.mark.asyncio
async def test_dispatch_schedule_disable_leaves_master_alone(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", return_value=0xAA55):
        await hass.services.async_call(DOMAIN, "solis_dispatch_schedule", {"period": 1, "enabled": False}, blocking=True)
    block = controller.async_write_holding_registers.await_args.args
    assert block[0] == 44116 and block[1][0] == 0
    assert single_writes(controller) == []  # no master/failsafe writes on disable
