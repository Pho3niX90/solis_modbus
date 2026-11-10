"""Config-entry diagnostics: redaction, cache scoping and structure."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.solis_modbus.const import DOMAIN, VALUES
from custom_components.solis_modbus.data.enums import InverterType, PollSpeed
from custom_components.solis_modbus.diagnostics import async_get_config_entry_diagnostics
from custom_components.solis_modbus.runtime import SolisRuntimeData


def make_controller():
    controller = MagicMock()
    controller.connection_id = "1.2.3.4:502"
    controller.device_id = 1
    controller.connection_type = "tcp"
    controller.host = "1.2.3.4"
    controller.connected.return_value = True
    controller.enabled = True
    controller.connect_failures = 0
    controller.last_modbus_success = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
    controller.poll_speed = {PollSpeed.FAST: 10, PollSpeed.NORMAL: 15, PollSpeed.SLOW: 30}
    controller.sw_version = "N/A"
    controller.inverter_config.model = "S6-EH1P"
    controller.inverter_config.type = InverterType.HYBRID
    controller.inverter_config.phases = 1
    controller.inverter_config.connection = "S2_WL_ST"
    controller.inverter_config.wattage_chosen = 8000
    controller.inverter_config.features = []
    group = MagicMock()
    group.start_register = 33000
    group.registrar_count = 20
    group.poll_speed = PollSpeed.ONCE
    group.sensors = []
    controller.sensor_groups = [group]
    return controller


def make_entry(controller):
    entry = MagicMock()
    entry.data = {"host": "1.2.3.4", "inverter_serial": "SN1234567890", "model": "S6-EH1P"}
    entry.options = {}
    entry.version = 4
    entry.minor_version = 0
    entry.unique_id = "SN1234567890"
    entry.runtime_data = SolisRuntimeData(controller=controller)
    entry.runtime_data.entities["sensor"] = [MagicMock(), MagicMock()]
    return entry


@pytest.fixture
def hass_with_cache():
    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            VALUES: {
                "1.2.3.4:502|1|33000": 12549,  # ours
                "1.2.3.4:502|1|33005": 21323,  # ours but a serial register -> excluded
                "1.2.3.4:502|2|33000": 999,  # other slave -> excluded
                "5.6.7.8:502|1|33000": 888,  # other link -> excluded
            }
        }
    }
    return hass


async def test_diagnostics_structure_and_redaction(hass_with_cache):
    controller = make_controller()
    entry = make_entry(controller)

    diag = await async_get_config_entry_diagnostics(hass_with_cache, entry)

    # Redaction: host and serial never appear verbatim
    assert diag["entry"]["data"]["host"] == "**REDACTED**"
    assert diag["entry"]["data"]["inverter_serial"] == "**REDACTED**"
    assert diag["entry"]["unique_id"] == "***7890"
    assert diag["controller"]["host"] == "***.3.4"

    # Cache scoped to this link+slave, serial registers dropped
    assert diag["register_cache"] == {"33000": 12549}

    # Structure
    assert diag["controller"]["poll_speed"] == {"FAST": 10, "NORMAL": 15, "SLOW": 30}
    assert diag["inverter_config"]["model"] == "S6-EH1P"
    assert diag["sensor_groups"][0]["start_register"] == 33000
    assert diag["entity_counts"] == {"sensor": 2}


async def test_diagnostics_without_runtime_data():
    entry = MagicMock(spec=["runtime_data"])
    entry.runtime_data = None
    diag = await async_get_config_entry_diagnostics(MagicMock(), entry)
    assert "error" in diag


async def test_diagnostics_show_serial_line_counters_for_a_resync_framer(hass_with_cache):
    from pymodbus.pdu import DecodePDU
    from pymodbus.pdu.register_message import ReadInputRegistersRequest

    from custom_components.solis_modbus.rtu_framer import EarlyEnd, ResyncFramerRTU

    now_s = [10.0]
    timers = []

    def call_later(delay_s, callback):
        timers.append(callback)
        return MagicMock()

    framer = ResyncFramerRTU(
        DecodePDU(False),
        clock=lambda: now_s[0],
        early_end=EarlyEnd(9600, 0.31, lambda: lambda: None),
        call_later=call_later,
    )
    request = ReadInputRegistersRequest(dev_id=1, address=33000, count=1)
    framer.buildFrame(request)
    timers.pop()()  # no first byte: a no-answer attempt
    framer.buildFrame(request)
    now_s[0] += 0.125
    framer.handleFrame(bytes.fromhex("01 90 0b 54"), 1, 0)
    timers.pop()()  # junk, then silence: a bad-answer attempt
    framer.buildFrame(request)
    framer.handleFrame(bytes.fromhex("ff 01 04 02 aa 55 07 af"), 1, 0)  # a valid answer behind one junk byte
    controller = make_controller()
    controller.client.ctx.framer = framer

    diag = await async_get_config_entry_diagnostics(hass_with_cache, make_entry(controller))

    section = diag["controller"]
    assert section["serial_junk_bytes_skipped"] == 5
    assert section["serial_frames_rescued"] == 1
    assert section["serial_attempts_no_answer"] == 1
    assert section["serial_attempts_bad_answer"] == 1
    assert section["serial_first_byte_latency_max_ms"] == pytest.approx(125.0 - 8 * 11 / 9600 * 1000.0)


async def test_diagnostics_have_no_serial_line_counters_for_other_clients(hass_with_cache):
    diag = await async_get_config_entry_diagnostics(hass_with_cache, make_entry(make_controller()))

    assert [key for key in diag["controller"] if key.startswith("serial_")] == []
