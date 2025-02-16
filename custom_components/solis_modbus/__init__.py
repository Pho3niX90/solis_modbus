"""The Modbus Integration."""
import asyncio
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, CONTROLLER
from .data_retrieval import DataRetrieval
from .modbus_controller import ModbusController
from .sensors.solis_base_sensor import SolisSensorGroup, SolisBaseSensor
from .sensors.solis_derived_sensor import SolisDerivedSensor

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NUMBER, Platform.SWITCH, Platform.TIME]

SCHEME_HOLDING_REGISTER = vol.Schema(
    {
        vol.Required("address"): vol.Coerce(int),
        vol.Required("value"): vol.Coerce(int),
    }
)


async def async_setup(hass: HomeAssistant):
    """Set up the Modbus integration."""

    def service_write_holding_register(call: ServiceCall):
        address = call.data.get('address')
        value = call.data.get('value')
        host = call.data.get("host")
        controller = hass.data[DOMAIN][CONTROLLER][host]
        # Perform the logic to write to the holding register using register_address and value_to_write
        # ...
        hass.create_task(controller.write_holding_register(address, value))

    hass.services.async_register(
        DOMAIN, "solis_write_holding_register", service_write_holding_register, schema=SCHEME_HOLDING_REGISTER
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Modbus from a config entry."""

    # Initialize storage for controllers
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(CONTROLLER, {})

    host = entry.data.get("host")
    port = entry.data.get("port", 502)
    poll_interval = entry.data.get("poll_interval", 15)
    inverter_type = entry.data.get("type", "hybrid")

    # Ensure valid polling interval
    if poll_interval is None or poll_interval < 5:
        poll_interval = 15

    # Load correct sensor data based on inverter type
    if inverter_type in ["string", "grid"]:
        from .sensor_data.string_sensors import string_sensors as sensors
        from .sensor_data.string_sensors import string_sensors_derived as sensors_derived
    elif inverter_type == "hybrid-waveshare":
        from .sensor_data.hybrid_waveshare_sensors import hybrid_waveshare as sensors
        from .sensor_data.hybrid_waveshare_sensors import hybrid_waveshare_sensors_derived as sensors_derived
    else:
        from .sensor_data.hybrid_sensors import hybrid_sensors as sensors
        from .sensor_data.hybrid_sensors import hybrid_sensors_derived as sensors_derived

    # Create the Modbus controller and assign sensor groups
    controller = ModbusController(
        host=host,
        sensor_groups=[SolisSensorGroup(hass=hass, definition=group, controller_host=host) for group in sensors],
        derived_sensors=list(map(lambda sensor: SolisDerivedSensor(
            hass=hass,
            sensor=sensor
        ),
        list(map(lambda entity: SolisBaseSensor(
            hass=hass,
            name= entity.get("name", None),
            controller_host=host,
            registrars=[int(r) for r in entity.get("resgiter")],
            multiplier=entity.get("multiplier", 1),
            unique_id="{}_{}".format(DOMAIN, entity["unique"])), sensors_derived
        )))),
        port=port,
        poll_interval=poll_interval
    )

    # Store controller in HA data
    hass.data[DOMAIN][CONTROLLER][host] = controller

    _LOGGER.debug(f"Config entry setup for host {host}, port {port}")

    # Forward entry to platforms
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start data retrieval
    DataRetrieval(hass, controller)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a Modbus config entry."""
    _LOGGER.debug('init async_unload_entry')
    # Unload platforms associated with this integration
    unload_ok = all(
        await asyncio.gather(
            *(hass.config_entries.async_forward_entry_unload(entry, platform) for platform in PLATFORMS)
        )
    )

    # Clean up resources
    if unload_ok:
        for controller in hass.data[DOMAIN][CONTROLLER].values():
            controller.close_connection()

    return unload_ok
