"""Auto-disable EPM when string/grid 36xxx registers are absent (issue #466)."""

from functools import partial
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.solis_modbus.const import DOMAIN, NUMBER_ENTITIES, SENSOR_ENTITIES, VALUES
from custom_components.solis_modbus.data.enums import InverterFeature, InverterType, PollSpeed
from custom_components.solis_modbus.data.solis_config import InverterConfig, InverterOptions
from custom_components.solis_modbus.data_retrieval import (
    DataRetrieval,
    epm_group_is_absence_witness,
    is_string_epm_operating_group,
)
from custom_components.solis_modbus.modbus_controller import ModbusController
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup


def _mock_sensor(registrars: list[int], name: str = "s", enabled: bool = True):
    m = MagicMock()
    m.registrars = registrars
    m.name = name
    m.enabled = enabled
    return m


def _group(registrars_list: list[list[int]], start: int | None = None) -> MagicMock:
    sensors = [_mock_sensor(r, name=f"r{r[0]}") for r in registrars_list]
    group = MagicMock(spec=SolisSensorGroup)
    group.sensors = sensors
    group.poll_speed = PollSpeed.FAST
    group.identification = "test"
    group.start_register = start if start is not None else min(registrars_list[0])
    group.registrar_count = sum(len(r) for r in registrars_list)
    return group


def test_reserved_pair_is_not_an_absence_witness():
    assert not epm_group_is_absence_witness(_group([[36013], [36014]]))


def test_load_power_group_is_an_absence_witness():
    assert epm_group_is_absence_witness(_group([[36028, 36029]]))


def test_hybrid_360xx_is_not_string_epm():
    group = _group([[36000], [36001]])
    assert not is_string_epm_operating_group(InverterType.HYBRID, group)
    assert is_string_epm_operating_group(InverterType.GRID, group)


def test_disable_epm_rebuilds_features():
    config = InverterConfig(
        model="S5-GR3P",
        wattage=[10000],
        phases=3,
        type=InverterType.GRID,
        options=InverterOptions(epm=True, battery=False),
    )
    assert InverterFeature.EPM in config.features
    config.disable_epm()
    assert InverterFeature.EPM not in config.features
    assert config.options.epm is False


def _retrieval(inverter_type=InverterType.GRID, epm=True, entry_id="entry1"):
    hass = MagicMock()
    hass.is_running = False
    hass.data = {DOMAIN: {VALUES: {}, SENSOR_ENTITIES: [], NUMBER_ENTITIES: []}}
    hass.loop = None
    hass.async_create_task = MagicMock()
    controller = MagicMock()
    controller.host = "192.168.88.1"
    controller.slave = 1
    controller.device_id = 1
    controller.enabled = True
    controller.connected = MagicMock(return_value=True)
    controller.inverter_config = InverterConfig(
        model="S5-GR3P",
        wattage=[10000],
        phases=3,
        type=inverter_type,
        options=InverterOptions(epm=epm, battery=False),
    )
    groups: list = []
    controller._sensor_groups = groups
    controller.sensor_groups = groups
    controller.replace_sensor_group = partial(ModbusController.replace_sensor_group, controller)
    with patch("custom_components.solis_modbus.data_retrieval.ir"):
        retrieval = DataRetrieval(hass, controller, entry_id)
    return retrieval, hass, controller


def _set_groups(controller, groups: list) -> None:
    controller._sensor_groups = groups
    controller.sensor_groups = groups


def test_runtime_disable_drops_epm_groups_and_keeps_others():
    retrieval, hass, controller = _retrieval()
    epm_fast = _group([[36028, 36029]], start=36028)
    epm_id = _group([[36013], [36014]], start=36013)
    other = _group([[3004, 3005]], start=3004)
    _set_groups(controller, [other, epm_fast, epm_id])

    with patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        with patch("custom_components.solis_modbus.data_retrieval.mark_platform_entities_unavailable_for_base_sensors"):
            retrieval._disable_epm_runtime(36028)

    assert retrieval._epm_disabled is True
    assert InverterFeature.EPM not in controller.inverter_config.features
    assert controller._sensor_groups == [other]
    assert epm_fast.sensors[0].enabled is False
    assert epm_id.sensors[0].enabled is False
    mock_ir.async_create_issue.assert_called_once()
    assert mock_ir.async_create_issue.call_args.kwargs["translation_key"] == "epm_absent"
    assert retrieval._epm_persist_pending is True


@pytest.mark.asyncio
async def test_persist_writes_has_epm_false():
    retrieval, hass, _ = _retrieval()
    entry = MagicMock()
    entry.data = {"has_epm": True, "host": "192.168.88.1"}
    entry.options = {}
    hass.config_entries.async_get_entry.return_value = entry

    await retrieval._async_persist_epm_disabled()

    hass.config_entries.async_update_entry.assert_called_once()
    kwargs = hass.config_entries.async_update_entry.call_args.kwargs
    assert kwargs["options"]["has_epm"] is False


@pytest.mark.asyncio
async def test_persist_skips_when_already_false():
    retrieval, hass, _ = _retrieval()
    entry = MagicMock()
    entry.data = {}
    entry.options = {"has_epm": False}
    hass.config_entries.async_get_entry.return_value = entry

    await retrieval._async_persist_epm_disabled()

    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_witness_group_failure_autodisables_epm():
    retrieval, hass, controller = _retrieval()
    epm_fast = _group([[36028, 36029]], start=36028)
    other = _group([[3004]], start=3004)
    other.poll_speed = PollSpeed.FAST
    _set_groups(controller, [other, epm_fast])

    async def read_blk(start, count, is_holding):
        if start == 36028:
            return None, 2
        return ([1] * count, None)

    with patch.object(retrieval, "_read_register_block_with_exception", new=AsyncMock(side_effect=read_blk)):
        with patch.object(retrieval, "_recover_sensor_group_after_modbus_failure", new=AsyncMock(return_value=None)):
            with patch("custom_components.solis_modbus.data_retrieval.ir"):
                with patch("custom_components.solis_modbus.data_retrieval.mark_platform_entities_unavailable_for_base_sensors"):
                    retrieval.connection_check = True
                    await retrieval.get_modbus_updates([other, epm_fast], PollSpeed.FAST)

    assert retrieval._epm_disabled is True
    assert other in controller._sensor_groups
    assert epm_fast not in controller._sensor_groups


@pytest.mark.asyncio
async def test_reserved_group_failure_does_not_autodisable():
    retrieval, hass, controller = _retrieval()
    reserved = _group([[36013], [36014]], start=36013)
    reserved.poll_speed = PollSpeed.NORMAL
    _set_groups(controller, [reserved])

    with patch.object(retrieval, "_read_register_block_with_exception", new=AsyncMock(return_value=(None, 2))):
        with patch.object(retrieval, "_recover_sensor_group_after_modbus_failure", new=AsyncMock(return_value=None)):
            retrieval.connection_check = True
            await retrieval.get_modbus_updates([reserved], PollSpeed.NORMAL)

    assert retrieval._epm_disabled is False
    assert InverterFeature.EPM in controller.inverter_config.features
    assert reserved in controller._sensor_groups


@pytest.mark.asyncio
async def test_hybrid_mapping_failure_does_not_autodisable():
    retrieval, hass, controller = _retrieval(inverter_type=InverterType.HYBRID)
    mapping = _group([[36000], [36001]], start=36000)
    mapping.poll_speed = PollSpeed.NORMAL
    _set_groups(controller, [mapping])

    with patch.object(retrieval, "_read_register_block_with_exception", new=AsyncMock(return_value=(None, 2))):
        with patch.object(retrieval, "_recover_sensor_group_after_modbus_failure", new=AsyncMock(return_value=None)):
            retrieval.connection_check = True
            await retrieval.get_modbus_updates([mapping], PollSpeed.NORMAL)

    assert retrieval._epm_disabled is False
    assert mapping in controller._sensor_groups
