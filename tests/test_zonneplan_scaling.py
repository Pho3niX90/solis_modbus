"""The Zonneplan battery scaling follows the option, and new ZP entries pick it from the firmware (#563).

Some S6-EH3P10K-H-ZP firmware sends the battery energy registers 10x/100x too high
(#191 and #563, all on DSP 2 / HMI 2). Firmware DSP 0x15 / HMI 0x22 sends
the standard values, so the scaling made its readings 10x/100x too low.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solis_modbus.const import CONF_ZONNEPLAN_SCALING, CONN_TYPE_TCP, DOMAIN
from custom_components.solis_modbus.data.enums import InverterFeature
from custom_components.solis_modbus.data.solis_config import (
    SOLIS_INVERTERS,
    inverter_options_from_config,
    zonneplan_scaling_for_firmware,
)
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

ZP = "S6-EH3P10K-H-ZP"
POLL = {"poll_interval_fast": 10, "poll_interval_normal": 15, "poll_interval_slow": 30}
ZP_REGISTERS = (33161, 33163, 33164, 33165, 33167, 33168, 33186, 33188)
U32_TOTALS = (33161, 33165, 33186, 33188)
DEFAULT_MULTIPLIERS = {33142: 0.1, 33161: 1, 33163: 0.1, 33164: 0.1, 33165: 1, 33167: 0.1, 33168: 0.1, 33186: 1, 33188: 1}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _config(model, config):
    template = next(inv for inv in SOLIS_INVERTERS if inv.model == model)
    return template.clone_with_options(inverter_options_from_config(config, template), "S2_WL_ST")


def _multiplier(model, config, register):
    controller = MagicMock()
    controller.inverter_config = _config(model, config)
    sensor = SolisBaseSensor(
        hass=MagicMock(),
        controller=controller,
        unique_id="test",
        name="Test",
        registrars=[register, register + 1] if register in U32_TOTALS else [register],
        write_register=None,
        multiplier=DEFAULT_MULTIPLIERS[register],
    )
    return sensor.multiplier


class TestOption:
    def test_absent_key_keeps_the_scaling(self):
        """Entries from before #563 have no key; their readings must not change on upgrade."""
        assert InverterFeature.ZONNEPLAN in _config(ZP, {}).features

    def test_option_off_drops_only_the_zonneplan_feature(self):
        on, off = _config(ZP, {}).features, _config(ZP, {CONF_ZONNEPLAN_SCALING: False}).features
        assert set(on) - set(off) == {InverterFeature.ZONNEPLAN}

    def test_option_is_a_no_op_on_other_models(self):
        assert InverterFeature.ZONNEPLAN not in _config("S6-EH3P", {}).features
        assert _config("S6-EH3P", {}).features == _config("S6-EH3P", {CONF_ZONNEPLAN_SCALING: False}).features

    def test_template_is_not_mutated(self):
        _config(ZP, {CONF_ZONNEPLAN_SCALING: False})
        template = next(inv for inv in SOLIS_INVERTERS if inv.model == ZP)
        assert InverterFeature.ZONNEPLAN in template.features

    @pytest.mark.parametrize("register", ZP_REGISTERS)
    def test_scaling_on(self, register):
        assert _multiplier(ZP, {}, register) == 0.01

    @pytest.mark.parametrize("register", ZP_REGISTERS)
    def test_scaling_off_uses_the_standard_multiplier(self, register):
        assert _multiplier(ZP, {CONF_ZONNEPLAN_SCALING: False}, register) == DEFAULT_MULTIPLIERS[register]

    @pytest.mark.parametrize("config", [{}, {CONF_ZONNEPLAN_SCALING: False}])
    def test_battery_current_is_never_scaled(self, config):
        """33142 reads standard on both firmwares: 2.26 A with the scaling while 22.6 A flowed (#563)."""
        assert _multiplier(ZP, config, 33142) == 0.1

    def test_default_multipliers_match_the_definitions(self):
        """Keep the expectations above in step with hybrid_sensors."""
        from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors

        declared = {int(e["register"][0]): e.get("multiplier", 1) for g in hybrid_sensors for e in g["entities"] if e.get("register")}
        assert {r: declared[r] for r in DEFAULT_MULTIPLIERS} == DEFAULT_MULTIPLIERS

    @pytest.mark.parametrize("register", ZP_REGISTERS)
    def test_s6_eh3p_is_unaffected(self, register):
        assert _multiplier("S6-EH3P", {}, register) == DEFAULT_MULTIPLIERS[register]


class TestFirmware:
    @pytest.mark.parametrize(
        ("dsp", "hmi", "scaling"),
        [
            (2, 2, True),  # #191, and Pluimvee and Dominic-070 on #563
            (0x15, 0x22, False),  # #563 reporter: confirmed standard values
            (0x16, 0x23, False),  # newer than the fix
            (0x15, 0x21, True),  # in between: unconfirmed, keep the scaling
            (0x14, 0x22, True),
            (0x10, 0x10, True),
        ],
    )
    def test_zonneplan_scaling_for_firmware(self, dsp, hmi, scaling):
        assert zonneplan_scaling_for_firmware(dsp, hmi) is scaling


def _ok(registers=None):
    result = MagicMock()
    result.isError.return_value = False
    result.registers = registers or [0]
    return result


def _client(firmware):
    """A Modbus client whose probe succeeds and whose 33001 read returns `firmware`."""

    async def read(address, count, device_id):
        if address == 33001:
            if isinstance(firmware, Exception):
                raise firmware
            return _ok(list(firmware))
        return _ok()

    client = MagicMock()
    client.connect = AsyncMock()
    client.connected = True
    client.read_input_registers = AsyncMock(side_effect=read)
    return client


def _form(model, serial="SNZP1"):
    return {
        "host": "1.2.3.4",
        "port": 502,
        "slave": 1,
        "model": model,
        "connection": "S2_WL_ST",
        "inverter_serial": serial,
    }


async def _create(hass, model, client):
    with (
        patch("custom_components.solis_modbus.config_flow.AsyncModbusTcpClient", return_value=client),
        patch("custom_components.solis_modbus.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={"connection_type": CONN_TYPE_TCP})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=_form(model))
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    return result["data"]


class TestConfigFlow:
    @pytest.mark.asyncio
    async def test_fixed_firmware_turns_the_scaling_off(self, hass: HomeAssistant):
        data = await _create(hass, ZP, _client((0x15, 0x22)))
        assert data[CONF_ZONNEPLAN_SCALING] is False

    @pytest.mark.asyncio
    async def test_old_firmware_keeps_the_scaling(self, hass: HomeAssistant):
        data = await _create(hass, ZP, _client((2, 2)))
        assert data[CONF_ZONNEPLAN_SCALING] is True

    @pytest.mark.asyncio
    async def test_failed_firmware_read_still_creates_the_entry(self, hass: HomeAssistant):
        """The version read is best effort; the option is left out and defaults to on."""
        data = await _create(hass, ZP, _client(TimeoutError("no answer")))
        assert CONF_ZONNEPLAN_SCALING not in data

    @pytest.mark.asyncio
    async def test_error_response_to_the_firmware_read_still_creates_the_entry(self, hass: HomeAssistant):
        client = _client((0x15, 0x22))
        error = MagicMock()
        error.isError.return_value = True
        probe = client.read_input_registers.side_effect

        async def read(address, count, device_id):
            return error if address == 33001 else await probe(address, count, device_id)

        client.read_input_registers.side_effect = read
        data = await _create(hass, ZP, client)
        assert CONF_ZONNEPLAN_SCALING not in data

    @pytest.mark.asyncio
    async def test_other_models_do_not_read_the_firmware(self, hass: HomeAssistant):
        client = _client((0x15, 0x22))
        data = await _create(hass, "S6-EH3P", client)
        assert CONF_ZONNEPLAN_SCALING not in data
        assert all(call.kwargs["address"] != 33001 for call in client.read_input_registers.await_args_list)

    async def _reconfigure(self, hass, entry, model, client):
        with (
            patch("custom_components.solis_modbus.config_flow.AsyncModbusTcpClient", return_value=client),
            patch("custom_components.solis_modbus.async_setup_entry", return_value=True),
        ):
            result = await entry.start_reconfigure_flow(hass)
            result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=_form(model, entry.unique_id))
        assert result["reason"] == "reconfigure_successful"

    def _entry(self, hass, model, options=None):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="SNZP1",
            version=5,
            minor_version=2,
            data={"connection_type": CONN_TYPE_TCP, **_form(model)},
            options=options or {},
        )
        entry.add_to_hass(hass)
        return entry

    @pytest.mark.asyncio
    async def test_reconfigure_to_zp_reads_the_firmware(self, hass: HomeAssistant):
        entry = self._entry(hass, "S6-EH3P")
        await self._reconfigure(hass, entry, ZP, _client((0x15, 0x22)))
        assert entry.data[CONF_ZONNEPLAN_SCALING] is False

    @pytest.mark.asyncio
    async def test_reconfigure_of_an_existing_zp_entry_leaves_the_scaling_alone(self, hass: HomeAssistant):
        """Editing the host must not flip the battery readings of an existing install."""
        entry = self._entry(hass, ZP)
        await self._reconfigure(hass, entry, ZP, _client((0x15, 0x22)))
        assert CONF_ZONNEPLAN_SCALING not in entry.data

    @pytest.mark.asyncio
    async def test_reconfigure_reads_the_model_from_options_too(self, hass: HomeAssistant):
        """A ZP picked in the options flow is the entry's model; editing the host must not re-detect."""
        entry = self._entry(hass, "S6-EH3P", options={"model": ZP})
        await self._reconfigure(hass, entry, ZP, _client((0x15, 0x22)))
        assert CONF_ZONNEPLAN_SCALING not in entry.data

    @pytest.mark.asyncio
    async def test_reconfigure_keeps_a_choice_made_in_the_options(self, hass: HomeAssistant):
        entry = self._entry(hass, "S6-EH3P", options={"model": ZP, CONF_ZONNEPLAN_SCALING: False})
        await self._reconfigure(hass, entry, ZP, _client((2, 2)))
        assert CONF_ZONNEPLAN_SCALING not in entry.data
        assert entry.options[CONF_ZONNEPLAN_SCALING] is False

    @pytest.mark.asyncio
    async def test_reconfigure_replaces_an_earlier_detection(self, hass: HomeAssistant):
        entry = self._entry(hass, "S6-EH3P")
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_ZONNEPLAN_SCALING: True})
        await self._reconfigure(hass, entry, ZP, _client((0x15, 0x22)))
        assert entry.data[CONF_ZONNEPLAN_SCALING] is False

    async def _save_options(self, hass, entry, **changes):
        with patch("custom_components.solis_modbus.async_setup_entry", return_value=True):
            result = await hass.config_entries.options.async_init(entry.entry_id)
            form = {}
            for key in result["data_schema"].schema:
                suggested = (key.description or {}).get("suggested_value", vol.UNDEFINED)
                value = suggested if suggested is not vol.UNDEFINED else key.default()
                if value is not vol.UNDEFINED:
                    form[key.schema] = value
            form.update(changes)
            result = await hass.config_entries.options.async_configure(result["flow_id"], user_input=form)
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        return entry.options

    @pytest.mark.asyncio
    async def test_options_save_on_another_model_does_not_store_the_option(self, hass: HomeAssistant):
        """Otherwise a later reconfigure to the ZP would treat the form default as the user's choice."""
        entry = self._entry(hass, "S6-EH3P", options=POLL)
        options = await self._save_options(hass, entry)
        assert CONF_ZONNEPLAN_SCALING not in options
        await self._reconfigure(hass, entry, ZP, _client((0x15, 0x22)))
        assert entry.data[CONF_ZONNEPLAN_SCALING] is False

    @pytest.mark.asyncio
    async def test_options_save_on_a_zp_keeps_the_detected_value(self, hass: HomeAssistant):
        entry = self._entry(hass, ZP, options=POLL)
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_ZONNEPLAN_SCALING: False})
        options = await self._save_options(hass, entry)
        assert options[CONF_ZONNEPLAN_SCALING] is False

    @pytest.mark.asyncio
    async def test_options_save_on_a_zp_stores_the_users_choice(self, hass: HomeAssistant):
        entry = self._entry(hass, ZP, options=POLL)
        options = await self._save_options(hass, entry, **{CONF_ZONNEPLAN_SCALING: False})
        assert options[CONF_ZONNEPLAN_SCALING] is False

    @pytest.mark.asyncio
    async def test_options_flow_shows_the_option_on_by_default(self, hass: HomeAssistant):
        entry = self._entry(hass, ZP, options=POLL)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        schema = result["data_schema"].schema
        (key,) = [k for k in schema if k == CONF_ZONNEPLAN_SCALING]
        assert key.default() is True
