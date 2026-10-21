"""Remote Dispatch services (44100 block) — live-verified write sequences."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solis_modbus import _dispatch_function_value, _dispatch_system_limits, _s32_words
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
    assert _dispatch_function_value(None, None, None, True, None) == 2 << 8  # battery reserve on
    assert _dispatch_function_value(None, None, None, None, True) == 2 << 14  # PV limit switch on
    assert _dispatch_function_value(None, None, None, False, False) == (1 << 8) | (1 << 14)


def test_system_limits():
    assert _dispatch_system_limits(None, None) == (0, 0xFFFF, 0xFFFF)
    assert _dispatch_system_limits(24000, 24000) == (3, 240, 240)
    assert _dispatch_system_limits(0, None) == (1, 0, 0xFFFF)
    assert _dispatch_system_limits(None, 100) == (2, 0xFFFF, 1)
    assert _dispatch_system_limits(50, 150) == (3, 1, 2)  # 100 W/LSB, half-up
    assert _dispatch_system_limits(49, 24999) == (3, 0, 250)
    # zero is a valid cap on both sides
    assert _dispatch_system_limits(0, 0) == (3, 0, 0)
    # exact LSB multiples
    assert _dispatch_system_limits(100, 200) == (3, 1, 2)
    assert _dispatch_system_limits(149, 151) == (3, 1, 2)
    # 2.5 LSB banker's-rounds down; half-up goes up
    assert _dispatch_system_limits(250, None) == (1, 3, 0xFFFF)
    # service schema ceiling
    assert _dispatch_system_limits(240000, 240000) == (3, 2400, 2400)
    # HA may pass watts as strings
    assert _dispatch_system_limits("6000", "0") == (3, 60, 0)


@pytest.fixture
def controller():
    c = MagicMock()
    c.host = "1.2.3.4"
    c.device_id = 1
    c.inverter_config.type = InverterType.HYBRID
    c.async_read_input_register = AsyncMock(return_value=[0xAA55])
    # Ver3.4 defaults for the reserve SOC / PV limit pair (40 %, 100.00 %)
    c.async_read_holding_register = AsyncMock(return_value=[40, 10000])
    c.async_write_holding_register = AsyncMock()
    c.async_write_holding_registers = AsyncMock()
    c.write_queue = asyncio.Queue()
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
@pytest.mark.parametrize("service", ["solis_dispatch", "solis_dispatch_schedule"])
@pytest.mark.parametrize(
    ("version", "features", "required"),
    [
        (1, {"mode": "self_consumption"}, 2),
        (1, {"mode": "feed_in_priority"}, 2),
        (1, {"battery_reserve_soc": 30}, 2),
        (1, {"disable_discharge": True}, 2),
        (1, {"disable_discharge": False}, 2),
        (1, {"pv_limit_percent": 50}, 3),
        (2, {"pv_limit_percent": 0}, 3),
    ],
)
async def test_dispatch_rejects_features_newer_than_firmware(hass, controller, service, version, features, required):
    """A V1 S6-EA1P must not receive unsupported V2/V3 control requests."""
    controller.inverter_config.type = InverterType.ENERGY
    await setup_services(hass, controller)
    data = {"mode": "battery_hold", **features}
    if service == "solis_dispatch_schedule":
        data.update(period=1, enabled=True)
    with patch(
        "custom_components.solis_modbus.helpers.cache_get",
        side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: version}.get(register),
    ):
        with pytest.raises(ServiceValidationError, match=f"require Remote Dispatch V{required:02d}"):
            await hass.services.async_call(DOMAIN, service, data, blocking=True)
    controller.async_write_holding_register.assert_not_awaited()
    controller.async_write_holding_registers.assert_not_awaited()
    controller.async_read_holding_register.assert_not_awaited()
    controller.async_read_input_register.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("service", ["solis_dispatch", "solis_dispatch_schedule"])
@pytest.mark.parametrize("version", [None, 0, 4, 0xAA55])
async def test_dispatch_unknown_function_version_writes_nothing(hass, controller, service, version):
    controller.async_read_input_register = AsyncMock(return_value=[] if version is None else [version])
    await setup_services(hass, controller)
    data = {"mode": "self_consumption"}
    if service == "solis_dispatch_schedule":
        data.update(period=1, enabled=True)
    with patch(
        "custom_components.solis_modbus.helpers.cache_get",
        side_effect=lambda _hass, _controller, register: {34502: 0xAA55}.get(register),
    ):
        with pytest.raises(ServiceValidationError, match="Cannot verify Remote Dispatch function version"):
            await hass.services.async_call(DOMAIN, service, data, blocking=True)
    controller.async_read_input_register.assert_awaited_once_with(34503, 1)
    controller.async_write_holding_register.assert_not_awaited()
    controller.async_write_holding_registers.assert_not_awaited()
    controller.async_read_holding_register.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("service", ["solis_dispatch", "solis_dispatch_schedule"])
@pytest.mark.parametrize(
    ("version", "features"),
    [
        (1, {"mode": "battery_charge", "power_watts": 500}),
        (2, {"mode": "self_consumption", "battery_reserve_soc": 30, "disable_discharge": True}),
        (3, {"mode": "self_consumption", "pv_limit_percent": 50}),
    ],
)
async def test_dispatch_accepts_features_available_in_firmware(hass, controller, service, version, features):
    controller.inverter_config.type = InverterType.ENERGY
    await setup_services(hass, controller)
    data = dict(features)
    if service == "solis_dispatch_schedule":
        data.update(period=1, enabled=True)
    with patch(
        "custom_components.solis_modbus.helpers.cache_get",
        side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: version}.get(register),
    ):
        await hass.services.async_call(DOMAIN, service, data, blocking=True)
    assert controller.async_write_holding_registers.await_count == (2 if service == "solis_dispatch" else 1)
    controller.async_read_input_register.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("service", ["solis_dispatch", "solis_dispatch_schedule"])
async def test_dispatch_reads_missing_version_before_advanced_control(hass, controller, service):
    controller.async_read_input_register = AsyncMock(return_value=[2])
    await setup_services(hass, controller)
    data = {"mode": "self_consumption"}
    if service == "solis_dispatch_schedule":
        data.update(period=1, enabled=True)
    with patch(
        "custom_components.solis_modbus.helpers.cache_get",
        side_effect=lambda _hass, _controller, register: {34502: 0xAA55}.get(register),
    ):
        await hass.services.async_call(DOMAIN, service, data, blocking=True)
    controller.async_read_input_register.assert_awaited_once_with(34503, 1)
    assert controller.async_write_holding_registers.await_count == (2 if service == "solis_dispatch" else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("service", ["solis_dispatch", "solis_dispatch_schedule"])
@pytest.mark.parametrize("mode", ["battery_charge", "grid_port_import", "grid_export"])
async def test_household_dispatch_modes_need_no_function_version(hass, controller, service, mode):
    """Existing V1 charging/export calls work without a function-version lookup."""
    controller.inverter_config.type = InverterType.ENERGY
    await setup_services(hass, controller)
    data = {
        "mode": mode,
        "power_watts": 500,
        "pv_shutdown": False,
        "allow_grid_charge": mode != "grid_export",
        "soc_min": 10,
        "soc_max": 100,
        "failsafe_minutes": 3,
    }
    if service == "solis_dispatch_schedule":
        data.update(period=1, enabled=True)
    else:
        data["export_limit_watts"] = 100 if mode == "grid_export" else 0

    def capability_only(_hass, _controller, register):
        assert register == 34502, "V1 requests must not require function-version metadata"
        return 0xAA55

    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=capability_only):
        await hass.services.async_call(DOMAIN, service, data, blocking=True)
    controller.async_read_input_register.assert_not_awaited()
    assert controller.async_write_holding_registers.await_count == (2 if service == "solis_dispatch" else 1)


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
        (44105, [3, 0xFFFF, 0xFDA8, 2, 0, 100, 40, 10000]),
    ]
    assert single_writes(controller) == []


@pytest.mark.asyncio
async def test_dispatch_battery_charge_positive_sign(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)):
        await hass.services.async_call(DOMAIN, "solis_dispatch", {"mode": "battery_charge", "power_watts": 3000}, blocking=True)
    blocks = [c.args for c in controller.async_write_holding_registers.await_args_list]
    # battery_charge => mode 2, positive power 3000 W -> raw 300
    assert blocks[0] == (44100, [1, 30, 0, 0xFFFF, 0xFFFF])
    assert blocks[1] == (44105, [2, 0, 300, 0, 0, 100, 40, 10000])


@pytest.mark.asyncio
async def test_dispatch_battery_charge_with_import_export_limits(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)):
        await hass.services.async_call(
            DOMAIN,
            "solis_dispatch",
            {"mode": "battery_charge", "power_watts": 3000, "import_limit_watts": 6000, "export_limit_watts": 0},
            blocking=True,
        )
    blocks = [c.args for c in controller.async_write_holding_registers.await_args_list]
    # 44102 BIT00|BIT01, 44103 = 6000 W / 100, 44104 = 0 W
    assert blocks[0] == (44100, [1, 30, 0b11, 60, 0])


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
    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)):
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
    controller.async_write_holding_registers.assert_awaited_once_with(44130, [1, (8 << 8) | 30, 16 << 8, 3, 0xFFFF, 0xFDA8, 2, 0, 100, 40, 10000])
    # current reserve/PV-limit pair of period 2 is read back, not zeroed (#500)
    controller.async_read_holding_register.assert_awaited_once_with(44139, 2)
    # enabled -> long failsafe + master on
    assert (44101, 1440) in single_writes(controller)
    assert (44100, 1) in single_writes(controller)


@pytest.mark.asyncio
async def test_dispatch_schedule_disable_leaves_master_alone(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)):
        await hass.services.async_call(DOMAIN, "solis_dispatch_schedule", {"period": 1, "enabled": False}, blocking=True)
    block = controller.async_write_holding_registers.await_args.args
    assert block[0] == 44116 and block[1][0] == 0
    assert single_writes(controller) == []  # no master/failsafe writes on disable


@pytest.mark.asyncio
async def test_dispatch_preserves_reserve_and_pv_limit(hass: HomeAssistant, controller):
    """#500: omitted reserve SOC / PV limit must be written back unchanged, never zeroed."""
    controller.async_read_holding_register = AsyncMock(return_value=[25, 8000])
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)):
        await hass.services.async_call(DOMAIN, "solis_dispatch", {"mode": "battery_hold"}, blocking=True)
    controller.async_read_holding_register.assert_awaited_once_with(44111, 2)
    blocks = [c.args for c in controller.async_write_holding_registers.await_args_list]
    # function 0: the reserve and PV-limit switches keep their current state
    assert blocks[1] == (44105, [1, 0, 0, 0, 0, 100, 25, 8000])


@pytest.mark.asyncio
async def test_dispatch_sets_reserve_and_pv_limit(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)):
        await hass.services.async_call(
            DOMAIN,
            "solis_dispatch",
            {"mode": "self_consumption", "battery_reserve_soc": 30, "pv_limit_percent": 55.5},
            blocking=True,
        )
    # both supplied: no read needed, and both switches enabled in 44108
    controller.async_read_holding_register.assert_not_awaited()
    blocks = [c.args for c in controller.async_write_holding_registers.await_args_list]
    assert blocks[1] == (44105, [5, 0, 0, (2 << 8) | (2 << 14), 0, 100, 30, 5550])


@pytest.mark.asyncio
async def test_dispatch_sets_one_and_preserves_the_other(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)):
        await hass.services.async_call(DOMAIN, "solis_dispatch", {"mode": "battery_hold", "pv_limit_percent": 0}, blocking=True)
    blocks = [c.args for c in controller.async_write_holding_registers.await_args_list]
    assert blocks[1] == (44105, [1, 0, 0, 2 << 14, 0, 100, 40, 0])


@pytest.mark.asyncio
async def test_dispatch_read_failure_writes_nothing(hass: HomeAssistant, controller):
    controller.async_read_holding_register = AsyncMock(return_value=None)
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(DOMAIN, "solis_dispatch", {"mode": "grid_import", "power_watts": 1000}, blocking=True)
    controller.async_write_holding_registers.assert_not_awaited()
    controller.async_write_holding_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_schedule_sets_reserve_and_pv_limit(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)):
        await hass.services.async_call(
            DOMAIN,
            "solis_dispatch_schedule",
            {"period": 1, "enabled": False, "battery_reserve_soc": 20, "pv_limit_percent": 100},
            blocking=True,
        )
    controller.async_read_holding_register.assert_not_awaited()
    controller.async_write_holding_registers.assert_awaited_once_with(44116, [0, 0, 0, 1, 0, 0, (2 << 8) | (2 << 14), 0, 100, 20, 10000])


@pytest.mark.asyncio
async def test_dispatch_drains_write_queue_before_read_back(hass: HomeAssistant, controller):
    """Writes are queued but reads are not: a read-back must not overtake pending writes."""
    order = []
    controller.write_queue = MagicMock()
    controller.write_queue.join = AsyncMock(side_effect=lambda: order.append("join"))
    controller.async_read_holding_register = AsyncMock(side_effect=lambda *a: order.append("read") or [40, 10000])
    await setup_services(hass, controller)
    with patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)):
        await hass.services.async_call(DOMAIN, "solis_dispatch", {"mode": "battery_hold"}, blocking=True)
    assert order == ["join", "read"]


@pytest.mark.asyncio
async def test_dispatch_pending_writes_timeout_writes_nothing(hass: HomeAssistant, controller):
    controller.write_queue.put_nowait((44105, 1, False))  # never processed
    await setup_services(hass, controller)
    with (
        patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)),
        patch("custom_components.solis_modbus.DISPATCH_WRITE_FLUSH_TIMEOUT", 0.01),
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(DOMAIN, "solis_dispatch", {"mode": "battery_hold"}, blocking=True)
    controller.async_read_holding_register.assert_not_awaited()
    controller.async_write_holding_registers.assert_not_awaited()


@pytest.mark.asyncio
async def test_stalled_inverter_does_not_block_dispatch_to_another(hass: HomeAssistant, controller):
    """The dispatch lock is per inverter: one waiting out its flush timeout must not hold up the rest."""
    stalled = MagicMock()
    stalled.host = "5.6.7.8"
    stalled.device_id = 1
    stalled.inverter_config.type = InverterType.HYBRID
    stalled.async_read_holding_register = AsyncMock(return_value=[40, 10000])
    stalled.async_write_holding_registers = AsyncMock()
    stalled.write_queue = asyncio.Queue()
    stalled.write_queue.put_nowait((44105, 1, False))  # never processed
    other = MockConfigEntry(domain=DOMAIN, data={})
    other.add_to_hass(hass)
    other.runtime_data = SolisRuntimeData(controller=stalled)
    await setup_services(hass, controller)

    with (
        patch("custom_components.solis_modbus.helpers.cache_get", side_effect=lambda _hass, _controller, register: {34502: 0xAA55, 34503: 3}.get(register)),
        patch("custom_components.solis_modbus.DISPATCH_WRITE_FLUSH_TIMEOUT", 5),
    ):
        stalled_call = hass.async_create_task(hass.services.async_call(DOMAIN, "solis_dispatch", {"mode": "battery_hold", "host": "5.6.7.8"}, blocking=True))
        await asyncio.sleep(0)  # let the stalled call take its lock and start waiting
        await asyncio.wait_for(
            hass.services.async_call(DOMAIN, "solis_dispatch", {"mode": "battery_hold", "host": "1.2.3.4"}, blocking=True),
            timeout=1,
        )
        assert controller.async_write_holding_registers.await_count == 2
        assert not stalled_call.done()
        stalled.write_queue.get_nowait()  # unstick it so the test exits cleanly
        stalled.write_queue.task_done()
        await stalled_call
