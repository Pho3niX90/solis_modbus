import asyncio
import logging
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlow
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient

from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CONNECTION_TYPE,
    CONF_EXTREME_INCLUDE_BATTERY,
    CONF_INVERTER_SERIAL,
    CONF_PARITY,
    CONF_POLL_PROFILE,
    CONF_SERIAL_PORT,
    CONF_STOPBITS,
    CONN_TYPE_SERIAL,
    CONN_TYPE_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
    POLL_INTERVAL_FAST_MIN,
    POLL_INTERVAL_FAST_MIN_EXTREME,
    POLL_PROFILE_EXTREME,
    POLL_PROFILE_FULL,
    POLL_PROFILES,
)
from .data.enums import InverterType
from .data.solis_config import CONNECTION_METHOD, SOLIS_INVERTERS, InverterConfig, inverter_options_from_config

_LOGGER = logging.getLogger(__name__)

# Extract model names for dropdown selection
SOLIS_MODELS = {inverter.model: inverter.model for inverter in SOLIS_INVERTERS}

# Connection type options
CONNECTION_TYPES = {CONN_TYPE_TCP: "TCP (WiFi Dongle)", CONN_TYPE_SERIAL: "Serial (RS485)"}

# Parity options
PARITY_OPTIONS = {"N": "None", "E": "Even", "O": "Odd"}

# Base schema with common fields (for both TCP and Serial)
BASE_CONFIG_SCHEMA = {
    vol.Required(CONF_CONNECTION_TYPE, default=CONN_TYPE_TCP): vol.In(CONNECTION_TYPES),
    vol.Required(CONF_INVERTER_SERIAL): str,
    vol.Required("slave", default=1): int,
    # Floor is the extreme-profile minimum; _validate_poll_interval enforces the
    # stricter default floor, which voluptuous can't do since the profile is
    # chosen on this same form.
    vol.Optional("poll_interval_fast", default=POLL_INTERVAL_FAST_MIN): vol.All(int, vol.Range(min=POLL_INTERVAL_FAST_MIN_EXTREME)),
    vol.Optional("poll_interval_normal", default=15): vol.All(int, vol.Range(min=15)),
    vol.Optional("poll_interval_slow", default=30): vol.All(int, vol.Range(min=30)),
    vol.Required(CONF_POLL_PROFILE, default=POLL_PROFILE_FULL): vol.In(POLL_PROFILES),
    vol.Required(CONF_EXTREME_INCLUDE_BATTERY, default=False): bool,
    vol.Required("model", default=list(SOLIS_MODELS.keys())[0]): vol.In(SOLIS_MODELS),
    # Boolean options (Yes/No toggle)
    vol.Required("has_v2", default=True): bool,
    vol.Required("has_pv", default=True): bool,
    vol.Required("has_ac_coupling", default=False): bool,
    vol.Required("has_parallel", default=False): bool,
    vol.Required("has_battery", default=True): bool,
    vol.Required("has_hv_battery", default=False): bool,
    vol.Required("has_generator", default=True): bool,
    vol.Required("has_dual_meter", default=False): bool,
    vol.Required("has_epm", default=True): bool,
}

# TCP-specific fields (includes WiFi dongle type)
TCP_CONFIG_SCHEMA = {
    **BASE_CONFIG_SCHEMA,
    vol.Required("host", default=""): str,
    vol.Required("port", default=502): int,
    vol.Required("connection", default=list(CONNECTION_METHOD.keys())[0]): vol.In(CONNECTION_METHOD),
}

# Serial-specific fields (no WiFi dongle type needed)
SERIAL_CONFIG_SCHEMA = {
    **BASE_CONFIG_SCHEMA,
    vol.Required(CONF_SERIAL_PORT, default="/dev/ttyUSB0"): str,
    vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.In([9600, 19200, 38400, 57600, 115200]),
    vol.Required(CONF_BYTESIZE, default=DEFAULT_BYTESIZE): vol.In([7, 8]),
    vol.Required(CONF_PARITY, default=DEFAULT_PARITY): vol.In(PARITY_OPTIONS),
    vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.In([1, 2]),
}

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required("poll_interval_fast"): vol.All(int, vol.Range(min=POLL_INTERVAL_FAST_MIN_EXTREME)),
        vol.Required("poll_interval_normal"): vol.All(int, vol.Range(min=15)),
        vol.Required("poll_interval_slow"): vol.All(int, vol.Range(min=30)),
        vol.Required(CONF_POLL_PROFILE, default=POLL_PROFILE_FULL): vol.In(POLL_PROFILES),
        vol.Required(CONF_EXTREME_INCLUDE_BATTERY, default=False): bool,
        vol.Required("model"): vol.In(SOLIS_MODELS),
        vol.Required("connection", default=list(CONNECTION_METHOD.keys())[0]): vol.In(CONNECTION_METHOD),
        # Boolean options (Yes/No toggle)
        vol.Required("has_v2", default=True): bool,
        vol.Required("has_pv", default=True): bool,
        vol.Required("has_ac_coupling", default=False): bool,
        vol.Required("has_parallel", default=False): bool,
        vol.Required("has_battery", default=True): bool,
        vol.Required("has_hv_battery", default=False): bool,
        vol.Required("has_generator", default=True): bool,
        vol.Required("has_dual_meter", default=False): bool,
        vol.Required("has_epm", default=True): bool,
    }
)


def _validate_poll_interval(config: dict) -> str | None:
    """Enforce the fast-poll floor that applies to the chosen profile.

    The schemas only declare the extreme floor, because the profile is picked on
    the same form and voluptuous can't vary a field's range by another field's
    value. Returns an error key, or None when the interval is acceptable.
    """
    profile = config.get(CONF_POLL_PROFILE, POLL_PROFILE_FULL)
    floor = POLL_INTERVAL_FAST_MIN_EXTREME if profile == POLL_PROFILE_EXTREME else POLL_INTERVAL_FAST_MIN
    interval = config.get("poll_interval_fast")
    if interval is not None and int(interval) < floor:
        return "poll_interval_below_floor"
    return None


async def _probe_tcp_port(host: str, port: int, timeout: float = 5.0) -> tuple[bool, str | None]:
    """Check that something is actually accepting TCP connections on host:port.

    A plain socket open is far cheaper than a Modbus handshake and separates the two
    failure modes cleanly: a refused/timed-out connect means nothing is listening,
    whereas a successful connect that then fails the register probe means Modbus (or
    the slave id) is the problem. Returns (reachable, reason).
    """
    writer = None
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        return True, None
    except TimeoutError:
        return False, "timeout"
    except OSError as e:
        # ConnectionRefusedError, host unreachable, DNS failure — all OSError subclasses.
        return False, type(e).__name__
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:  # pragma: no cover - best-effort cleanup
                pass


def clean_identification(iden: str | None) -> str | None:
    if not iden or not iden.strip():
        return None
    # Replace spaces and disallowed characters with underscores
    iden = iden.strip().lower()
    iden = re.sub(r"[^a-z0-9_]", "_", iden)
    return re.sub(r"_+", "_", iden).strip("_")


class ModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Modbus configuration flow."""

    VERSION = 5
    MINOR_VERSION = 0

    def __init__(self):
        """Initialize the config flow."""
        self._connection_type = None
        self._config_data = {}

    async def async_step_user(self, user_input=None):
        """Handle initial step - ask for connection type."""
        errors = {}

        if user_input is not None:
            # Save connection type and proceed to config step
            conn_type = user_input.get(CONF_CONNECTION_TYPE)
            if conn_type:
                self._connection_type = conn_type
                return await self.async_step_config()

            errors["base"] = "Please select a connection type."

        # Show connection type selector only
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONNECTION_TYPE, default=CONN_TYPE_TCP): vol.In(CONNECTION_TYPES),
                }
            ),
            errors=errors,
        )

    async def async_step_config(self, user_input=None):
        """Handle second step - show connection-specific configuration."""
        errors = {}

        if user_input is not None:
            # Merge connection type with configuration
            full_config = {CONF_CONNECTION_TYPE: self._connection_type, **user_input}
            return await self._create_entry_from_input(full_config)

        # Remove connection_type from schema since we already have it
        if self._connection_type == CONN_TYPE_TCP:
            # Create TCP schema without connection_type field
            schema_dict = {k: v for k, v in TCP_CONFIG_SCHEMA.items() if not (hasattr(k, "schema") and k.schema == CONF_CONNECTION_TYPE)}
            schema = vol.Schema(schema_dict)
        else:
            # Create Serial schema without connection_type field
            schema_dict = {k: v for k, v in SERIAL_CONFIG_SCHEMA.items() if not (hasattr(k, "schema") and k.schema == CONF_CONNECTION_TYPE)}
            schema = vol.Schema(schema_dict)

        return self.async_show_form(step_id="config", data_schema=schema, errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration."""
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            if CONF_INVERTER_SERIAL in user_input:
                user_input[CONF_INVERTER_SERIAL] = str(user_input[CONF_INVERTER_SERIAL]).strip().upper()

            # Update existing entry data with new input
            data = {**entry.data, **user_input}
            serial = (data.get(CONF_INVERTER_SERIAL) or "").strip()

            # Require serial and model so the form always collects them
            if not serial:
                errors["base"] = "serial_required"
            elif not data.get("model"):
                errors["base"] = "model_required"
            elif any(other.unique_id == serial and other.entry_id != entry.entry_id for other in self.hass.config_entries.async_entries(DOMAIN)):
                # Another entry already manages this inverter
                return self.async_abort(reason="already_configured")
            elif interval_error := _validate_poll_interval(data):
                errors["base"] = interval_error
            else:
                valid, err_key = await self._validate_config(data)
                if valid:
                    # Strip reconfigured keys from options: setup merges
                    # {**data, **options}, so stale option values would silently
                    # shadow the freshly reconfigured data otherwise.
                    new_options = {k: v for k, v in entry.options.items() if k not in user_input}
                    return self.async_update_reload_and_abort(entry, data=data, options=new_options, unique_id=serial)
                errors["base"] = err_key or "cannot_connect"

        # 1. Select the full schema (TCP or Serial) so reconfigure shows all fields
        conn_type = entry.data.get(CONF_CONNECTION_TYPE, CONN_TYPE_TCP)
        if conn_type == CONN_TYPE_TCP:
            source_schema = TCP_CONFIG_SCHEMA
        else:
            source_schema = SERIAL_CONFIG_SCHEMA

        # 2. Pre-fill form with current entry data/options (serial, model, host, etc.)
        current_config = {**entry.data, **entry.options}
        schema_with_suggestions = self.add_suggested_values_to_schema(vol.Schema(source_schema), current_config)

        return self.async_show_form(step_id="reconfigure", data_schema=schema_with_suggestions, errors=errors)

    async def _create_entry_from_input(self, data):
        """Validate and create the entry from input data."""
        errors = {}

        # 1. Sanitize Serial (Convert to Uppercase)
        if CONF_INVERTER_SERIAL in data:
            data[CONF_INVERTER_SERIAL] = str(data[CONF_INVERTER_SERIAL]).upper()

        # 2. Validate Connection
        interval_error = _validate_poll_interval(data)
        valid, err_key = (False, interval_error) if interval_error else await self._validate_config(data)
        if not valid:
            errors["base"] = err_key or "cannot_connect"

            # Determine which schema to show again based on connection type
            if data.get(CONF_CONNECTION_TYPE) == CONN_TYPE_TCP:
                schema_dict = TCP_CONFIG_SCHEMA
            else:
                schema_dict = SERIAL_CONFIG_SCHEMA

            return self.async_show_form(step_id="config", data_schema=vol.Schema(schema_dict), errors=errors)

        # 3. Check for Duplicates
        if CONF_INVERTER_SERIAL in data:
            await self.async_set_unique_id(data[CONF_INVERTER_SERIAL])
            self._abort_if_unique_id_configured()

        # 4. Create the Config Entry
        return self.async_create_entry(title=f"Solis: {data[CONF_INVERTER_SERIAL]}", data=data)

    async def _validate_config(self, user_input):
        """Validate the configuration by probing the Modbus device.

        Uses a throwaway pymodbus client on purpose: building a ModbusController
        here would acquire the SHARED client from ModbusClientManager and the old
        retry loop released it up to 5 times per validation — closing a running
        entry's connection out from under it during reconfigure or when adding a
        second inverter on the same datalogger.

        Returns (True, None) on success, (False, error_key) on failure.
        """
        inverter_model = user_input.get("model")
        inverter_template: InverterConfig | None = next((inv for inv in SOLIS_INVERTERS if inv.model == inverter_model), None)

        if inverter_template is None:
            _LOGGER.warning("Invalid or unknown inverter model: %s", inverter_model)
            return False, "invalid_model"

        user_options = inverter_options_from_config(user_input, inverter_template)
        inverter_config = inverter_template.clone_with_options(user_options, user_input.get("connection", "S2_WL_ST"))

        conn_type = user_input.get(CONF_CONNECTION_TYPE, CONN_TYPE_SERIAL)
        device_id = user_input.get("slave", 1)
        probe_register = 3041 if inverter_config.type in [InverterType.GRID, InverterType.STRING] else 35000

        if conn_type == CONN_TYPE_TCP:
            host, port = user_input["host"], user_input.get("port", 502)
            reachable, reason = await _probe_tcp_port(host, port)
            if not reachable:
                # Distinguish "nothing is listening on 502" from "Modbus itself failed".
                # Recent Solis datalogger firmware closes the local TCP services while
                # cloud upload keeps working, which otherwise surfaces as a generic
                # "check your configuration" and sends people hunting the wrong problem
                # (issue #432).
                _LOGGER.error("TCP pre-probe of %s:%s failed (%s) — nothing is serving Modbus there", host, port, reason)
                return False, "tcp_port_closed"
            client = AsyncModbusTcpClient(host=host, port=port, timeout=5, retries=1)
        else:  # Serial
            client = AsyncModbusSerialClient(
                port=user_input[CONF_SERIAL_PORT],
                baudrate=user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
                bytesize=user_input.get(CONF_BYTESIZE, DEFAULT_BYTESIZE),
                parity=user_input.get(CONF_PARITY, DEFAULT_PARITY),
                stopbits=user_input.get(CONF_STOPBITS, DEFAULT_STOPBITS),
                timeout=5,
                retries=1,
            )

        try:
            for attempt in range(3):
                try:
                    await client.connect()
                    if not client.connected:
                        raise ConnectionError("Failed to connect")
                    # Both client types take the target unit as `device_id` on the
                    # request itself. Assigning `client.slave` did nothing on the
                    # serial client, so the probe always read device 1 regardless
                    # of the configured slave.
                    result = await client.read_input_registers(address=probe_register, count=1, device_id=device_id)
                    if result.isError():
                        raise ConnectionError(f"Probe read of {probe_register} failed: {result}")
                    return True, None
                except Exception as e:
                    _LOGGER.warning("Connection validation attempt %s/3 failed: %s", attempt + 1, e)
                    if attempt < 2:
                        await asyncio.sleep(1)
        finally:
            try:
                client.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup of a throwaway client
                pass

        _LOGGER.error("Connection validation failed after 3 attempts (%s)", conn_type)
        return False, "cannot_connect"

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return ModbusOptionsFlowHandler()


class ModbusOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Modbus."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            merged = {**self.config_entry.options, **user_input}
            interval_error = _validate_poll_interval(merged)
            if interval_error is None:
                return self.async_create_entry(title="", data=merged)
            errors["base"] = interval_error

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, current),
            errors=errors,
        )
