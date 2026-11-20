"""Config flow for RTU over TCP (RS485 Ethernet gateway), issue #577."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pymodbus import FramerType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solis_modbus.config_flow import ModbusConfigFlow
from custom_components.solis_modbus.const import CONF_CONNECTION_TYPE, CONN_TYPE_RTU_TCP, DOMAIN
from custom_components.solis_modbus.rtu_framer import ResyncFramerRTU

RTU_TCP_INPUT = {
    "host": "1.2.3.4",
    "port": 4196,
    "slave": 1,
    "model": "S6-EH1P",
    "has_v2": True,
    "has_pv": True,
    "has_ac_coupling": False,
    "has_parallel": False,
    "has_battery": True,
    "has_hv_battery": False,
    "has_generator": False,
    "inverter_serial": "sn123",
}

SERIAL_FIELDS = {"serial_port", "baudrate", "bytesize", "parity", "stopbits"}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _fields(result) -> set[str]:
    return {str(key) for key in result["data_schema"].schema}


async def _rtu_tcp_config_form(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input={CONF_CONNECTION_TYPE: CONN_TYPE_RTU_TCP})


async def test_rtu_tcp_shows_host_and_port_without_dongle_or_serial_fields(hass: HomeAssistant):
    result = await _rtu_tcp_config_form(hass)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "config"
    fields = _fields(result)
    assert {"host", "port"} <= fields
    assert "connection" not in fields
    assert not fields & SERIAL_FIELDS


async def test_failed_rtu_tcp_check_shows_the_rtu_form_again_and_keeps_the_type(hass: HomeAssistant):
    with patch.object(ModbusConfigFlow, "_validate_config", return_value=(False, "cannot_connect")) as validate:
        result = await _rtu_tcp_config_form(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=RTU_TCP_INPUT)

    assert validate.call_args.args[0][CONF_CONNECTION_TYPE] == CONN_TYPE_RTU_TCP
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "config"
    assert result["errors"] == {"base": "cannot_connect"}
    fields = _fields(result)
    assert {"host", "port"} <= fields
    assert "connection" not in fields
    assert not fields & SERIAL_FIELDS

    with (
        patch.object(ModbusConfigFlow, "_validate_config", return_value=(True, None)),
        patch("custom_components.solis_modbus.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=RTU_TCP_INPUT)

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CONNECTION_TYPE] == CONN_TYPE_RTU_TCP


async def test_validate_config_probes_an_rtu_tcp_gateway_with_an_rtu_client(hass: HomeAssistant):
    """The probe client is built with RTU framing for the configured host and port (the framer swap itself: next test)."""
    flow = ModbusConfigFlow()
    flow.hass = hass
    built = []

    def connected_client(**kwargs):
        built.append(kwargs)
        client = MagicMock()
        client.connect = AsyncMock()
        client.connected = True
        client.ctx.framer = MagicMock()
        client.read_input_registers = AsyncMock(return_value=MagicMock(isError=MagicMock(return_value=False)))
        return client

    with patch("custom_components.solis_modbus.client_manager.AsyncModbusTcpClient", side_effect=connected_client):
        valid, err = await flow._validate_config({**RTU_TCP_INPUT, CONF_CONNECTION_TYPE: CONN_TYPE_RTU_TCP})

    assert (valid, err) == (True, None)
    assert len(built) == 1
    assert built[0]["framer"] == FramerType.RTU
    assert (built[0]["host"], built[0]["port"]) == ("1.2.3.4", 4196)


async def test_validate_config_gives_the_real_rtu_tcp_client_the_resync_framer(hass: HomeAssistant):
    """Without mocking pymodbus: the probe client carries ResyncFramerRTU (connect fails, nothing listens)."""
    flow = ModbusConfigFlow()
    flow.hass = hass
    from custom_components.solis_modbus import client_manager

    clients = []
    real_create = client_manager.create_tcp_client

    def recording_create(*args, **kwargs):
        client = real_create(*args, **kwargs)
        client.connect = AsyncMock()  # never opens a socket
        clients.append(client)
        return client

    with patch("custom_components.solis_modbus.config_flow.create_tcp_client", side_effect=recording_create):
        valid, err = await flow._validate_config({**RTU_TCP_INPUT, CONF_CONNECTION_TYPE: CONN_TYPE_RTU_TCP})

    assert (valid, err) == (False, "tcp_port_closed")
    assert isinstance(clients[0].ctx.framer, ResyncFramerRTU)


async def test_reconfiguring_an_rtu_tcp_entry_shows_the_rtu_form(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN123",
        version=5,
        data={**RTU_TCP_INPUT, "inverter_serial": "SN123", CONF_CONNECTION_TYPE: CONN_TYPE_RTU_TCP},
        options={},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    fields = _fields(result)
    assert {"host", "port"} <= fields
    assert "connection" not in fields
    assert not fields & SERIAL_FIELDS
