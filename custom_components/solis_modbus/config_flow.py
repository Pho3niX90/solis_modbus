import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN
from .modbus_controller import ModbusController


class ModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Modbus configuration flow."""

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            # Validate user input and create a config entry if valid
            if await self._validate_config(user_input):
                await self.async_set_unique_id(user_input["host"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Solis: {user_input['host']}", data=user_input)

            errors["base"] = "Cannot connect to Modbus device. Please check your configuration."

        # Show the configuration form to the user
        return self.async_show_form(
            step_id="user", data_schema=self._get_user_schema(), errors=errors
        )

    async def _validate_config(self, user_input):
        """Validate the configuration by trying to connect to the Modbus device."""
        modbus_controller = ModbusController(user_input["host"], user_input.get("port", 502))
        try:
            await modbus_controller.connect()
            await modbus_controller.read_input_register(33093)
            return True
        except ConnectionError:
            return False
        finally:
            modbus_controller.close_connection()

    def _get_user_schema(self):
        """Return the schema for the user configuration form."""
        return vol.Schema(
            {
                vol.Required("host", default="", description="your solis ip"): str,
                vol.Required("port", default=502, description="port of your modbus, typically 502 or 8899"): int,
            }
        )
