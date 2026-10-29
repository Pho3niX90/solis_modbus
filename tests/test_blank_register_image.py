"""Issue #540: a rebooted datalogger answers with all zeros before it relays the inverter.

Those zeros must not reach the entities: a lifetime energy counter at 0 is
recorded as a meter reset, and its recovery as the whole lifetime in one hour.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.solis_modbus.const import CONTROLLER, DOMAIN, REGISTER, SLAVE, VALUE, VALUES
from custom_components.solis_modbus.data.enums import InverterType, PollSpeed
from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS, InverterOptions
from custom_components.solis_modbus.data_retrieval import DataRetrieval
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup
from custom_components.solis_modbus.sensors.solis_sensor import SolisSensor

MODEL = 0x2105


class _Rig:
    """A controller whose datalogger serves either the inverter or a blank image."""

    def __init__(self):
        self.model = MODEL
        self.probe_ok = True
        self.block = [7, 8]
        self.cache: dict[int, int] = {}
        self.applied: list[int] = []
        self.probes = 0

        controller = MagicMock()
        controller.host = "192.168.1.100"
        controller.slave = 1
        controller.enabled = True
        controller.connected = MagicMock(return_value=True)
        controller.connection_count = 1
        controller.inverter_config.identity_register = 33000
        controller.async_read_input_registers_with_exception = AsyncMock(side_effect=lambda start, count: (list(self.block), None))
        controller._async_read_input_register_raw_detailed = AsyncMock(side_effect=self._probe)
        self.controller = controller

        hass = MagicMock()
        hass.is_running = True
        hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close())
        self.retrieval = DataRetrieval(hass, controller)

        group = MagicMock(spec=SolisSensorGroup)
        group.poll_speed = PollSpeed.SLOW
        group.start_register = 33029
        group.registrar_count = 2
        self.groups = [group]

    async def _probe(self, register, count, quiet=False):
        assert (register, count) == (33000, 1)
        self.probes += 1
        return ([self.model], None) if self.probe_ok else (None, None)

    def _save(self, hass, controller, register, value):
        self.cache[register] = value
        self.applied.append(register)

    async def poll(self):
        with (
            patch("custom_components.solis_modbus.data_retrieval.cache_save", side_effect=self._save),
            patch("custom_components.solis_modbus.data_retrieval.cache_get", side_effect=lambda hass, controller, reg: self.cache.get(reg)),
            patch("custom_components.solis_modbus.data_retrieval.notify_register_update"),
        ):
            await self.retrieval.get_modbus_updates(self.groups, PollSpeed.SLOW)
        applied, self.applied = self.applied, []
        return applied


@pytest.fixture
def rig():
    return _Rig()


async def test_blank_image_after_connect_is_not_applied(rig):
    rig.model, rig.block = 0, [0, 0]

    assert await rig.poll() == []
    assert await rig.poll() == []  # still blank: checked again on every batch
    assert rig.probes == 2

    rig.model, rig.block = MODEL, [7, 8]
    assert await rig.poll() == [33029, 33030]
    assert rig.cache == {33029: 7, 33030: 8}


async def test_real_image_is_checked_once_per_connection(rig):
    assert await rig.poll() == [33029, 33030]
    assert await rig.poll() == [33029, 33030]
    assert rig.probes == 1

    rig.controller.connection_count = 2  # reconnected
    rig.model = 0
    assert await rig.poll() == []
    assert rig.probes == 2


async def test_zeros_from_a_real_inverter_are_applied(rig):
    """Zeros with a real model number are readings (PV at night, an RTC that lost power)."""
    rig.block = [0, 0]
    assert await rig.poll() == [33029, 33030]
    assert rig.cache == {33029: 0, 33030: 0}


async def test_block_dropping_to_zero_mid_session_is_checked(rig):
    assert await rig.poll() == [33029, 33030]

    rig.model, rig.block = 0, [0, 0]  # the datalogger rebooted without the link dropping
    assert await rig.poll() == []
    assert rig.cache == {33029: 7, 33030: 8}
    assert rig.probes == 2

    rig.model, rig.block = MODEL, [7, 9]
    assert await rig.poll() == [33029, 33030]


async def test_block_already_zero_is_not_probed_again(rig):
    rig.block = [0, 0]
    await rig.poll()
    await rig.poll()
    await rig.poll()
    assert rig.probes == 1


async def test_failed_probe_keeps_the_last_verdict(rig):
    rig.model = 0
    assert await rig.poll() == []

    rig.probe_ok = False
    assert await rig.poll() == []  # a failed probe doesn't end a blank image

    rig.probe_ok, rig.model = True, MODEL
    assert await rig.poll() == [33029, 33030]


def test_identity_register_is_the_model_number():
    by_type = {config.type: config.identity_register for config in SOLIS_INVERTERS}
    assert by_type[InverterType.HYBRID] == 33000
    assert by_type[InverterType.ENERGY] == 33000
    assert by_type[InverterType.GRID] == 2999


def _energy_sensors(hass) -> dict[str, SolisSensor]:
    hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
    template = next(config for config in SOLIS_INVERTERS if config.type == InverterType.HYBRID)
    controller = SimpleNamespace(
        inverter_config=template.clone_with_options(InverterOptions(), "S2_WL_ST"),
        device_serial_number="BLANK_IMAGE",
        identification=None,
        host="blank.invalid",
        connection_id="blank",
        device_id=1,
        poll_speed={PollSpeed.FAST: 10, PollSpeed.NORMAL: 15, PollSpeed.SLOW: 30},
    )
    definition = next(group for group in hybrid_sensors if group["register_start"] == 33029)
    entities = {}
    for sensor in SolisSensorGroup(hass, definition, controller).sensors:
        entity = SolisSensor(hass, sensor)
        entity.hass = hass
        entity.schedule_update_ha_state = MagicMock()
        entities[sensor.unique_id.rsplit("_inverter_", 1)[-1]] = entity
    return entities


def _feed(entity: SolisSensor, words: list[int]) -> None:
    for register, word in zip(entity._register, words, strict=True):
        entity.handle_modbus_update({REGISTER: register, VALUE: word, CONTROLLER: "blank.invalid", SLAVE: 1})


def test_lifetime_counter_ignores_a_drop_to_zero(hass):
    total = _energy_sensors(hass)["pv_total_generation"]
    _feed(total, [0, 6609])
    assert total.native_value == 6609

    _feed(total, [0, 0])
    assert total.native_value == 6609

    _feed(total, [0, 6610])
    assert total.native_value == 6610


def test_lifetime_counter_accepts_zero_without_a_previous_value(hass):
    total = _energy_sensors(hass)["pv_total_generation"]
    _feed(total, [0, 0])
    assert total.native_value == 0


def test_periodic_counter_still_resets_to_zero(hass):
    today = _energy_sensors(hass)["pv_today_generation"]
    _feed(today, [123])
    _feed(today, [0])
    assert today.native_value == 0
