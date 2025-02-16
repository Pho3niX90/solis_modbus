"""The Modbus Integration."""
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, CONTROLLER
from .modbus_controller import ModbusController

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NUMBER, Platform.SWITCH, Platform.TIME]

SCHEME_HOLDING_REGISTER = vol.Schema(
    {
        vol.Required("address"): vol.Coerce(int),
        vol.Required("value"): vol.Coerce(int),
    }
)


async def async_setup(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Modbus integration."""

    def service_write_holding_register(call: ServiceCall):
        address = call.data.get('address')
        value = call.data.get('value')
        host = call.data.get("host")

        if host:
            controller = hass.data[DOMAIN][CONTROLLER][host]
            hass.create_task(controller.write_holding_register(address, value))
        else:
            for controller in hass.data[DOMAIN][CONTROLLER]:
                hass.create_task(controller.write_holding_register(address, value))

    hass.services.async_register(
        DOMAIN, "solis_write_holding_register", service_write_holding_register, schema=SCHEME_HOLDING_REGISTER
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Modbus from a config entry."""

    # Store an instance of the ModbusController in hass.data for access by other components
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            "values": [],
            CONTROLLER: {}
        }

    host = entry.data.get("host")
    port = entry.data.get("port", 502)
    poll_interval = entry.data.get("poll_interval")

    if poll_interval is None or poll_interval < 5:
        poll_interval = 15

    controller = ModbusController(host, port, poll_interval)
    hass.data[DOMAIN][CONTROLLER][host] = controller

    _LOGGER.debug(f'config entry host = {host}, post = {port}')

    # Set up the platforms associated with this integration
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a Modbus config entry."""
    _LOGGER.debug('init async_unload_entry')
    # Unload platforms associated with this integration
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, DOMAIN)

    # Clean up resources
    if unload_ok:
        for controller in hass.data[DOMAIN][CONTROLLER].values():
            controller.close_connection()

    return unload_ok
