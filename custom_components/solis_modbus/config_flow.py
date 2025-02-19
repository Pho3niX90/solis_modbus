import voluptuous as vol
import logging
from homeassistant import config_entries

from . import ModbusController
from .const import DOMAIN
from .data.solis_config import SOLIS_INVERTERS

_LOGGER = logging.getLogger(__name__)

# Extract model names for dropdown selection
SOLIS_MODELS = {inverter["model"]: inverter["model"] for inverter in SOLIS_INVERTERS}

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("host", default=""): str,
        vol.Required("port", default=502): int,
        vol.Optional("poll_interval_fast", default=10): vol.All(int, vol.Range(min=5)),
        vol.Optional("poll_interval_normal", default=15): vol.All(int, vol.Range(min=5)),
        vol.Optional("poll_interval_slow", default=15): vol.All(int, vol.Range(min=5)),
        vol.Required("model", default=list(SOLIS_MODELS.keys())[0]): vol.In(SOLIS_MODELS),  # Model dropdown
        vol.Optional("type", default="hybrid"): vol.In(["hybrid", "hybrid-waveshare", "string", "grid"]),
    }
)

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
        modbus_controller = ModbusController(
            user_input["host"], user_input.get("port", 502),
            fast_poll=user_input.get("poll_interval_fast", 10),
            normal_poll=user_input.get("poll_interval_normal", 15),
            slow_poll=user_input.get("poll_interval_slow", 15)
        )

        try:
            await modbus_controller.connect()
            if user_input["type"] == "string":
                await modbus_controller.async_read_input_register(3262)
            else:
                await modbus_controller.async_read_input_register(33263)
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

        current_options = self.config_entry.options or self.config_entry.data

        options_schema = vol.Schema(
            {
                vol.Required("host", default=current_options.get("host", "")): str,
                vol.Required("port", default=current_options.get("port", 502)): int,
                vol.Required("poll_interval_fast", default=current_options.get("poll_interval_fast", 10)): vol.All(int, vol.Range(min=5)),
                vol.Required("poll_interval_normal", default=current_options.get("poll_interval_normal", 15)): vol.All(int, vol.Range(min=5)),
                vol.Required("poll_interval_slow", default=current_options.get("poll_interval_slow", 15)): vol.All(int, vol.Range(min=5)),
                vol.Required("model", default=current_options.get("model", list(SOLIS_MODELS.keys())[0])): vol.In(SOLIS_MODELS),
                vol.Required("type", default=current_options.get("type", "hybrid")): vol.In(["hybrid", "hybrid-waveshare", "string", "grid"]),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema, errors=errors)
