import asyncio
import logging
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithConfigEntry

from . import ModbusController
from .const import (
    DOMAIN, CONN_TYPE_TCP, CONN_TYPE_SERIAL, CONF_SERIAL_PORT,
    CONF_BAUDRATE, CONF_BYTESIZE, CONF_PARITY, CONF_STOPBITS,
    CONF_CONNECTION_TYPE, CONF_INVERTER_SERIAL, DEFAULT_BAUDRATE, DEFAULT_BYTESIZE,
    DEFAULT_PARITY, DEFAULT_STOPBITS
)
from .data.enums import InverterType
from .data.solis_config import SOLIS_INVERTERS, InverterConfig, CONNECTION_METHOD

_LOGGER = logging.getLogger(__name__)

# Extract model names for dropdown selection
SOLIS_MODELS = {inverter.model: inverter.model for inverter in SOLIS_INVERTERS}

# Connection type options
CONNECTION_TYPES = {
    CONN_TYPE_TCP: "TCP (WiFi Dongle)",
    CONN_TYPE_SERIAL: "Serial (RS485)"
}

# Parity options
PARITY_OPTIONS = {
    "N": "None",
    "E": "Even",
    "O": "Odd"
}

# Base schema with common fields (for both TCP and Serial)
BASE_CONFIG_SCHEMA = {
    vol.Required(CONF_CONNECTION_TYPE, default=CONN_TYPE_TCP): vol.In(CONNECTION_TYPES),
    vol.Required(CONF_INVERTER_SERIAL): str,
    vol.Required("slave", default=1): int,
    vol.Optional("poll_interval_fast", default=10): vol.All(int, vol.Range(min=10)),
    vol.Optional("poll_interval_normal", default=15): vol.All(int, vol.Range(min=15)),
    vol.Optional("poll_interval_slow", default=30): vol.All(int, vol.Range(min=30)),
    vol.Required("model", default=list(SOLIS_MODELS.keys())[0]): vol.In(SOLIS_MODELS),
    # Boolean options (Yes/No toggle)
    vol.Required("has_v2", default=True): vol.Coerce(bool),
    vol.Required("has_pv", default=True): vol.Coerce(bool),
    vol.Required("has_battery", default=True): vol.Coerce(bool),
    vol.Required("has_hv_battery", default=False): vol.Coerce(bool),
    vol.Required("has_generator", default=True): vol.Coerce(bool),
}

# Combined schema that accepts both TCP and Serial fields (all optional except connection_type)
# This allows the form to accept either type of connection
COMBINED_CONFIG_SCHEMA = {
    **BASE_CONFIG_SCHEMA,
    # TCP fields (optional)
    vol.Optional("host", default=""): str,
    vol.Optional("port", default=502): int,
    vol.Optional("connection", default=list(CONNECTION_METHOD.keys())[0]): vol.In(CONNECTION_METHOD),
    # Serial fields (optional)
    vol.Optional(CONF_SERIAL_PORT, default="/dev/ttyUSB0"): str,
    vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.In([9600, 19200, 38400, 57600, 115200]),
    vol.Optional(CONF_BYTESIZE, default=DEFAULT_BYTESIZE): vol.In([7, 8]),
    vol.Optional(CONF_PARITY, default=DEFAULT_PARITY): vol.In(PARITY_OPTIONS),
    vol.Optional(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.In([1, 2]),
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
        vol.Required("poll_interval_fast"): vol.All(int, vol.Range(min=10)),
        vol.Required("poll_interval_normal"): vol.All(int, vol.Range(min=15)),
        vol.Required("poll_interval_slow"): vol.All(int, vol.Range(min=30)),
        vol.Required("model"): vol.In(SOLIS_MODELS),
        vol.Required("connection", default=list(CONNECTION_METHOD.keys())[0]): vol.In(CONNECTION_METHOD),

        # Boolean options (Yes/No toggle)
        vol.Required("has_v2", default=True): vol.Coerce(bool),
        vol.Required("has_pv", default=True): vol.Coerce(bool),
        vol.Required("has_battery", default=True): vol.Coerce(bool),
        vol.Required("has_hv_battery", default=False): vol.Coerce(bool),
        vol.Required("has_generator", default=True): vol.Coerce(bool),
    }
)


def clean_identification(iden: str | None) -> str | None:
    if not iden or not iden.strip():
        return None
    # Replace spaces and disallowed characters with underscores
    iden = iden.strip().lower()
    iden = re.sub(r"[^a-z0-9_]", "_", iden)
    return re.sub(r"_+", "_", iden).strip("_")

class ModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Modbus configuration flow."""

    VERSION = 2
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
            data_schema=vol.Schema({
                vol.Required(CONF_CONNECTION_TYPE, default=CONN_TYPE_TCP): vol.In(CONNECTION_TYPES),
            }),
            errors=errors
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
            schema_dict = {k: v for k, v in TCP_CONFIG_SCHEMA.items()
                           if not (hasattr(k, 'schema') and k.schema == CONF_CONNECTION_TYPE)}
            schema = vol.Schema(schema_dict)
        else:
            # Create Serial schema without connection_type field
            schema_dict = {k: v for k, v in SERIAL_CONFIG_SCHEMA.items()
                           if not (hasattr(k, 'schema') and k.schema == CONF_CONNECTION_TYPE)}
            schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="config",
            data_schema=schema,
            errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration."""
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            if CONF_INVERTER_SERIAL in user_input:
                user_input[CONF_INVERTER_SERIAL] = str(user_input[CONF_INVERTER_SERIAL]).upper()

            data = {**entry.data, **user_input}

            if await self._validate_config(data):
                return self.async_update_reload_and_abort(
                    entry, data=data
                )

            errors["base"] = "Cannot connect to Modbus device. Please check your configuration."

        # Show config form with existing values pre-filled
        conn_type = entry.data.get(CONF_CONNECTION_TYPE, CONN_TYPE_TCP)

        if conn_type == CONN_TYPE_TCP:
            schema_dict = TCP_CONFIG_SCHEMA.copy()
        else:
            schema_dict = SERIAL_CONFIG_SCHEMA.copy()

        # Re-create schema with defaults from entry data
        new_schema = {}
        for key, value in schema_dict.items():
            if key in entry.data:
                new_schema[key] = vol.Required(key, default=entry.data[key]) if isinstance(value,
                                                                                           vol.Required) else vol.Optional(
                    key, default=entry.data[key])
            elif key == CONF_INVERTER_SERIAL and CONF_INVERTER_SERIAL not in entry.data:
                # If serial is missing (the problem we are solving), make it required without default
                new_schema[key] = vol.Required(key)
            else:
                new_schema[key] = value

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(new_schema),
            errors=errors
        )

    async def _create_entry_from_input(self, user_input):
        """Create config entry from validated input."""

        # --- UPPERCASE SANITIZATION ---
        if CONF_INVERTER_SERIAL in user_input:
            user_input[CONF_INVERTER_SERIAL] = str(user_input[CONF_INVERTER_SERIAL]).upper()
        # ------------------------------

        conn_type = user_input.get(CONF_CONNECTION_TYPE, CONN_TYPE_SERIAL)
        slave = user_input["slave"]

        if not await self._validate_config(user_input):
            # Validation failed - show error
            errors = {"base": "Cannot connect to Modbus device. Please check your configuration."}

            if conn_type == CONN_TYPE_TCP:
                schema_dict = {k: v for k, v in TCP_CONFIG_SCHEMA.items()
                               if not (hasattr(k, 'schema') and k.schema == CONF_CONNECTION_TYPE)}
            else:
                schema_dict = {k: v for k, v in SERIAL_CONFIG_SCHEMA.items()
                               if not (hasattr(k, 'schema') and k.schema == CONF_CONNECTION_TYPE)}

            return self.async_show_form(
                step_id="config",
                data_schema=vol.Schema(schema_dict),
                errors=errors
            )

        # Create unique ID based on connection type
        inverter_serial = user_input.get(CONF_INVERTER_SERIAL)

        if inverter_serial:
            # BEST: Use the Serial Number (matches your V2 migration)
            unique_id = str(inverter_serial)
            title = f"Solis: {inverter_serial}"
        elif conn_type == CONN_TYPE_TCP:
            # FALLBACK: Use Host_Slave (Legacy V1 style)
            host = user_input["host"]
            unique_id = f"{host}_{slave}"
            title = f"Solis: Host {host}, Modbus Address {slave}"
        else:
            # FALLBACK: Use Port_Slave (Legacy V1 style)
            port = user_input[CONF_SERIAL_PORT]
            unique_id = f"{port}_{slave}"
            title = f"Solis: {port}, Modbus Address {slave}"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=user_input)

    async def _validate_config(self, user_input):
        """Validate the configuration by trying to connect to the Modbus device."""
        inverter_model = user_input.get("model")
        inverter_config: InverterConfig = next(
            (inv for inv in SOLIS_INVERTERS if inv.model == inverter_model), None
        )

        inverter_config.options = {
            "v2": user_input.get("has_v2", True),
            "pv": user_input.get("has_pv", True),
            "generator": user_input.get("has_generator", True),
            "battery": user_input.get("has_battery", True),
            "hv_battery": user_input.get("has_hv_battery", False),
        }
        inverter_config.connection = user_input.get("connection", "S2_WL_ST")

        conn_type = user_input.get(CONF_CONNECTION_TYPE, CONN_TYPE_SERIAL)

        # Build ModbusController parameters based on connection type
        controller_params = {
            "hass": self.hass,
            "device_id": user_input.get("slave", 1),
            "identification": clean_identification(user_input.get("identification", None)),
            "fast_poll": user_input.get("poll_interval_fast", 10),
            "normal_poll": user_input.get("poll_interval_normal", 15),
            "slow_poll": user_input.get("poll_interval_slow", 15),
            "inverter_config": inverter_config,
            "connection_type": conn_type
        }

        if conn_type == CONN_TYPE_TCP:
            controller_params["host"] = user_input["host"]
            controller_params["port"] = user_input.get("port", 502)
        else:  # Serial
            controller_params["serial_port"] = user_input[CONF_SERIAL_PORT]
            controller_params["baudrate"] = user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
            controller_params["bytesize"] = user_input.get(CONF_BYTESIZE, DEFAULT_BYTESIZE)
            controller_params["parity"] = user_input.get(CONF_PARITY, DEFAULT_PARITY)
            controller_params["stopbits"] = user_input.get(CONF_STOPBITS, DEFAULT_STOPBITS)

        modbus_controller = ModbusController(**controller_params)

        for attempt in range(5):
            try:
                if not await modbus_controller.connect():
                    raise ConnectionError("Failed to connect")
                if inverter_config.type in [InverterType.GRID, InverterType.STRING]:
                    await modbus_controller.async_read_input_register(3041, 1)
                else:
                    await modbus_controller.async_read_input_register(35000, 1)

                return True
            except Exception as e:
                _LOGGER.warning(f"Connection failed attempt {attempt + 1}/5: {str(e)}")
                if attempt < 4:
                    await asyncio.sleep(1)
            finally:
                modbus_controller.close_connection()

        _LOGGER.error(f"Connection failed after 5 attempts: {str(controller_params)}")
        return False

    def _get_user_schema(self, user_input=None):
        """Return the appropriate schema based on connection type selection."""
        if user_input and CONF_CONNECTION_TYPE in user_input:
            conn_type = user_input[CONF_CONNECTION_TYPE]
            if conn_type == CONN_TYPE_TCP:
                return vol.Schema(TCP_CONFIG_SCHEMA)
            else:
                return vol.Schema(SERIAL_CONFIG_SCHEMA)

        return vol.Schema(SERIAL_CONFIG_SCHEMA)

    @staticmethod
    @config_entries.HANDLERS.register(DOMAIN)
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return ModbusOptionsFlowHandler(config_entry)


class ModbusOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle options flow for Modbus."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=self.add_suggested_values_to_schema(
            OPTIONS_SCHEMA, self.config_entry.options
        ), errors=errors)