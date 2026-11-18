"""Second battery (BAT2) support on dual-battery hybrids such as the S6-EH3P50K-H.

Registers verified live on an S6-EH3P50K-H: SOC 34278 matches the app's battery-2
value, direction 34291 is 0 while charging and 1 while discharging, and power
34368/34369 is S32 (positive charging, negative discharging), like battery 1.
Battery Combined Power follows Battery Power Net instead: negative charging,
positive discharging, signed from the direction registers 33135 / 34291.
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


COMBINED_POWER = [33149, 33150, 33135, 34368, 34369, 34291]


def test_combined_power_discharging_is_positive_like_battery_power_net(hass):
    """Measured while discharging: BAT1 -2300 W (0xFFFF F704), BAT2 -2500 W (0xFFFF F63C)."""
    sensor = _derived(hass, COMBINED_POWER)
    _feed(sensor, {33149: 0xFFFF, 33150: 0xF704, 33135: 1, 34368: 0xFFFF, 34369: 0xF63C, 34291: 1})
    assert sensor.native_value == 4800


def test_combined_power_charging_is_negative_like_battery_power_net(hass):
    """Charging: BAT1 +1500 W, BAT2 +1000 W, direction 0 on both."""
    sensor = _derived(hass, COMBINED_POWER)
    _feed(sensor, {33149: 0, 33150: 1500, 33135: 0, 34368: 0, 34369: 1000, 34291: 0})
    assert sensor.native_value == -2500


def test_combined_power_takes_the_sign_from_the_direction_registers(hass):
    """Firmware reporting 33149/50 as an unsigned magnitude: the direction sets the sign.
    One battery charging while the other discharges nets out."""
    sensor = _derived(hass, COMBINED_POWER)
    _feed(sensor, {33149: 0, 33150: 2300, 33135: 1, 34368: 0, 34369: 1000, 34291: 0})
    assert sensor.native_value == 1300


def test_derived_update_handler_is_an_event_loop_callback():
    """Without @callback the dispatcher runs the handler in the executor, unordered."""
    from homeassistant.core import HassJob, HassJobType, is_callback

    from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

    assert is_callback(SolisDerivedSensor.handle_modbus_update)
    assert HassJob(SolisDerivedSensor.handle_modbus_update).job_type is HassJobType.Callback


async def test_combined_power_through_the_real_dispatcher(hass):
    """Two overlapping polls sent through async_dispatcher_send publish only same-poll
    sums, and every update is handled on the event loop, never on executor threads."""
    import threading
    from unittest.mock import patch

    from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

    from custom_components.solis_modbus.const import CONTROLLER, POLL_ID, REGISTER, SLAVE, VALUE

    loop_thread = threading.get_ident()
    sensor = _derived(hass, COMBINED_POWER)
    for reg in set(COMBINED_POWER):
        async_dispatcher_connect(hass, f"test_{reg}", sensor.handle_modbus_update)

    def send(reg, value, poll_id):
        payload = {REGISTER: reg, VALUE: value, CONTROLLER: "1.2.3.4", SLAVE: 1, POLL_ID: poll_id}
        async_dispatcher_send(hass, f"test_{reg}", payload)

    published = []
    threads = set()
    same_poll = sensor._sources_from_same_poll

    def on_loop_check(poll_id):
        threads.add(threading.get_ident())
        return same_poll(poll_id)

    with (
        patch.object(sensor, "schedule_update_ha_state", side_effect=lambda: published.append(sensor.native_value)),
        patch.object(sensor, "_sources_from_same_poll", side_effect=on_loop_check),
    ):
        # Poll 1 BAT2 discharging 1000 W, then poll 2 overtakes it completely.
        for reg, value in ((34368, 0), (34369, 1000), (34291, 1)):
            send(reg, value, 1)
        for reg, value in ((33149, 0), (33150, 2300), (33135, 1), (34368, 0), (34369, 2500), (34291, 1)):
            send(reg, value, 2)
        await hass.async_block_till_done()

    assert threads == {loop_thread}
    assert published == [4800]


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
    sensor = _derived(hass, COMBINED_POWER)
    # Poll 1: BAT1 read failed, only BAT2 arrives (discharging 1000 W).
    _feed(sensor, {34368: 0xFFFF, 34369: 0xFC18, 34291: 1}, poll_id=1)
    assert sensor.native_value is None
    # Poll 2: BAT1 2300 W arrives first; BAT2 from poll 1 is dropped, not combined.
    _feed(sensor, {33149: 0xFFFF, 33150: 0xF704, 33135: 1}, poll_id=2)
    assert sensor.native_value is None
    # Poll 2: BAT2 2500 W completes the pair.
    _feed(sensor, {34368: 0xFFFF, 34369: 0xF63C, 34291: 1}, poll_id=2)
    assert sensor.native_value == 4800
    # Poll 3: both succeed and publish together.
    _feed(sensor, {33149: 0xFFFF, 33150: 0xF768, 33135: 1, 34368: 0xFFFF, 34369: 0xF6A0, 34291: 1}, poll_id=3)
    assert sensor.native_value == 4600


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


async def _run_polls(hass, polls):
    """Drive real DataRetrieval batches into a real Combined Power sensor.

    ``polls`` is a list of {battery_start: (power_words, direction) or None}; None
    makes that battery's reads fail in that poll. Each battery is read as two
    groups, power and direction. Returns every value the combined sensor published.
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from custom_components.solis_modbus.const import DOMAIN, VALUES
    from custom_components.solis_modbus.data.enums import PollSpeed
    from custom_components.solis_modbus.data_retrieval import DataRetrieval
    from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup

    sensor = _derived(hass, COMBINED_POWER)
    controller = sensor.base_sensor.controller
    controller.enabled = True
    controller.connected = MagicMock(return_value=True)
    controller.last_read_unanswered = False
    controller.poll_speed = {PollSpeed.FAST: 10, PollSpeed.NORMAL: 15, PollSpeed.SLOW: 30}

    groups = []
    for start, count in ((33135, 1), (33149, 2), (34291, 1), (34368, 2)):
        group = MagicMock(spec=SolisSensorGroup)
        group.poll_speed = PollSpeed.FAST
        group.start_register = start
        group.registrar_count = count
        groups.append(group)
    controller.sensor_groups = groups

    current = {}
    battery_of = {33135: 33149, 33149: 33149, 34291: 34368, 34368: 34368}

    async def read(start, count):
        if start >= 34291:
            await asyncio.sleep(0.05)  # BAT2 answers late within its poll
        reading = current[battery_of[start]]
        if reading is None:
            return None, None
        power, direction = reading
        return (power if count == 2 else [direction]), None

    controller.async_read_input_registers_with_exception = AsyncMock(side_effect=read)

    published = []
    poll_hass = MagicMock()
    poll_hass.is_running = False
    poll_hass.data = {DOMAIN: {VALUES: {}}}

    def deliver(_hass, _signal, payload):
        sensor.handle_modbus_update(payload)

    with (
        patch("custom_components.solis_modbus.data_retrieval.async_track_time_interval"),
        patch("custom_components.solis_modbus.helpers.async_dispatcher_send", side_effect=deliver),
        patch.object(DataRetrieval, "_image_is_blank", AsyncMock(return_value=False)),
        patch.object(sensor, "schedule_update_ha_state", side_effect=lambda: published.append(sensor.native_value)),
    ):
        retrieval = DataRetrieval(poll_hass, controller)
        retrieval._can_poll = MagicMock(return_value=True)
        for poll in polls:
            current.clear()
            current.update(poll)
            await retrieval.get_modbus_updates(groups, PollSpeed.FAST)
    return published


async def test_poller_publishes_a_poll_whose_bat2_read_is_delayed(hass):
    """Readings from one poll are combined however late the second group answers."""
    published = await _run_polls(hass, [{33149: ([0xFFFF, 0xF704], 1), 34368: ([0xFFFF, 0xF63C], 1)}])
    assert published == [4800]


async def test_poller_never_mixes_polls_after_a_failed_bat1_block(hass):
    """Poll 1: BAT1 fails, BAT2 discharges 1000 W. Poll 2 and 3 succeed. Only same-poll sums are published."""
    published = await _run_polls(
        hass,
        [
            {33149: None, 34368: ([0xFFFF, 0xFC18], 1)},
            {33149: ([0xFFFF, 0xF704], 1), 34368: ([0xFFFF, 0xF63C], 1)},
            {33149: ([0xFFFF, 0xF768], 1), 34368: ([0xFFFF, 0xF6A0], 1)},
        ],
    )
    # 2300 + 1000 (poll 2 BAT1 with poll 1 BAT2) must never appear.
    assert published == [4800, 4600]
