"""The string-map export limit (issue #569): 3110-3113 read back, 3151 written, S5-GC only."""

from unittest.mock import AsyncMock, MagicMock

from custom_components.solis_modbus.data.enums import InverterFeature, InverterType, PollSpeed
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, inverter_options_from_config
from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup
from custom_components.solis_modbus.sensors.solis_number_sensor import SolisNumberEntity


def _group():
    (group,) = [g for g in string_sensors if g.get("register_start") == 3110]
    return group


def _entity(unique):
    return next(e for e in _group()["entities"] if e.get("unique") == unique)


def _limit():
    return _entity("solis_modbus_inverter_export_power_limit")


def _features(model):
    template = next(inv for inv in SOLIS_INVERTERS if inv.model == model)
    return template.clone_with_options(inverter_options_from_config({}, template), "S2_WL_ST").features


def _controller():
    class MockConfig:
        model = "S5-GC"
        features = [InverterFeature.INTERNAL_EPM]
        wattage_chosen = 30000

    controller = MagicMock()
    controller.inverter_config = MockConfig()
    controller.device_serial_number = "SN"
    controller.identification = None
    controller.host = "127.0.0.1"
    controller.async_write_holding_register = AsyncMock()
    return controller


def _built_group(controller):
    """The group as setup builds it, so the tests see what SolisSensorGroup passes on."""
    return SolisSensorGroup(hass=None, definition=_group(), controller=controller)


def _sensor(controller):
    return next(x for x in _built_group(controller).sensors if x.registrars == [3111])


def test_group_is_contiguous_and_gated():
    group = _group()
    assert group["feature_requirement"] == [InverterFeature.INTERNAL_EPM]
    registers = sorted(int(r) for e in group["entities"] for r in e["register"])
    assert registers == [3110, 3111, 3112, 3113]


def test_built_group_reads_one_contiguous_slow_block():
    group = _built_group(_controller())
    assert (group.start_register, group.registrar_count) == (3110, 4)
    assert group.poll_speed == PollSpeed.SLOW


def test_group_is_the_last_slow_group():
    """A timeout ends the batch, so no other slow group may come after this one."""
    slow = [g["register_start"] for g in string_sensors if g.get("poll_speed") == PollSpeed.SLOW]
    assert slow[-1] == 3110


def test_only_the_s5_gc_polls_it():
    """A string model that never answered on 3110 must not start timing out there."""
    assert InverterFeature.INTERNAL_EPM in _features("S5-GC")
    for inv in SOLIS_INVERTERS:
        if inv.model != "S5-GC" and inv.type in (InverterType.GRID, InverterType.STRING):
            assert InverterFeature.INTERNAL_EPM not in _features(inv.model), inv.model


def test_limit_writes_the_holding_register():
    entity = _limit()
    assert entity["register"] == ["3111"]
    assert entity["write_register"] == 3151
    assert entity["editable"] is True
    assert entity["min"] == 0
    # A grid-side limit: never capped at the inverter rating (#438).
    assert "max" not in entity and "max_source" not in entity


def test_reported_reading_decodes_to_the_cloud_value():
    """The S5-GC30K in #569 read 3111 = 189 while SolisCloud showed 18900 W."""
    sensor = _sensor(_controller())
    assert sensor.convert_value([189]) == 18900
    assert sensor.convert_value([65535]) == -100  # S16: import side reads negative


def test_setting_the_limit_writes_hectowatts():
    controller = _controller()
    hass = MagicMock()
    number = SolisNumberEntity(hass, _sensor(controller))
    number.schedule_update_ha_state = MagicMock()
    number.set_native_value(18900)
    hass.create_task.assert_called_once()
    hass.create_task.call_args[0][0].close()  # the mocked hass never runs it
    controller.async_write_holding_register.assert_called_once_with(3151, 189)


def test_live_export_power_scale():
    entity = _entity("solis_modbus_inverter_export_control_live_power")
    assert entity["register"] == ["3113"]
    assert entity["multiplier"] == 10
