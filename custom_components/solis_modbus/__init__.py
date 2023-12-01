"""The Modbus Integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONTROLLER
from .modbus_controller import ModbusController

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    _LOGGER.warning('init async_setup')
    """Set up the Modbus integration."""
    # Check if there are any configurations in the YAML file
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, data=config[DOMAIN], context={"source": "import"}
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Modbus from a config entry."""
    _LOGGER.warning('init async_setup_entry')

    # Store an instance of the ModbusController in hass.data for access by other components
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            "values": []
        }

    host = entry.data.get("host")
    port = entry.data.get("port", 502)

    hass.data[DOMAIN][CONTROLLER] = ModbusController(host, port)

    _LOGGER.warning(f'config entry host = {host}, post = {port}')
    # Set up the platforms associated with this integration
    for component in PLATFORMS:
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, component))
        _LOGGER.debug(f"async_setup_entry: loading: {component}")
    await asyncio.sleep(20)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a Modbus config entry."""
    _LOGGER.warning('init async_unload_entry')
    # Unload platforms associated with this integration
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, DOMAIN)

    # Clean up resources
    if unload_ok:
        modbus_controller = hass.data[DOMAIN][CONTROLLER]
        modbus_controller.close_connection()

    return unload_ok
