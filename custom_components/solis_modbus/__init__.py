"""The Modbus Integration."""
import asyncio
import logging
from datetime import datetime

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryError

from .const import DOMAIN, CONTROLLER, TIME_ENTITIES
from .data.enums import InverterFeature
from .data.solis_config import SOLIS_INVERTERS, InverterConfig, InverterType
from .data_retrieval import DataRetrieval
from .modbus_controller import ModbusController
from .sensors.solis_base_sensor import SolisSensorGroup, SolisBaseSensor
from .sensors.solis_derived_sensor import SolisDerivedSensor

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NUMBER, Platform.SWITCH, Platform.TIME, Platform.SELECT]

SCHEME_HOLDING_REGISTER = vol.Schema(
    {
        vol.Required("address"): vol.Coerce(int),
        vol.Required("value"): vol.Coerce(int),
        vol.Optional("host"): vol.Coerce(str),
    }
)
SCHEME_TIME_SET = vol.Schema(
    {
        vol.Required("entity_id"): vol.Coerce(str),
        vol.Required("time"): vol.Coerce(str)
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
            hass.create_task(controller.async_write_holding_register(int(address), int(value)))
        else:
            for controller in hass.data[DOMAIN][CONTROLLER].values():
                hass.create_task(controller.async_write_holding_register(int(address), int(value)))

    # @Ian-Johnston
    async def service_set_time(call: ServiceCall) -> None:
        """Service to update a Solis time entity."""
        entity_id = call.data.get("entity_id")
        time_str = call.data.get("time")

        if not entity_id or not time_str:
            _LOGGER.error("Missing entity_id or time parameter in service call")
            return

        try:
            # Try to parse time in HH:MM:SS format first, then fallback to HH:MM
            try:
                new_time = datetime.strptime(time_str, "%H:%M:%S").time()
            except ValueError:
                new_time = datetime.strptime(time_str, "%H:%M").time()
        except Exception as e:
            _LOGGER.error("❌ Failed to parse time string '%s': %s", time_str, e)
            return

        # Look through the registered time entities for one that matches the given entity_id
        for entity in call.hass.data.get(DOMAIN, {}).get(TIME_ENTITIES, []):
            if entity.entity_id == entity_id:
                await entity.async_set_value(new_time)
                _LOGGER.debug("Set time for %s to %s", entity_id, new_time)
                return

        _LOGGER.error("⚠️ Entity with id %s not found in solis_modbus TIME_ENTITIES", entity_id)

    hass.services.async_register(
        DOMAIN, "solis_write_holding_register", service_write_holding_register, schema=SCHEME_HOLDING_REGISTER
    )
    hass.services.async_register(
        DOMAIN, "solis_write_time", service_set_time, schema=SCHEME_TIME_SET
    )

    return True


async def async_update_options(entry):
    """Handle options updates."""
    hass = entry.hass
    await hass.config_entries.async_update_entry(entry, options=entry.options)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Modbus from a config entry."""

    # Merge data and options (options take priority)
    config = {**entry.data, **entry.options}
    _LOGGER.debug(config)

    # Initialize storage for controllers
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(CONTROLLER, {})
    hass.data[DOMAIN][entry.entry_id] = entry
    _LOGGER.info(f"Loaded Solis Modbus Integration with Model: {config.get('model')}")

    host = config.get("host")
    port = config.get("port", 502)
    slave = config.get("slave", 1)

    poll_interval_fast = config.get("poll_interval_fast", 5)
    poll_interval_normal = config.get("poll_interval_normal", 15)
    poll_interval_slow = config.get("poll_interval_slow", 30)
    inverter_model = config.get("model")
    identification = config.get("identification", None)

    if inverter_model is None:
        old_type = config.get("type", "hybrid")
        inverter_model = "S6-EH3P" if old_type == "hybrid" else ("WAVESHARE" if old_type == "hybrid-waveshare" else "S6-GR1P")

    inverter_config: InverterConfig = next(
        (inv for inv in SOLIS_INVERTERS if inv.model == inverter_model), None
    )

    # defaulting
    if inverter_config is None:
        hass.components.persistent_notification.async_create(
            f"Your Solis Modbus configuration is invalid. Please reconfigure the integration.",
            title="Solis Modbus Configuration Issue",
            notification_id="solis_modbus_invalid_config",
        )
        raise ConfigEntryError

    inverter_config.options = {
        "v2": config.get("has_v2", True),
        "pv": config.get("has_pv",
                         inverter_config.type in [InverterType.HYBRID, InverterType.GRID, InverterType.WAVESHARE]),
        "generator": config.get("has_generator", True),
        "battery": config.get("has_battery", True),
        "hv_battery": config.get("has_hv_battery", False),
    }
    inverter_config.connection = config.get("connection", "S2_WL_ST")

    # Load correct sensor data based on inverter type
    if inverter_config.type in [InverterType.STRING, InverterType.GRID]:
        from .sensor_data.string_sensors import string_sensors as sensors
        from .sensor_data.string_sensors import string_sensors_derived as sensors_derived
    else:
        from .sensor_data.hybrid_sensors import hybrid_sensors as sensors
        from .sensor_data.hybrid_sensors import hybrid_sensors_derived as sensors_derived

    # Create the Modbus controller and assign sensor groups
    controller = ModbusController(
        hass=hass,
        host=host,
        port=port,
        slave=slave,
        identification=identification,
        fast_poll=poll_interval_fast,
        normal_poll=poll_interval_normal,
        slow_poll=poll_interval_slow,
        inverter_config=inverter_config
    )

    controller._sensor_groups = []
    for group in sensors:
        feature_requirement = group.get("feature_requirement", [])

        # If there are feature requirements, check if they exist in inverter_config.features
        if feature_requirement and not any(feature in inverter_config.features for feature in feature_requirement):
            _LOGGER.warning(
                f"Skipping sensor group '{group.get('name', group.get('register_start', 'Unnamed'))}' due to missing required features: {feature_requirement}"
            )
            continue  # Skip this group

        # If it passes the check, add to sensor groups
        controller._sensor_groups.append(SolisSensorGroup(hass=hass, definition=group, controller=controller, identification=identification))

    controller._derived_sensors = [
        SolisBaseSensor(
            hass=hass,
            name=entity.get("name"),
            controller=controller,
            registrars=[int(r) for r in entity.get("register", [])],
            state_class=entity.get("state_class", None),
            device_class=entity.get("device_class", None),
            unit_of_measurement=entity.get("unit_of_measurement", None),
            editable=entity.get("editable", False),
            hidden=entity.get("hidden", False),
            multiplier=entity.get("multiplier", 1),
            category=entity.get("category", 1),
            identification=entity.get("identification", None),
            unique_id=f"{DOMAIN}_{entity['unique']}" if not identification else f"{DOMAIN}_{identification}_{entity['unique']}"
        )
        for entity in sensors_derived
    ]

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
