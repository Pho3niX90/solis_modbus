"""Regression guards for issue #452 — unique_id must not embed entity definition dicts.

v4.2.0 created duplicate entities because SolisSensorGroup passed the whole entity
dict into unique_id_generator, so unique IDs became ``..._{str(dict)}``. Adding
``data_type: U32`` (or any other key) then changed the unique_id and HA registered
a second entity.

These tests fail if that call-site or stringification pattern returns.
"""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest

from custom_components.solis_modbus.const import DOMAIN
from custom_components.solis_modbus.data.enums import DataType, PollSpeed
from custom_components.solis_modbus.helpers import unique_id_generator
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors
from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup


def _controller(serial="SN_REGRESSION"):
    controller = MagicMock()
    controller.device_serial_number = serial
    controller.identification = None
    controller.host = "10.0.0.1"
    controller.inverter_config = MagicMock()
    controller.inverter_config.model = "S6-EH3P"
    controller.inverter_config.features = set()
    controller.inverter_config.wattage_chosen = 10000
    return controller


def _build_group(controller, group):
    definition = deepcopy(group)
    definition.setdefault("poll_speed", PollSpeed.NORMAL)
    return SolisSensorGroup(hass=MagicMock(), definition=definition, controller=controller)


def test_adding_data_type_does_not_change_unique_id():
    """Exact #452 shape: tagging a lifetime total as U32 must not mint a new unique_id."""
    controller = _controller()
    base_entity = {
        "name": "Backup Load Total Energy",
        "unique": "solis_modbus_inverter_backup_total_energy",
        "register": ["33590", "33591"],
        "multiplier": 0,
    }
    with_u32 = {**base_entity, "data_type": DataType.U32}

    group_before = _build_group(
        controller,
        {"register_start": 33590, "poll_speed": PollSpeed.SLOW, "entities": [base_entity]},
    )
    group_after = _build_group(
        controller,
        {"register_start": 33590, "poll_speed": PollSpeed.SLOW, "entities": [with_u32]},
    )

    uid_before = group_before.sensors[0].unique_id
    uid_after = group_after.sensors[0].unique_id
    expected = f"{DOMAIN}_SN_REGRESSION_solis_modbus_inverter_backup_total_energy"

    assert uid_before == expected
    assert uid_after == expected
    assert uid_before == uid_after
    assert "{" not in uid_before
    assert "data_type" not in uid_after


def test_arbitrary_definition_keys_do_not_change_unique_id():
    """Any future definition field must leave unique_id keyed only on ``unique``."""
    controller = _controller()
    unique_key = "solis_modbus_inverter_pv_total_generation"
    minimal = {
        "name": "PV Total Energy Generation",
        "unique": unique_key,
        "register": ["33029", "33030"],
    }
    bloated = {
        **minimal,
        "category": "PV_INFORMATION",
        "data_type": DataType.U32,
        "device_class": "energy",
        "state_class": "total_increasing",
        "multiplier": 0,
        "hidden": False,
        "enabled": True,
        "_future_flag": True,
    }

    a = _build_group(controller, {"register_start": 33029, "entities": [minimal]}).sensors[0].unique_id
    b = _build_group(controller, {"register_start": 33029, "entities": [bloated]}).sensors[0].unique_id
    assert a == b == f"{DOMAIN}_SN_REGRESSION_{unique_key}"


@pytest.mark.parametrize(
    "name,groups",
    [
        ("hybrid", hybrid_sensors),
        ("string", string_sensors),
    ],
)
def test_all_sensor_group_unique_ids_are_stable_format(name, groups):
    """Every SolisSensorGroup entity unique_id must be DOMAIN_serial_<unique key>.

    Catches a return of ``unique_id_generator(controller, entity)`` with the whole
    dict: those IDs contain ``{`` / ``'unique':``.
    """
    controller = _controller(serial="SN_MATRIX")
    offenders = []

    for group in groups:
        built = _build_group(controller, group)
        for entity_def, sensor in zip(group.get("entities", []), built.sensors, strict=False):
            if entity_def.get("type") == "reserve":
                continue
            unique_key = entity_def.get("unique", "reserve")
            expected = unique_id_generator(controller, unique_key)
            uid = sensor.unique_id
            if uid != expected:
                offenders.append(f"{name}:{unique_key}: got {uid!r} expected {expected!r}")
            if "{" in uid or "'unique':" in uid or "data_type" in uid:
                offenders.append(f"{name}:{unique_key}: looks dict-stringified: {uid!r}")

    assert not offenders, "unstable unique_ids (#452 regression):\n  " + "\n  ".join(offenders[:20])


def test_unique_id_generator_dict_guard_ignores_extra_keys():
    """Safety net: even if a caller passes a dict, only ``unique`` is used."""
    controller = _controller(serial="SN_GUARD")
    key = "solis_modbus_inverter_total_battery_charge_energy"
    plain = unique_id_generator(controller, {"unique": key, "name": "A"})
    with_extra = unique_id_generator(
        controller,
        {"unique": key, "name": "A", "data_type": DataType.U32, "register": ["33161", "33162"]},
    )
    assert plain == with_extra == f"{DOMAIN}_SN_GUARD_{key}"
    assert "{" not in plain
