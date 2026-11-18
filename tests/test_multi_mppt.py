"""MPPT count: DC voltage/current/power 1..N on every model, more than 4 on multi-MPPT string
inverters (3P(80-110)K-5G up to 15, S5-GC up to 6), which also get a current per PV string.

Register layout (protocol doc -> wire = doc - 1), field-verified on a Solis-100K-5G:
  3022-3029   DC voltage/current 1-4 (wire 3021-3028), every string model
  3287        string voltage/current combination (wire 3286)
  3299 / 3300 total PV voltage / current (= sum of the string currents)
  3301-3320   PV string current 1-20
  3504-3514   DC voltage 5-15 (MPPT voltage block, doc 3500 = MPPT 1)
  3534-3544   DC current 5-15 (MPPT current block, doc 3530 = MPPT 1)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import data_entry_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solis_modbus.const import CONF_MPPT_COUNT, CONN_TYPE_TCP, CONTROLLER, DOMAIN, REGISTER, SLAVE, VALUE
from custom_components.solis_modbus.data.enums import InverterFeature, InverterType, PollSpeed
from custom_components.solis_modbus.data.solis_config import (
    LEGACY_MPPT_COUNT,
    SOLIS_INVERTERS,
    InverterOptions,
    inverter_options_from_config,
    mppt_count_from_registers,
)
from custom_components.solis_modbus.helpers import apply_mppt_count, derived_sensor_is_supported, registers_declared_by
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors, hybrid_sensors_derived
from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors, string_sensors_derived
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor

MULTI_MPPT_MODEL = "3P(80-110)K-5G"
GC_MODEL = "S5-GC"
LEGACY_MODELS = [inv.model for inv in SOLIS_INVERTERS if InverterFeature.MULTI_MPPT not in inv.features]


def _template(model):
    return next(inv for inv in SOLIS_INVERTERS if inv.model == model)


def _config(model, entry_config=None):
    template = _template(model)
    return template.clone_with_options(inverter_options_from_config(entry_config or {}, template), "S2_WL_ST")


def _select(model, entry_config=None, *, trim=True):
    """What async_setup_entry builds: (start, registers, uniques) per polled group, and derived uniques."""
    cfg = _config(model, entry_config)
    if cfg.type in (InverterType.STRING, InverterType.GRID):
        sensors, derived = string_sensors, string_sensors_derived
    else:
        sensors, derived = hybrid_sensors, hybrid_sensors_derived
    known = registers_declared_by(sensors)
    if trim:
        sensors, derived = apply_mppt_count(sensors, derived, cfg.mppt_count, cfg.string_count)
    groups = [g for g in sensors if not g.get("feature_requirement") or any(f in cfg.features for f in g["feature_requirement"])]
    polled = registers_declared_by(groups)
    supported = [d["unique"] for d in derived if derived_sensor_is_supported(d, polled, known)]
    shape = [(g["register_start"], tuple(int(r) for e in g["entities"] for r in e["register"]), tuple(e.get("unique") for e in g["entities"])) for g in groups]
    return shape, supported


def _uniques(model, entry_config=None):
    shape, derived = _select(model, entry_config)
    return {u for _, _, uniques in shape for u in uniques if u} | set(derived)


def _group(model, start, entry_config=None):
    shape, _ = _select(model, entry_config)
    return next((regs for s, regs, _ in shape if s == start), None)


# --- Backward compatibility ---------------------------------------------------------


@pytest.mark.parametrize("model", LEGACY_MODELS)
def test_existing_entries_keep_exactly_their_groups_and_entities(model):
    """No count stored (every entry made before the option) = the same reads and entities as before."""
    assert _config(model).mppt_count == LEGACY_MPPT_COUNT
    assert _select(model) == _select(model, trim=False)


@pytest.mark.parametrize("model", LEGACY_MODELS)
def test_existing_dc_entities_are_unchanged(model):
    # Energy-storage models default to no PV; with PV on they get the same four.
    uniques = _uniques(model, {"has_pv": True})
    prefix = "solis_modbus_dc_" if _config(model).type in (InverterType.STRING, InverterType.GRID) else "solis_modbus_inverter_dc_"
    for n in range(1, 5):
        assert {f"{prefix}voltage_{n}", f"{prefix}current_{n}", f"{prefix}power_{n}"} <= uniques
    assert not any(u.startswith(prefix) and u.rsplit("_", 1)[1] == "5" for u in uniques)


def test_dc_1_to_4_keep_their_registers():
    entities = {e["unique"]: e["register"] for g in string_sensors for e in g["entities"] if e.get("unique")}
    for n in range(1, 5):
        assert entities[f"solis_modbus_dc_voltage_{n}"] == [str(3019 + 2 * n)]
        assert entities[f"solis_modbus_dc_current_{n}"] == [str(3020 + 2 * n)]


def test_unknown_or_bad_stored_counts_are_clamped():
    assert _config("S5-GR3P", {CONF_MPPT_COUNT: 9}).mppt_count == 4
    assert _config("S5-GR3P", {CONF_MPPT_COUNT: 0}).mppt_count == 1
    assert _config(GC_MODEL, {CONF_MPPT_COUNT: 9}).mppt_count == 6
    assert _config(MULTI_MPPT_MODEL, {CONF_MPPT_COUNT: 40}).mppt_count == 15


# --- The count on the existing four -----------------------------------------------


def test_string_model_with_two_mppts_drops_dc_3_and_4():
    uniques = _uniques("S6-GR1P", {CONF_MPPT_COUNT: 2})
    assert {"solis_modbus_dc_voltage_2", "solis_modbus_dc_current_2", "solis_modbus_dc_power_2"} <= uniques
    assert not uniques & {"solis_modbus_dc_voltage_3", "solis_modbus_dc_current_4", "solis_modbus_dc_power_3", "solis_modbus_dc_power_4"}
    # DC 3/4 were the last registers of the 2999 block, so they are no longer read at all.
    assert _group("S6-GR1P", 2999, {CONF_MPPT_COUNT: 2})[-1] == 3024


def test_hybrid_with_two_mppts_drops_pv_3_and_4_but_keeps_the_block():
    uniques = _uniques("S6-EH1P", {CONF_MPPT_COUNT: 2})
    assert "solis_modbus_inverter_dc_power_2" in uniques
    assert not uniques & {"solis_modbus_inverter_dc_voltage_3", "solis_modbus_inverter_dc_current_4", "solis_modbus_inverter_dc_power_3"}
    # Total DC output follows them in the same block, so their registers are still read.
    assert _group("S6-EH1P", 33049, {CONF_MPPT_COUNT: 2}) == tuple(range(33049, 33059))


def test_definitions_are_not_mutated_by_trimming():
    before = repr(string_sensors) + repr(string_sensors_derived)
    _select("S6-GR1P", {CONF_MPPT_COUNT: 1})
    _select(MULTI_MPPT_MODEL, {CONF_MPPT_COUNT: 5})
    assert repr(string_sensors) + repr(string_sensors_derived) == before


# --- Multi-MPPT models --------------------------------------------------------------


def test_multi_mppt_model():
    template = _template(MULTI_MPPT_MODEL)
    assert template.type == InverterType.GRID
    assert InverterFeature.MULTI_MPPT in template.features
    assert (template.max_mppts, template.default_mppts, template.strings_per_mppt) == (15, 10, 2)
    cfg = template.clone_with_options(InverterOptions(), "S2_WL_ST")
    assert InverterFeature.MULTI_MPPT in cfg.features
    assert (cfg.mppt_count, cfg.string_count) == (10, 20)


@pytest.mark.parametrize("model", ["S5-GR3P", "S6-GR1P", "3P(3-20)K-4G", "1P(2.5-6)K-4G"])
def test_other_string_models_do_not_get_multi_mppt(model):
    template = _template(model)
    assert InverterFeature.MULTI_MPPT not in template.features
    assert template.max_mppts == LEGACY_MPPT_COUNT
    assert template.strings_per_mppt == 0


@pytest.mark.parametrize(
    ("count", "strings", "mppt_block"),
    [
        (10, 20, (3503, 3538)),  # field-verified Solis-100K-5G
        (9, 18, (3503, 3537)),  # 80K-5G
        (8, 16, (3503, 3536)),  # 100/110K-5G-PRO
        (6, 12, (3503, 3534)),  # 80K-5G-PRO
        (15, 20, (3503, 3543)),  # protocol maximum; 20 string registers known
        (4, 8, None),  # no MPPT above 4: block not read
    ],
)
def test_multi_mppt_count_sets_entities_and_reads(count, strings, mppt_block):
    entry = {CONF_MPPT_COUNT: count}
    uniques = _uniques(MULTI_MPPT_MODEL, entry)
    for n in range(1, 16):
        expected = n <= count
        for kind in ("voltage", "current", "power"):
            assert (f"solis_modbus_dc_{kind}_{n}" in uniques) is expected, (kind, n)
    for k in range(1, 21):
        assert (f"solis_modbus_pv_string_current_{k}" in uniques) is (k <= strings), k
    assert {"solis_modbus_total_pv_voltage", "solis_modbus_total_pv_current", "solis_modbus_pv_string_combination"} <= uniques

    string_block = _group(MULTI_MPPT_MODEL, 3286, entry)
    assert (string_block[0], string_block[-1]) == (3286, 3299 + strings)
    block = _group(MULTI_MPPT_MODEL, 3503, entry)
    assert (block[0], block[-1]) == mppt_block if mppt_block else block is None
    if block:
        assert block == tuple(range(block[0], block[-1] + 1))


def test_gc_model():
    template = _template(GC_MODEL)
    assert InverterFeature.MULTI_MPPT in template.features
    assert (template.max_mppts, template.default_mppts, template.strings_per_mppt) == (6, 4, 2)


def test_existing_gc_entries_keep_dc_1_to_4_and_gain_the_string_currents(monkeypatch):
    """No count stored: the same DC 1-4 entities and reads as before, plus 8 string currents."""
    shape, derived = _select(GC_MODEL)
    # The S5-GC as it was before MULTI_MPPT: same template, no multi-MPPT fields.
    template = _template(GC_MODEL)
    monkeypatch.setattr(template, "_intrinsic_features", [f for f in template._intrinsic_features if f != InverterFeature.MULTI_MPPT])
    monkeypatch.setattr(template, "max_mppts", LEGACY_MPPT_COUNT)
    monkeypatch.setattr(template, "strings_per_mppt", 0)
    before_shape, before_derived = _select(GC_MODEL)
    monkeypatch.undo()
    assert _config(GC_MODEL).mppt_count == LEGACY_MPPT_COUNT
    uniques = _uniques(GC_MODEL)
    for n in range(1, 5):
        assert {f"solis_modbus_dc_voltage_{n}", f"solis_modbus_dc_current_{n}", f"solis_modbus_dc_power_{n}"} <= uniques
    assert not uniques & {"solis_modbus_dc_voltage_5", "solis_modbus_dc_power_5"}
    assert _group(GC_MODEL, 3503) is None
    assert {f"solis_modbus_pv_string_current_{k}" for k in range(1, 9)} <= uniques
    assert "solis_modbus_pv_string_current_9" not in uniques
    # Everything else is what the model had before: only the string block is new.
    assert [g for g in shape if g[0] != 3286] == before_shape
    assert set(derived) == set(before_derived)


@pytest.mark.parametrize(
    ("count", "strings", "mppt_block"),
    [
        (3, 6, None),  # 25-33K
        (4, 8, None),  # 36-40K
        (5, 10, (3503, 3533)),  # 50K
        (6, 12, (3503, 3534)),  # 60K
    ],
)
def test_gc_count_sets_entities_and_reads(count, strings, mppt_block):
    entry = {CONF_MPPT_COUNT: count}
    uniques = _uniques(GC_MODEL, entry)
    for n in range(1, 16):
        for kind in ("voltage", "current", "power"):
            assert (f"solis_modbus_dc_{kind}_{n}" in uniques) is (n <= count), (kind, n)
    for k in range(1, 21):
        assert (f"solis_modbus_pv_string_current_{k}" in uniques) is (k <= strings), k
    string_block = _group(GC_MODEL, 3286, entry)
    assert (string_block[0], string_block[-1]) == (3286, 3299 + strings)
    block = _group(GC_MODEL, 3503, entry)
    assert (block[0], block[-1]) == mppt_block if mppt_block else block is None


def test_multi_mppt_groups_are_the_last_normal_groups():
    """A timeout ends the batch, so no other normal-speed group may come after these."""
    normal = [g["register_start"] for g in string_sensors if g.get("poll_speed", PollSpeed.NORMAL) == PollSpeed.NORMAL]
    assert normal[-2:] == [3286, 3503]


def test_gc_with_three_mppts_stops_reading_dc_4():
    assert _group(GC_MODEL, 2999, {CONF_MPPT_COUNT: 3})[-1] == 3026


@pytest.mark.parametrize("n", range(5, 16))
def test_extended_mppt_registers(n):
    entities = {e["unique"]: e for g in string_sensors for e in g["entities"] if e.get("unique")}
    assert entities[f"solis_modbus_dc_voltage_{n}"]["register"] == [str(3498 + n)]
    assert entities[f"solis_modbus_dc_current_{n}"]["register"] == [str(3528 + n)]
    derived = next(d for d in string_sensors_derived if d["unique"] == f"solis_modbus_dc_power_{n}")
    assert derived["register"] == [str(3498 + n), str(3528 + n)]


@pytest.mark.parametrize("k", range(1, 21))
def test_string_current_registers(k):
    entity = next(e for g in string_sensors for e in g["entities"] if e.get("unique") == f"solis_modbus_pv_string_current_{k}")
    assert entity["register"] == [str(3299 + k)]
    assert entity["multiplier"] == 0.1


def test_string_combination_is_not_a_statistic():
    entity = next(e for g in string_sensors for e in g["entities"] if e.get("unique") == "solis_modbus_pv_string_combination")
    assert "state_class" not in entity


# --- Detection ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dc_input_type", "combination", "expected"),
    [
        (19, 0, 10),  # Solis-100K-5G, field-verified
        (17, 0, 9),
        (11, 0, 6),
        (19, 3, None),  # three strings per MPPT is not how this model is laid out
        (18, 0, None),  # 19 inputs don't split into pairs
        (39, 0, None),  # 20 MPPTs: more than the protocol has
        (19, 7, None),  # unknown combination code
    ],
)
def test_mppt_count_from_registers(dc_input_type, combination, expected):
    assert mppt_count_from_registers(dc_input_type, combination, _template(MULTI_MPPT_MODEL)) == expected


@pytest.mark.parametrize(
    ("dc_input_type", "combination", "expected"),
    [
        (5, 0, 3),  # 25-33K: 6 strings
        (7, 0, 4),  # 36-40K
        (9, 0, 5),  # 50K
        (11, 0, 6),  # 60K
        (13, 0, None),  # 7 MPPTs: more than the GC has
        (5, 3, None),  # three strings per MPPT is not how the GC is laid out
    ],
)
def test_gc_mppt_count_from_registers(dc_input_type, combination, expected):
    assert mppt_count_from_registers(dc_input_type, combination, _template(GC_MODEL)) == expected


def test_mppt_count_is_not_detected_on_models_without_strings():
    assert mppt_count_from_registers(3, 0, _template("S5-GR3P")) is None


def _registers(*values):
    result = MagicMock()
    result.isError.return_value = False
    result.registers = list(values)
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize(("model", "dc_input_type", "expected"), [(MULTI_MPPT_MODEL, 17, 9), (GC_MODEL, 5, 3)])
async def test_setup_reads_the_mppt_count_on_a_multi_mppt_model(hass, model, dc_input_type, expected):
    from custom_components.solis_modbus.config_flow import ModbusConfigFlow

    flow = ModbusConfigFlow()
    flow.hass = hass
    reads = {3041: _registers(0), 3003: _registers(dc_input_type), 3286: _registers(0)}
    client = MagicMock(connect=AsyncMock(), connected=True)
    client.read_input_registers = AsyncMock(side_effect=lambda address, count, device_id: reads[address])

    with patch("custom_components.solis_modbus.config_flow.AsyncModbusTcpClient", return_value=client):
        valid, _ = await flow._validate_config({"connection_type": CONN_TYPE_TCP, "host": "1.2.3.4", "slave": 1, "model": model})

    assert valid
    data = {"model": model}
    flow._apply_mppt_count(data)
    assert data[CONF_MPPT_COUNT] == expected


@pytest.mark.asyncio
async def test_setup_does_not_read_the_mppt_count_on_other_models(hass):
    from custom_components.solis_modbus.config_flow import ModbusConfigFlow

    flow = ModbusConfigFlow()
    flow.hass = hass
    client = MagicMock(connect=AsyncMock(), connected=True)
    client.read_input_registers = AsyncMock(return_value=_registers(0))

    with patch("custom_components.solis_modbus.config_flow.AsyncModbusTcpClient", return_value=client):
        valid, _ = await flow._validate_config({"connection_type": CONN_TYPE_TCP, "host": "1.2.3.4", "slave": 1, "model": "S5-GR3P"})

    assert valid
    client.read_input_registers.assert_awaited_once()  # the probe only
    data = {"model": "S5-GR3P", CONF_MPPT_COUNT: 3}
    flow._apply_mppt_count(data)
    assert CONF_MPPT_COUNT not in data


@pytest.mark.asyncio
async def test_failed_mppt_read_keeps_the_model_default(hass):
    from custom_components.solis_modbus.config_flow import _read_mppt_count

    client = MagicMock()
    client.read_input_registers = AsyncMock(side_effect=ConnectionError("timeout"))
    assert await _read_mppt_count(client, 1, _template(MULTI_MPPT_MODEL)) is None


# --- Options flow -------------------------------------------------------------------


def _entry(hass, model, data_extra=None, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"SN{model}",
        version=5,
        data={
            "connection_type": CONN_TYPE_TCP,
            "inverter_serial": f"SN{model}",
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1,
            "model": model,
            "connection": "S2_WL_ST",
            "poll_interval_fast": 10,
            "poll_interval_normal": 15,
            "poll_interval_slow": 30,
            **(data_extra or {}),
        },
        options=options or {},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def custom_integration(enable_custom_integrations):
    """Options flows need the integration loadable."""


async def _submit_options(hass, entry, **changes):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"]
    shown = {k.schema: (k.description or {}).get("suggested_value") for k in schema.schema}
    user_input = {"poll_interval_fast": 10, "poll_interval_normal": 15, "poll_interval_slow": 30, "model": entry.data["model"]}
    if shown.get(CONF_MPPT_COUNT) is not None:
        user_input[CONF_MPPT_COUNT] = shown[CONF_MPPT_COUNT]
    user_input.update(changes)
    with patch("custom_components.solis_modbus.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(result["flow_id"], user_input=user_input)
        await hass.async_block_till_done()
    return shown, result


@pytest.mark.asyncio
@pytest.mark.usefixtures("custom_integration")
async def test_options_show_the_model_default_and_do_not_store_it(hass):
    entry = _entry(hass, "S5-GC")
    shown, result = await _submit_options(hass, entry)
    assert shown[CONF_MPPT_COUNT] == 4
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert CONF_MPPT_COUNT not in entry.options


@pytest.mark.asyncio
@pytest.mark.usefixtures("custom_integration")
async def test_options_store_a_changed_count(hass):
    entry = _entry(hass, "S6-GR1P")
    _, result = await _submit_options(hass, entry, **{CONF_MPPT_COUNT: 2})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MPPT_COUNT] == 2


@pytest.mark.asyncio
@pytest.mark.usefixtures("custom_integration")
@pytest.mark.parametrize(("model", "count"), [("S5-GR3P", 5), (GC_MODEL, 7)])
async def test_options_reject_more_mppts_than_the_model_has(hass, model, count):
    entry = _entry(hass, model)
    _, result = await _submit_options(hass, entry, **{CONF_MPPT_COUNT: count})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "mppt_count_above_model_max"}


@pytest.mark.asyncio
@pytest.mark.usefixtures("custom_integration")
async def test_options_show_the_detected_count(hass):
    entry = _entry(hass, MULTI_MPPT_MODEL, data_extra={CONF_MPPT_COUNT: 9})
    shown, _ = await _submit_options(hass, entry)
    assert shown[CONF_MPPT_COUNT] == 9
    assert CONF_MPPT_COUNT not in entry.options


@pytest.mark.asyncio
@pytest.mark.usefixtures("custom_integration")
async def test_switching_to_a_multi_mppt_model_does_not_carry_the_old_count(hass):
    """A 100K first set up as S5-GC: the form shows 4; switching the model must give the new default, not 4."""
    entry = _entry(hass, "S5-GC")
    _, result = await _submit_options(hass, entry, model=MULTI_MPPT_MODEL)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert CONF_MPPT_COUNT not in entry.options
    assert _config(MULTI_MPPT_MODEL, {**entry.data, **entry.options}).mppt_count == 10


@pytest.mark.asyncio
@pytest.mark.usefixtures("custom_integration")
async def test_switching_model_drops_a_count_chosen_for_the_old_one(hass):
    entry = _entry(hass, "S6-GR1P", options={CONF_MPPT_COUNT: 2})
    _, result = await _submit_options(hass, entry, model="S5-GC")
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert CONF_MPPT_COUNT not in entry.options


@pytest.mark.asyncio
@pytest.mark.usefixtures("custom_integration")
async def test_switching_model_keeps_a_count_set_in_the_same_save(hass):
    entry = _entry(hass, "S5-GC")
    _, result = await _submit_options(hass, entry, model=MULTI_MPPT_MODEL, **{CONF_MPPT_COUNT: 8})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MPPT_COUNT] == 8


# --- DC Power 5-15 ------------------------------------------------------------------


@pytest.fixture
def mppt_base_sensor():
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.slave = 1
    controller.device_id = 1
    sensor = MagicMock()
    sensor.controller = controller
    sensor.name = "DC Power 5"
    sensor.unique_id = "test_dc_power_5"
    sensor.registrars = [3503, 3533]
    sensor.multiplier = 0.1
    sensor.device_class = None
    sensor.unit_of_measurement = None
    sensor.hidden = False
    sensor.state_class = "measurement"
    return sensor


def _send(sensor, register, value):
    sensor.handle_modbus_update({REGISTER: register, VALUE: value, CONTROLLER: "1.2.3.4", SLAVE: 1})


@pytest.mark.parametrize(
    ("current_raw", "expected"),
    [
        (67, 2295),  # 342.6 V x 6.7 A
        (0, 0),
        (0xFFFF, -34),  # -0.1 A, signed
    ],
)
def test_dc_power(hass, mppt_base_sensor, current_raw, expected):
    sensor = SolisDerivedSensor(hass, mppt_base_sensor)
    with patch.object(sensor, "schedule_update_ha_state"):
        _send(sensor, 3503, 3426)
        _send(sensor, 3533, current_raw)
    assert sensor.native_value == expected


def test_dc_power_ignores_a_current_left_over_from_a_read_without_voltage(hass, mppt_base_sensor):
    """600 V with a stale 10 A must not give 6000 W when the fresh current is 20 A."""
    sensor = SolisDerivedSensor(hass, mppt_base_sensor)
    with patch.object(sensor, "schedule_update_ha_state") as update:
        _send(sensor, 3533, 100)  # poll N: current only (voltage missing)
        assert update.call_count == 0
        _send(sensor, 3503, 6000)  # poll N+1: 600.0 V ...
        assert update.call_count == 0  # ... not multiplied by the stale 10 A
        _send(sensor, 3533, 200)  # ... then 20.0 A
    assert update.call_count == 1
    assert sensor.native_value == 12000


def test_dc_power_ignores_a_voltage_left_over_from_a_read_without_current(hass, mppt_base_sensor):
    sensor = SolisDerivedSensor(hass, mppt_base_sensor)
    with patch.object(sensor, "schedule_update_ha_state") as update:
        _send(sensor, 3503, 5000)  # poll N: 500.0 V, current missing
        _send(sensor, 3503, 6000)  # poll N+1: 600.0 V
        _send(sensor, 3533, 200)  # 20.0 A
    assert update.call_count == 1
    assert sensor.native_value == 12000


def test_dc_power_stays_in_step_after_a_missed_read(hass, mppt_base_sensor):
    sensor = SolisDerivedSensor(hass, mppt_base_sensor)
    with patch.object(sensor, "schedule_update_ha_state"):
        _send(sensor, 3533, 100)
        for voltage, current, expected in [(6000, 200, 12000), (6100, 300, 18300), (5900, 50, 2950)]:
            _send(sensor, 3503, voltage)
            _send(sensor, 3533, current)
            assert sensor.native_value == expected


def test_dc_power_1_to_4_keep_the_classic_path(hass, mppt_base_sensor):
    mppt_base_sensor.registrars = [3021, 3022]
    mppt_base_sensor.get_value = 0
    sensor = SolisDerivedSensor(hass, mppt_base_sensor)
    with patch.object(sensor, "schedule_update_ha_state"):
        _send(sensor, 3021, 3426)
        _send(sensor, 3022, 67)
    assert sensor.native_value == 2295
