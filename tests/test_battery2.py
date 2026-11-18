"""Second battery (BAT2) support on dual-battery hybrids such as the S6-EH3P50K-H.

Registers verified live on an S6-EH3P50K-H: SOC 34278 matches the app's battery-2
value, direction 34291 is 0 while charging and 1 while discharging, and power
34368/34369 is S32 (positive charging, negative discharging), like battery 1.
"""

from custom_components.solis_modbus.data.enums import DataType, InverterFeature
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, inverter_options_from_config
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors

BATTERY2_GROUP_STARTS = {34275, 34368, 34373}


def _battery2_groups():
    return [g for g in hybrid_sensors if g.get("register_start") in BATTERY2_GROUP_STARTS]


def _battery2_entities():
    return {e["unique"]: e for g in _battery2_groups() for e in g["entities"] if "unique" in e}


def test_battery2_groups_exist_and_are_gated():
    groups = _battery2_groups()
    assert len(groups) == 3
    for group in groups:
        assert group.get("feature_requirement") == [InverterFeature.BATTERY2]


def test_battery2_feature_from_config():
    template = next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH3P")

    default_opts = inverter_options_from_config({}, template)
    enabled_opts = inverter_options_from_config({"has_battery2": True}, template)

    assert InverterFeature.BATTERY2 not in template.clone_with_options(default_opts, "S2_WL_ST").features
    assert InverterFeature.BATTERY2 in template.clone_with_options(enabled_opts, "S2_WL_ST").features


def test_battery2_core_registers():
    ents = _battery2_entities()
    assert ents["solis_modbus_inverter_battery2_soc"]["register"] == ["34278"]
    assert ents["solis_modbus_inverter_battery2_voltage"]["register"] == ["34289"]
    assert ents["solis_modbus_inverter_battery2_current"]["register"] == ["34290"]
    assert ents["solis_modbus_inverter_battery2_current_direction"]["register"] == ["34291"]
    power = ents["solis_modbus_inverter_battery2_power"]
    assert power["register"] == ["34368", "34369"]
    # Two registers decode as S32 by default; discharging must come out negative.
    assert power.get("data_type") in (None, DataType.S32)


def test_battery2_unique_ids_do_not_clash_with_other_sensors():
    others = {e["unique"] for g in hybrid_sensors if g.get("register_start") not in BATTERY2_GROUP_STARTS for e in g["entities"] if "unique" in e}
    assert not others & set(_battery2_entities())


def _derived(hass, registrars):
    from unittest.mock import MagicMock

    from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.slave = 1
    controller.device_id = 1
    base = MagicMock()
    base.controller = controller
    base.name = "Test"
    base.unique_id = "test"
    base.registrars = registrars
    base.multiplier = 0
    base.device_class = None
    base.unit_of_measurement = None
    base.hidden = False
    base.state_class = "measurement"
    return SolisDerivedSensor(hass, base)


def _feed(sensor, values, poll_id=None):
    from unittest.mock import patch

    from custom_components.solis_modbus.const import CONTROLLER, POLL_ID, REGISTER, SLAVE, VALUE

    with patch.object(sensor, "schedule_update_ha_state"):
        for reg, val in values.items():
            data = {REGISTER: reg, VALUE: val, CONTROLLER: "1.2.3.4", SLAVE: 1}
            if poll_id is not None:
                data[POLL_ID] = poll_id
            sensor.handle_modbus_update(data)


def test_combined_soc_matches_app(hass):
    """The app showed 51 % with BAT1 at 60 % and BAT2 at 42 %."""
    sensor = _derived(hass, [33139, 34278])
    _feed(sensor, {33139: 60, 34278: 42})
    assert sensor.native_value == 51


def test_combined_power_sums_signed_values(hass):
    """Measured while discharging: BAT1 -2300 W (0xFFFF F704), BAT2 -2500 W (0xFFFF F63C)."""
    sensor = _derived(hass, [33149, 33150, 34368, 34369])
    _feed(sensor, {33149: 0xFFFF, 33150: 0xF704, 34368: 0xFFFF, 34369: 0xF63C})
    assert sensor.native_value == -4800


def test_combined_sensors_only_with_battery2():
    from custom_components.solis_modbus.helpers import derived_sensor_is_supported
    from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors_derived

    known = {int(r) for g in hybrid_sensors for e in g["entities"] for r in e.get("register", [])}
    without_b2 = {int(r) for g in hybrid_sensors if g.get("register_start") not in BATTERY2_GROUP_STARTS for e in g["entities"] for r in e.get("register", [])}
    combined = [e for e in hybrid_sensors_derived if "combined_soc" in e["unique"] or "combined_power" in e["unique"]]
    assert len(combined) == 2
    for entity in combined:
        assert not derived_sensor_is_supported(entity, without_b2, known)
        assert derived_sensor_is_supported(entity, known, known)


def test_battery1_cell_extremes_mirror_battery2():
    """#573: battery-1 cell extremes 34348-34351 sit 25 registers before battery 2's."""
    group = next(g for g in hybrid_sensors if g.get("register_start") == 34348)
    assert group.get("feature_requirement") == [InverterFeature.BATTERY]
    b1 = {e["unique"].replace("solis_modbus_inverter_battery_", ""): e for e in group["entities"]}
    b2 = {k.replace("solis_modbus_inverter_battery2_", ""): e for k, e in _battery2_entities().items()}
    assert set(b1) == {"min_cell_voltage_bms", "max_cell_voltage_bms", "min_cell_temperature_bms", "max_cell_temperature_bms"}
    for key, entity in b1.items():
        assert int(entity["register"][0]) + 25 == int(b2[key]["register"][0])
        assert entity["multiplier"] == b2[key]["multiplier"]
        assert entity.get("data_type") == b2[key].get("data_type")


def test_battery2_is_polled_in_essential_but_not_extreme():
    """BAT2 SOC and power join the essential profile like BAT1's 33132 block. Extreme
    stays within its frame budget (#457), so it keeps polling BAT1 only."""
    from custom_components.solis_modbus.const import POLL_PROFILE_ESSENTIAL, POLL_PROFILE_EXTREME
    from custom_components.solis_modbus.helpers import group_in_poll_profile

    for start in (34275, 34368):
        group = next(g for g in hybrid_sensors if g.get("register_start") == start)
        assert group_in_poll_profile(group, POLL_PROFILE_ESSENTIAL)
        assert not group_in_poll_profile(group, POLL_PROFILE_EXTREME, include_battery=True)


def test_combined_power_pairs_readings_by_poll(hass):
    """A missed BAT1 read must not pair the next BAT1 value with BAT2 from the previous poll."""
    sensor = _derived(hass, [33149, 33150, 34368, 34369])
    # Poll 1: BAT1 read failed, only BAT2 arrives (-1000 W).
    _feed(sensor, {34368: 0xFFFF, 34369: 0xFC18}, poll_id=1)
    assert sensor.native_value is None
    # Poll 2: BAT1 -2300 W arrives first; BAT2 from poll 1 is dropped, not combined.
    _feed(sensor, {33149: 0xFFFF, 33150: 0xF704}, poll_id=2)
    assert sensor.native_value is None
    # Poll 2: BAT2 -2500 W completes the pair.
    _feed(sensor, {34368: 0xFFFF, 34369: 0xF63C}, poll_id=2)
    assert sensor.native_value == -4800
    # Poll 3: both succeed and publish together.
    _feed(sensor, {33149: 0xFFFF, 33150: 0xF768, 34368: 0xFFFF, 34369: 0xF6A0}, poll_id=3)
    assert sensor.native_value == -4600


def test_combined_soc_pairs_readings_by_poll(hass):
    sensor = _derived(hass, [33139, 34278])
    _feed(sensor, {34278: 40}, poll_id=7)
    _feed(sensor, {33139: 60}, poll_id=8)
    assert sensor.native_value is None
    _feed(sensor, {34278: 42}, poll_id=8)
    assert sensor.native_value == 51


async def test_poller_tags_each_batch_with_its_own_poll_id():
    """All groups read in one batch share a poll id; the next batch gets a new one."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from custom_components.solis_modbus.const import DOMAIN, VALUES
    from custom_components.solis_modbus.data.enums import PollSpeed
    from custom_components.solis_modbus.data_retrieval import DataRetrieval
    from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup

    hass = MagicMock()
    hass.is_running = False  # don't start the poll loop; batches are driven by hand
    hass.data = {DOMAIN: {VALUES: {}}}
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.device_id = 1
    controller.enabled = True
    controller.connected = MagicMock(return_value=True)
    controller.last_read_unanswered = False
    controller.poll_speed = {PollSpeed.FAST: 10, PollSpeed.NORMAL: 15, PollSpeed.SLOW: 30}
    controller.async_read_input_registers_with_exception = AsyncMock(side_effect=lambda start, count: ([1] * count, None))

    groups = []
    for start in (33149, 34368):
        group = MagicMock(spec=SolisSensorGroup)
        group.poll_speed = PollSpeed.FAST
        group.start_register = start
        group.registrar_count = 2
        groups.append(group)
    controller.sensor_groups = groups

    with (
        patch("custom_components.solis_modbus.data_retrieval.async_track_time_interval"),
        patch("custom_components.solis_modbus.data_retrieval.notify_register_update") as notify,
        patch.object(DataRetrieval, "_image_is_blank", AsyncMock(return_value=False)),
    ):
        retrieval = DataRetrieval(hass, controller)
        retrieval._can_poll = MagicMock(return_value=True)
        await retrieval.get_modbus_updates(groups, PollSpeed.FAST)
        first = {call.args[2]: call.args[4] for call in notify.call_args_list}
        notify.reset_mock()
        await retrieval.get_modbus_updates(groups, PollSpeed.FAST)
        second = {call.args[2]: call.args[4] for call in notify.call_args_list}

    assert set(first) == {33149, 33150, 34368, 34369}
    assert len(set(first.values())) == 1
    assert len(set(second.values())) == 1
    assert set(first.values()) != set(second.values())


def test_battery2_soc_gets_the_same_spike_filter_as_battery1():
    """A one-off 0 % from BAT2 must not drag Combined SOC down, as for BAT1."""
    from unittest.mock import MagicMock, patch

    from custom_components.solis_modbus.data_retrieval import DataRetrieval

    hass = MagicMock()
    hass.is_running = False
    with patch("custom_components.solis_modbus.data_retrieval.cache_get", return_value=42):
        retrieval = DataRetrieval(hass, MagicMock())
        for register in (33139, 34278):
            assert retrieval.spike_filtering(register, 0) == 42
            assert retrieval.spike_filtering(register, 0) == 42
            assert retrieval.spike_filtering(register, 0) == 0  # persistent: accepted
            assert retrieval.spike_filtering(register, 41) == 41
