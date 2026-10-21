"""Replay owner-provided S6-EA1P6K-L observations through clean entity code.

The source installation used a locally modified S6-EH1P configuration. These
tests check that the S6-EA1P profile reproduces its observed sensor decoding;
they do not qualify physical accuracy, transport, or inverter writes.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.solis_modbus.const import CONTROLLER, DOMAIN, REGISTER, SLAVE, VALUE, VALUES
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, InverterOptions
from custom_components.solis_modbus.helpers import cache_save
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors, hybrid_sensors_derived
from custom_components.solis_modbus.sensor_data.select_sensors import get_select_sensors
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor, SolisSensorGroup
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor
from custom_components.solis_modbus.sensors.solis_select_entity import SolisSelectEntity
from custom_components.solis_modbus.sensors.solis_sensor import SolisSensor

CAPTURE = json.loads((Path(__file__).parent / "fixtures/s6_ea1p6k_l.json").read_text())


@pytest.mark.parametrize("snapshot", CAPTURE["snapshots"], ids=lambda snapshot: snapshot["id"])
def test_ac_coupled_profile_replays_observed_telemetry(hass, snapshot):
    hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
    template = next(config for config in SOLIS_INVERTERS if config.model == "S6-EA1P")
    config = template.clone_with_options(InverterOptions(pv=False, generator=False, hv_battery=False), "S2_WL_ST")
    controller = SimpleNamespace(
        inverter_config=config,
        device_serial_number="REPLAY_ONLY",
        identification=None,
        host="replay.invalid",
        connection_id="replay",
        device_id=1,
        poll_speed={PollSpeed.FAST: 10, PollSpeed.NORMAL: 15, PollSpeed.SLOW: 30},
    )
    for address, word in snapshot["registers"].items():
        cache_save(hass, controller, int(address), word)

    expected = snapshot["expected"]
    entities = {}
    for definition in hybrid_sensors:
        requirements = definition.get("feature_requirement", [])
        if requirements and not any(feature in config.features for feature in requirements):
            continue
        group = SolisSensorGroup(hass, definition, controller)
        for sensor in group.sensors:
            if sensor.name in expected:
                entities[sensor.name] = SolisSensor(hass, sensor)

    for definition in hybrid_sensors_derived:
        name = definition["name"]
        if name not in expected:
            continue
        sensor = SolisBaseSensor(
            hass=hass,
            controller=controller,
            unique_id=f"replay_{name}",
            name=name,
            registrars=[int(reg) for reg in definition["register"]],
            write_register=None,
            multiplier=definition.get("multiplier", 1),
            unit_of_measurement=definition.get("unit_of_measurement"),
            device_class=definition.get("device_class"),
        )
        entities[name] = SolisDerivedSensor(hass, sensor)

    assert entities.keys() == expected.keys()
    for name, entity in entities.items():
        entity.hass = hass
        with patch.object(entity, "schedule_update_ha_state"):
            for address, word in snapshot["registers"].items():
                entity.handle_modbus_update({REGISTER: int(address), VALUE: word, CONTROLLER: controller.host, SLAVE: 1})
        assert entity.available, name
        assert entity.native_value == pytest.approx(expected[name]["value"]), name
        assert entity.native_unit_of_measurement == expected[name]["unit"], name

    storage_mode = next(definition for definition in get_select_sensors(config) if definition["register"] == 43110)
    assert SolisSelectEntity(hass, controller, storage_mode).current_option == snapshot["storage_mode"]
