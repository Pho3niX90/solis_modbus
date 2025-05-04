from typing import re

import voluptuous as vol
import logging
from homeassistant import config_entries

from . import ModbusController
from .const import DOMAIN
from .data.enums import InverterType
from .data.solis_config import SOLIS_INVERTERS, InverterConfig, CONNECTION_METHOD
import re

_LOGGER = logging.getLogger(__name__)

# Extract model names for dropdown selection
SOLIS_MODELS = {inverter.model: inverter.model for inverter in SOLIS_INVERTERS}

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("host", default=""): str,
        vol.Required("port", default=502): int,
        vol.Required("slave", default=1): int,
        vol.Optional("poll_interval_fast", default=10): vol.All(int, vol.Range(min=10)),
        vol.Optional("poll_interval_normal", default=15): vol.All(int, vol.Range(min=15)),
        vol.Optional("poll_interval_slow", default=30): vol.All(int, vol.Range(min=30)),
        vol.Required("model", default=list(SOLIS_MODELS.keys())[0]): vol.In(SOLIS_MODELS),  # Model dropdown
        vol.Optional("identification", default=""): str,
        vol.Required("connection", default=list(CONNECTION_METHOD.keys())[0]): vol.In(CONNECTION_METHOD),

        # Boolean options (Yes/No toggle)
        vol.Required("has_v2", default=True): vol.Coerce(bool),
        vol.Required("has_pv", default=True): vol.Coerce(bool),
        vol.Required("has_battery", default=True): vol.Coerce(bool),
        vol.Required("has_hv_battery", default=False): vol.Coerce(bool),
        vol.Required("has_generator", default=True): vol.Coerce(bool),
    }
)
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

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            if await self._validate_config(user_input):
                await self.async_set_unique_id(user_input["host"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Solis: {user_input['host']}", data=user_input)

            errors["base"] = "Cannot connect to Modbus device. Please check your configuration."

        return self.async_show_form(
            step_id="user", data_schema=self._get_user_schema(), errors=errors
        )

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

        modbus_controller = ModbusController(
            hass=self.hass,
            host=user_input["host"],
            port=user_input.get("port", 502),
            slave=user_input.get("slave", 1),
            identification=clean_identification(user_input.get("identification", None)),
            fast_poll=user_input.get("poll_interval_fast", 10),
            normal_poll=user_input.get("poll_interval_normal", 15),
            slow_poll=user_input.get("poll_interval_slow", 15),
            inverter_config=inverter_config
        )

        try:
            await modbus_controller.connect()
            if inverter_config.type in [InverterType.GRID, InverterType.STRING]:
                await modbus_controller.async_read_input_register(3041)
            else:
                await modbus_controller.async_read_input_register(35000)
            return True
        except ConnectionError as e:
            _LOGGER.error(f"Connection failed: {str(e)}")
            return False
        finally:
            modbus_controller.close_connection()

    def _get_user_schema(self):
        """Return the schema for the user configuration form."""
        return CONFIG_SCHEMA

    @staticmethod
    @config_entries.HANDLERS.register(DOMAIN)
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return ModbusOptionsFlowHandler(config_entry)


class ModbusOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Modbus."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=self.add_suggested_values_to_schema(
            OPTIONS_SCHEMA, self.config_entry.options
        ), errors=errors)
