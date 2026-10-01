"""SAPN Flexible Export (issue #499): 43292 is the execution switch (0x00AA on,
0x0000 off — every other value invalid), 43291 the export limit it applies.

Turning the switch OFF used to write 0x55, which the inverter ignores, so the
switch stayed on and export stayed capped at the (default 0 W) 43291 limit.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.solis_modbus.const import CONTROLLER, REGISTER, SLAVE, VALUE
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors, hybrid_sensors_derived
from custom_components.solis_modbus.sensor_data.switch_sensors import get_switch_sensors
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup
from custom_components.solis_modbus.sensors.solis_binary_sensor import SolisBinaryEntity
from custom_components.solis_modbus.sensors.solis_derived_sensor import (
    FLEXIBLE_EXPORT_ACTIVE,
    FLEXIBLE_EXPORT_BLOCKED,
    FLEXIBLE_EXPORT_OFF,
    SolisDerivedSensor,
)
from custom_components.solis_modbus.sensors.solis_number_sensor import SolisNumberEntity


def _flexible_export_switch():
    hybrid = next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH1P")
    for group in get_switch_sensors(hybrid):
        for entity in group["entities"]:
            if entity["name"] == "Flexible Export Enabling Switch":
                return group["register"], entity
    raise AssertionError("Flexible Export Enabling Switch not defined")


def _make_switch(cached_value):
    register, definition = _flexible_export_switch()
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.device_id = 1
    controller.connected.return_value = True
    controller.async_write_holding_register = AsyncMock()
    entity = SolisBinaryEntity(MagicMock(), controller, {**definition, "register": register, "write_register": None})
    cache = {register: cached_value}
    return entity, controller, cache


def test_switch_uses_spec_values():
    register, definition = _flexible_export_switch()
    assert register == 43292
    assert definition["on_value"] == 0xAA
    assert definition["off_value"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(("turn_on", "cached", "expected"), [(False, 0xAA, 0), (True, 0, 0xAA)])
async def test_switch_writes_spec_values(turn_on, cached, expected):
    entity, controller, cache = _make_switch(cached)
    with (
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_get", side_effect=lambda h, c, r: cache.get(r)),
        patch("custom_components.solis_modbus.sensors.solis_binary_sensor.cache_save"),
    ):
        await (entity.async_turn_on() if turn_on else entity.async_turn_off())
    controller.async_write_holding_register.assert_awaited_once_with(43292, expected)


def test_switch_disabled_in_registry_by_default():
    entity, _, _ = _make_switch(0)
    assert entity.entity_registry_enabled_default is False


def test_export_limit_control_disabled_but_still_polled():
    """Registry-disabled only: 43291 must still be polled for the status sensor."""
    definition = next(g for g in hybrid_sensors if g.get("register_start") == 43291)
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.device_serial_number = None
    controller.identification = None
    group = SolisSensorGroup(hass=MagicMock(), definition=definition, controller=controller)
    limit = next(s for s in group.sensors if s.registrars == [43291])

    assert limit.enabled is True  # still polled
    assert SolisNumberEntity(MagicMock(), limit).entity_registry_enabled_default is False


def test_status_sensor_defined():
    status = next(e for e in hybrid_sensors_derived if e["unique"] == "solis_modbus_inverter_flexible_export_status")
    assert status["register"] == ["43292", "43291"]


@pytest.mark.parametrize(
    ("switch_value", "limit", "expected"),
    [
        (0, 0, FLEXIBLE_EXPORT_OFF),
        (0x55, 0, FLEXIBLE_EXPORT_OFF),
        (0xAA, 0, FLEXIBLE_EXPORT_BLOCKED),
        (0xAA, 80, FLEXIBLE_EXPORT_ACTIVE),
    ],
)
def test_status_sensor_states(hass: HomeAssistant, switch_value, limit, expected):
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.device_id = 1
    base = MagicMock()
    base.controller = controller
    base.name = "Flexible Export Status"
    base.unique_id = "flexible_export_status"
    base.registrars = [43292, 43291]
    base.multiplier = 0
    base.device_class = None
    base.unit_of_measurement = None
    base.hidden = False
    base.state_class = None
    base.get_value = 0
    sensor = SolisDerivedSensor(hass, base)

    with patch.object(sensor, "schedule_update_ha_state"):
        sensor.handle_modbus_update({REGISTER: 43292, VALUE: switch_value, CONTROLLER: "1.2.3.4", SLAVE: 1})
        sensor.handle_modbus_update({REGISTER: 43291, VALUE: limit, CONTROLLER: "1.2.3.4", SLAVE: 1})

    assert sensor.native_value == expected
