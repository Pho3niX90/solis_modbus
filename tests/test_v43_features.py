"""v4.2.0 second wave: read_register + force charge/discharge services,
little-endian 32-bit decode, EPM gating."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solis_modbus.const import DOMAIN
from custom_components.solis_modbus.data.enums import DataType, InverterFeature, InverterType
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, inverter_options_from_config
from custom_components.solis_modbus.helpers import combine_u32_le, split_s32_le
from custom_components.solis_modbus.runtime import SolisRuntimeData
from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

# ---------- little-endian decode ----------


def test_le_combiners():
    # raw words [low, high]: 0x86A0 low + 0x0001 high -> 100000
    assert combine_u32_le([0x86A0, 0x0001]) == 100000
    assert combine_u32_le([0xFFFF, 0xFFFF]) == 4294967295
    assert split_s32_le([0xFFFF, 0xFFFF]) == -1
    assert split_s32_le([0x86A0, 0x0001]) == 100000


def make_sensor(data_type):
    controller = MagicMock()
    controller.inverter_config.model = "TEST"
    controller.inverter_config.features = []
    controller.inverter_config.wattage_chosen = 5000
    return SolisBaseSensor(
        hass=None,
        controller=controller,
        unique_id="u",
        name="n",
        registrars=[36050, 36051],
        write_register=None,
        multiplier=1,
        data_type=data_type,
    )


def test_u32_le_decode_path():
    sensor = make_sensor(DataType.U32_LE)
    # EPM energy past the 16-bit boundary: big-endian would read garbage
    assert sensor._convert_raw_value([0x86A0, 0x0001]) == 100000


def test_s32_le_decode_path():
    sensor = make_sensor(DataType.S32_LE)
    assert sensor._convert_raw_value([0xFFFF, 0xFFFF]) == -1


# ---------- EPM gating ----------


def test_epm_groups_are_gated():
    epm_groups = [g for g in string_sensors if g.get("register_start") in (36013, 36022, 36028, 36050)]
    assert len(epm_groups) == 4
    for group in epm_groups:
        assert group.get("feature_requirement") == [InverterFeature.EPM]


def test_epm_feature_defaults_on_and_can_be_disabled():
    template = next(inv for inv in SOLIS_INVERTERS if inv.model == "S5-GR3P")
    default = template.clone_with_options(inverter_options_from_config({}, template), "S2_WL_ST")
    disabled = template.clone_with_options(inverter_options_from_config({"has_epm": False}, template), "S2_WL_ST")
    assert InverterFeature.EPM in default.features  # status quo preserved on upgrade
    assert InverterFeature.EPM not in disabled.features


# ---------- services ----------


@pytest.fixture
def controller():
    c = MagicMock()
    c.host = "1.2.3.4"
    c.device_id = 1
    c.inverter_config.type = InverterType.HYBRID
    c.inverter_config.wattage_chosen = 8000
    c.async_read_input_register = AsyncMock(return_value=[0x0001, 0x86A0])
    c.async_read_holding_register = AsyncMock(return_value=[33])
    c.async_read_input_registers_with_exception = AsyncMock(return_value=([0x0001, 0x86A0], None))
    c.async_read_holding_registers_with_exception = AsyncMock(return_value=([33], None))
    c.async_write_holding_register = AsyncMock()
    return c


async def setup_services(hass, controller):
    from custom_components.solis_modbus import async_setup

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.runtime_data = SolisRuntimeData(controller=controller)
    await async_setup(hass, {})
    return entry


@pytest.mark.asyncio
async def test_read_register_service_returns_values(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    response = await hass.services.async_call(DOMAIN, "solis_read_register", {"address": 33169, "count": 2}, blocking=True, return_response=True)
    controller.async_read_input_registers_with_exception.assert_awaited_once_with(33169, 2)
    assert response["values"] == [1, 0x86A0]
    assert response["hex"] == ["0x0001", "0x86A0"]
    assert response["u32_be"] == 100000
    assert response["u32_le"] == 0x86A00001


@pytest.mark.asyncio
async def test_read_register_holding(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    response = await hass.services.async_call(
        DOMAIN, "solis_read_register", {"address": 43110, "register_type": "holding"}, blocking=True, return_response=True
    )
    controller.async_read_holding_registers_with_exception.assert_awaited_once_with(43110, 1)
    assert response["values"] == [33]


@pytest.mark.asyncio
async def test_read_register_rejects_a_bad_address_without_a_server_error(hass: HomeAssistant, controller):
    """Probing the wrong register type is a caller mistake, not a crash (#447).

    Reading a holding register as "input" made the inverter reject the address,
    which surfaced as an unhandled HTTP 500. It should be a validation error
    naming the other register type instead.
    """
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.solis_modbus.const import MODBUS_ILLEGAL_DATA_ADDRESS

    controller.async_read_input_registers_with_exception = AsyncMock(
        return_value=(None, MODBUS_ILLEGAL_DATA_ADDRESS)
    )
    await setup_services(hass, controller)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "solis_read_register",
            {"address": 44100, "count": 2}, blocking=True, return_response=True,
        )

    assert "44100" in str(err.value)
    assert "holding" in str(err.value), "should point the user at the other register type"


@pytest.mark.asyncio
async def test_read_register_still_errors_when_the_read_simply_fails(hass: HomeAssistant, controller):
    """No exception code means a transport failure, which is not the caller's fault."""
    from homeassistant.exceptions import HomeAssistantError

    controller.async_read_input_registers_with_exception = AsyncMock(return_value=(None, None))
    await setup_services(hass, controller)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "solis_read_register",
            {"address": 33169, "count": 2}, blocking=True, return_response=True,
        )


@pytest.mark.asyncio
async def test_force_charge_writes_the_352_combo_in_order(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    await hass.services.async_call(DOMAIN, "solis_force_battery_charge", {"power_watts": 3000, "duration_minutes": 30}, blocking=True)
    calls = [c.args for c in controller.async_write_holding_register.await_args_list]
    # Enable FIRST (issue #352 latch), then power (W/10), then timeout (minutes)
    assert calls == [(43135, 1), (43136, 300), (43282, 30)]


@pytest.mark.asyncio
async def test_force_discharge_clamps_power_to_inverter_rating(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    await hass.services.async_call(DOMAIN, "solis_force_battery_discharge", {"power_watts": 20000}, blocking=True)
    calls = [c.args for c in controller.async_write_holding_register.await_args_list]
    assert calls == [(43135, 2), (43129, 800)]  # clamped to 8000 W -> raw 800; no timeout write


@pytest.mark.asyncio
async def test_stop_force(hass: HomeAssistant, controller):
    await setup_services(hass, controller)
    await hass.services.async_call(DOMAIN, "solis_stop_force_charge_discharge", {}, blocking=True)
    controller.async_write_holding_register.assert_awaited_once_with(43135, 0)


@pytest.mark.asyncio
async def test_force_charge_rejected_on_grid_inverter(hass: HomeAssistant, controller):
    controller.inverter_config.type = InverterType.GRID
    await setup_services(hass, controller)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "solis_force_battery_charge", {"power_watts": 1000}, blocking=True)
    controller.async_write_holding_register.assert_not_awaited()
