"""Bounds must come from an authority, never from a guess.

#438, #441 and #455 were three instances of one cause: a ceiling derived from the
inverter's AC rating, applied to every editable entity because it was keyed off the unit.
A change aimed at one register silently retargeted all of them.

These tests lock the resolution order in place rather than the individual numbers:

1. a declared ``"max"`` must be a value the register can actually carry;
2. omitting ``"max"`` must never produce a rating-derived ceiling;
3. only an explicit ``"max_source"`` reaches ``wattage_chosen``.
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
    """RC force charge/discharge must reach the inverter's own nameplate."""

    @pytest.mark.parametrize("register", [43027, 43129, 43130, 43131, 43136])
    def test_a_20kw_inverter_can_dispatch_20kw(self, register):
        entity = next(e for e in ENTITIES if e["register"] == [str(register)])
        sensor = _build(entity, _controller(wattage_chosen=20000))

        assert sensor.max_value == 20000

    @pytest.mark.parametrize("register", [43128, 43133, 43134])
    def test_signed_dispatch_registers_stay_symmetric(self, register):
        entity = next(e for e in ENTITIES if e["register"] == [str(register)])
        sensor = _build(entity, _controller(wattage_chosen=20000))

        assert sensor.max_value == 20000
        assert sensor.min_value == -20000
