"""Bounds must come from an authority, never from a guess.

#438, #441 and #455 were three instances of one cause: a ceiling derived from the
inverter's AC rating, applied to every editable entity because it was keyed off the unit.
A change aimed at one register silently retargeted all of them.

#464 and #467 then showed the inverse failure: an *authoritative* bound that moves (the
BMS mirror derating with SOC, or echoing the setpoint back) rejects legitimate writes
and strands states above their own max. So authorities don't set bounds either — they
are surfaced as an advisory ``device_limit``.

These tests lock the resolution order in place rather than the individual numbers:

1. a declared ``"max"`` must be a value the register can actually carry;
2. omitting ``"max"`` resolves to the protocol ceiling — never a rating-derived one;
3. only an explicit ``"max_source"`` reaches ``wattage_chosen``, and only as the
   advisory ``device_limit``, never as the advertised max.
"""

import pytest
from homeassistant.const import UnitOfElectricPotential

from custom_components.solis_modbus.data.enums import InverterFeature
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors
from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors
from custom_components.solis_modbus.sensors.solis_base_sensor import (
    DATA_TYPE_RAW_RANGES,
    HV_BATTERY_VOLTAGE_MAX,
    HV_BATTERY_VOLTAGE_REGISTERS,
    MAX_SOURCE_INVERTER_RATING,
    SolisBaseSensor,
)


def _controller(wattage_chosen=8000, features=()):
    class MockConfig:
        model = "TEST"

    MockConfig.features = list(features)
    MockConfig.wattage_chosen = wattage_chosen

    class MockController:
        inverter_config = MockConfig()
        device_serial_number = "SN"
        identification = None
        host = "127.0.0.1"

    return MockController()


def _editable_entities():
    for group in list(hybrid_sensors) + list(string_sensors):
        for entity in group.get("entities", []):
            if entity.get("editable"):
                yield entity


def _build(entity, controller):
    return SolisBaseSensor(
        hass=None,
        controller=controller,
        unique_id="u",
        name=entity.get("name", "n"),
        registrars=[int(r) for r in entity["register"]],
        write_register=entity.get("write_register"),
        multiplier=entity.get("multiplier", 1),
        unit_of_measurement=entity.get("unit_of_measurement"),
        editable=True,
        step=entity.get("step"),
        min_value=entity.get("min", 0),
        max_value=entity.get("max"),
        max_source=entity.get("max_source"),
        data_type=entity.get("data_type"),
    )


ENTITIES = list(_editable_entities())
IDS = [f"{e['register'][0]}-{e.get('name', '?')}" for e in ENTITIES]


@pytest.mark.parametrize("entity", ENTITIES, ids=IDS)
def test_declared_bounds_fit_the_register(entity):
    """A literal above the protocol ceiling would be unwritable — the inverter can't hold it."""
    sensor = _build(entity, _controller())
    raw_min, raw_max = sensor.protocol_raw_range
    scale = entity.get("multiplier", 1) or 1

    if entity.get("max") is not None:
        assert entity["max"] <= raw_max * scale, f"declared max exceeds what the register can carry ({raw_max * scale})"
    if entity.get("min") is not None:
        assert entity["min"] >= raw_min * scale, f"declared min is below what the register can carry ({raw_min * scale})"


@pytest.mark.parametrize("entity", ENTITIES, ids=IDS)
def test_the_inverter_rating_is_never_reached_implicitly(entity):
    """Only "max_source" may consult wattage_chosen — the unit must imply nothing.

    Two inverters, one small and one large, must resolve the same bound for every
    definition that did not explicitly ask for the rating.
    """
    if entity.get("max_source") is not None:
        pytest.skip("opts into the rating explicitly")

    small = _build(entity, _controller(wattage_chosen=3000))
    large = _build(entity, _controller(wattage_chosen=20000))

    assert small.max_value == large.max_value
    assert small.min_value == large.min_value


@pytest.mark.parametrize("entity", ENTITIES, ids=IDS)
def test_the_rating_is_only_ever_an_opt_in(entity):
    """Guards the key itself: a typo'd source silently reverts to the protocol ceiling."""
    source = entity.get("max_source")
    assert source in (None, MAX_SOURCE_INVERTER_RATING), f"unknown max_source {source!r}"


NEGATIVE_MIN_MARKERS = [e for e in ENTITIES if e.get("min", 0) < 0 and e.get("max") is None]


def test_the_signed_marker_registers_still_exist():
    """An empty list would make the parametrized contract test below vanish silently.

    If a definition change legitimately removes the last negative-min marker (e.g. by
    declaring a max on 43128/43133/43134), this failure forces a conscious update
    here rather than a quiet loss of coverage.
    """
    assert NEGATIVE_MIN_MARKERS, "no negative-min marker entities left — update or remove the marker contract tests"


@pytest.mark.parametrize("entity", NEGATIVE_MIN_MARKERS, ids=[e["register"][0] for e in NEGATIVE_MIN_MARKERS])
def test_a_negative_min_without_a_declared_max_is_only_a_marker(entity):
    """The literal's value must never survive as the bound — only its sign is read.

    With no declared max the floor resolves to the protocol floor, whatever number
    the marker happens to be (43128/43133/43134 ship -10000 for historical reasons).
    """
    sensor = _build(entity, _controller())

    assert sensor.min_value == sensor.protocol_min
    assert sensor.min_value != entity["min"]


def test_a_fully_declared_signed_range_is_not_widened():
    """Export Calibration (43195) declares both bounds — the ±1000 trim survives.

    The protocol floor only replaces a negative min when the ceiling was derived;
    a definition that declares its max keeps its declared min untouched.
    """
    entity = next(e for e in ENTITIES if e["register"] == ["43195"])
    sensor = _build(entity, _controller())

    assert sensor.max_value == 1000
    assert sensor.min_value == -1000


def test_every_data_type_has_a_range():
    """A new DataType without a range would silently fall back to U16."""
    from custom_components.solis_modbus.data.enums import DataType

    missing = [dt.value for dt in DataType if dt is not DataType.STRING and dt.value not in DATA_TYPE_RAW_RANGES]
    assert not missing, f"no protocol range for {missing}"


class TestHvBatteryVoltages:
    """The LV literals are unusable on an HV pack.

    ESINV-33000ID, on the 33208-33211 read-side equivalents: "Range:40—48 ... HV Series-
    Default:120; Range 100-999". A 480 V pack (issue #393) is over every shipped literal.
    """

    @pytest.mark.parametrize("register", sorted(HV_BATTERY_VOLTAGE_REGISTERS))
    def test_hv_widens_the_ceiling(self, register):
        sensor = SolisBaseSensor(
            hass=None,
            controller=_controller(features=[InverterFeature.HV_BATTERY]),
            unique_id="u",
            name="Battery Voltage Setting",
            registrars=[register],
            write_register=register,
            multiplier=0.1,
            unit_of_measurement=UnitOfElectricPotential.VOLT,
            editable=True,
            min_value=0,
            max_value=60.0,
        )

        assert sensor.max_value == HV_BATTERY_VOLTAGE_MAX

    @pytest.mark.parametrize("register", sorted(HV_BATTERY_VOLTAGE_REGISTERS))
    def test_lv_keeps_the_declared_literal(self, register):
        """Widening must not leak onto a 48 V bank."""
        sensor = SolisBaseSensor(
            hass=None,
            controller=_controller(features=[InverterFeature.LV_BATTERY]),
            unique_id="u",
            name="Battery Voltage Setting",
            registrars=[register],
            write_register=register,
            multiplier=0.1,
            unit_of_measurement=UnitOfElectricPotential.VOLT,
            editable=True,
            min_value=0,
            max_value=60.0,
        )

        assert sensor.max_value == 60.0

    def test_a_480v_pack_is_settable(self):
        """The reproduction from #393: 2x Dyness TS17, 480 V nominal."""
        sensor = SolisBaseSensor(
            hass=None,
            controller=_controller(features=[InverterFeature.HV_BATTERY]),
            unique_id="u",
            name="Floating Charge Voltage",
            registrars=[43016],
            write_register=43016,
            multiplier=0.1,
            unit_of_measurement=UnitOfElectricPotential.VOLT,
            editable=True,
            min_value=40.0,
            max_value=60.0,
        )

        assert sensor.min_value <= 480 <= sensor.max_value


class TestIssue351:
    """RC force charge/discharge must reach the inverter's own nameplate — and beyond.

    The rating is not the advertised max (that would reject a legitimate DC-side
    setpoint or a misconfigured model's dispatch, the #464/#467 failure mode); it is
    the advisory ``device_limit``, and the bound is the protocol ceiling.
    """

    @pytest.mark.parametrize("register", [43027, 43129, 43130, 43131, 43136])
    def test_a_20kw_inverter_can_dispatch_20kw(self, register):
        entity = next(e for e in ENTITIES if e["register"] == [str(register)])
        sensor = _build(entity, _controller(wattage_chosen=20000))

        assert sensor.min_value <= 20000 <= sensor.max_value
        assert sensor.device_limit == 20000
        assert sensor.device_limit_source == MAX_SOURCE_INVERTER_RATING

    @pytest.mark.parametrize("register", [43027, 43129, 43130, 43131, 43136])
    def test_the_rating_does_not_cap_the_advertised_max(self, register):
        """A wrong-low rating must not turn into hard write rejections."""
        entity = next(e for e in ENTITIES if e["register"] == [str(register)])
        sensor = _build(entity, _controller(wattage_chosen=3000))

        assert sensor.max_value == sensor.protocol_max
        assert sensor.device_limit == 3000

    @pytest.mark.parametrize("register", [43128, 43133, 43134])
    def test_signed_dispatch_registers_open_the_full_signed_range(self, register):
        """The floor resolves like the ceiling — the protocol range, opposite direction."""
        entity = next(e for e in ENTITIES if e["register"] == [str(register)])
        sensor = _build(entity, _controller(wattage_chosen=20000))

        assert sensor.max_value == sensor.protocol_max
        assert sensor.min_value == sensor.protocol_min
        assert sensor.min_value < 0
        assert sensor.device_limit == 20000
