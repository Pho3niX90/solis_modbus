"""The Modbus Integration."""
import asyncio
import logging
from datetime import datetime

import homeassistant.helpers.entity_registry
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    DOMAIN, CONTROLLER, TIME_ENTITIES,
    CONN_TYPE_TCP, CONN_TYPE_SERIAL, CONF_SERIAL_PORT,
    CONF_BAUDRATE, CONF_BYTESIZE, CONF_PARITY, CONF_STOPBITS,
    CONF_CONNECTION_TYPE, CONF_INVERTER_SERIAL, DEFAULT_BAUDRATE, DEFAULT_BYTESIZE,
    DEFAULT_PARITY, DEFAULT_STOPBITS, CONF_SLAVE
)
from .data.enums import InverterFeature
from .data.solis_config import SOLIS_INVERTERS, InverterConfig, InverterType
from .data_retrieval import DataRetrieval
from .helpers import get_controller, set_controller, unique_id_generator
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

async def async_remove_config_entry_device(
        hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True

async def async_setup(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Modbus integration."""

    def service_write_holding_register(call: ServiceCall):
        address = call.data.get('address')
        value = call.data.get('value')
        host = call.data.get("host")
        slave = call.data.get("slave", 1)

        if host:
            controller = get_controller(hass, host, slave)
            hass.create_task(controller.async_write_holding_register(int(address), int(value)))
        else:
            for controller in hass.data[DOMAIN][CONTROLLER].values():
                hass.create_task(controller.async_write_holding_register(int(address), int(value)))

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
    slave = config.get(CONF_SLAVE, 1)
    inverter_serial = config.get(CONF_INVERTER_SERIAL)

    # --- MISSING VALIDATION BLOCK RESTORED ---
    if not inverter_serial:
        hass.components.persistent_notification.async_create(
            "Solis Modbus: Inverter Serial is missing. Please reconfigure the integration.",
            title="Solis Modbus Configuration Issue",
            notification_id="solis_modbus_missing_serial",
        )
        raise ConfigEntryError("Inverter Serial is missing")
    # -----------------------------------------

    # Deferred Migration Check
    if entry.unique_id != inverter_serial:
        _LOGGER.warning("Executing deferred migration to Serial Number IDs")
        await async_migrate_to_serial_ids(hass, entry)

    # Determine connection type (default to TCP for backwards compatibility with old configs)
    connection_type = config.get(CONF_CONNECTION_TYPE, CONN_TYPE_TCP if "host" in config else CONN_TYPE_SERIAL)

    # Get connection-specific parameters
    host = config.get("host")
    port = config.get("port", 502)

    # ... (Rest of your function remains the same) ...
    if connection_type == CONN_TYPE_TCP:
        connection_id = f"{host}:{port}"
    else:  # Serial
        serial_port = config.get(CONF_SERIAL_PORT, "/dev/ttyUSB0")
        connection_id = serial_port

    _LOGGER.debug(config)

    # Initialize storage for controllers
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(CONTROLLER, {})

    _LOGGER.info(f"Loaded Solis Modbus Integration ({connection_type}) with Model: {config.get('model')}")

    # ... (Config extraction ...) ...
    poll_interval_fast = config.get("poll_interval_fast", 5)
    poll_interval_normal = config.get("poll_interval_normal", 15)
    poll_interval_slow = config.get("poll_interval_slow", 30)
    inverter_model = config.get("model")
    identification = config.get("identification", None)

    if inverter_model is None:
        old_type = config.get("type", "hybrid")
        inverter_model = "S6-EH3P" if old_type == "hybrid" else (
            "WAVESHARE" if old_type == "hybrid-waveshare" else "S6-GR1P")

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
        "inverter_serial": inverter_serial,
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
    controller_params = {
        "hass": hass,
        "device_id": slave,
        "identification": identification,
        "fast_poll": poll_interval_fast,
        "normal_poll": poll_interval_normal,
        "slow_poll": poll_interval_slow,
        "inverter_config": inverter_config,
        "connection_type": connection_type,
        "serial_number": inverter_serial
    }

    if connection_type == CONN_TYPE_TCP:
        controller_params["host"] = host
        controller_params["port"] = port
    else:  # Serial
        controller_params["serial_port"] = config.get(CONF_SERIAL_PORT, "/dev/ttyUSB0")
        controller_params["baudrate"] = config.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
        controller_params["bytesize"] = config.get(CONF_BYTESIZE, DEFAULT_BYTESIZE)
        controller_params["parity"] = config.get(CONF_PARITY, DEFAULT_PARITY)
        controller_params["stopbits"] = config.get(CONF_STOPBITS, DEFAULT_STOPBITS)

    controller = ModbusController(**controller_params)

    controller._sensor_groups = []
    for group in sensors:
        feature_requirement = group.get("feature_requirement", [])
        if feature_requirement and not any(feature in inverter_config.features for feature in feature_requirement):
            _LOGGER.warning(
                f"Skipping sensor group '{group.get('name', group.get('register_start', 'Unnamed'))}' due to missing required features: {feature_requirement}"
            )
            continue

        controller._sensor_groups.append(
            SolisSensorGroup(hass=hass, definition=group, controller=controller, identification=identification))

    controller._derived_sensors = [
        SolisBaseSensor(
            hass=hass,
            name=entity.get("name"),
            controller=controller,
            registrars=[int(r) for r in entity.get("register", [])],
            write_register=entity.get("write_register", None),
            state_class=entity.get("state_class", None),
            device_class=entity.get("device_class", None),
            unit_of_measurement=entity.get("unit_of_measurement", None),
            multiplier=entity.get("multiplier", 1),
            editable=entity.get("editable", False),
            hidden=entity.get("hidden", False),
            category=entity.get("category", None),
            unique_id=unique_id_generator(controller, entity.get("unique", "reserve"))
        )
        for entity in sensors_derived
    ]

    set_controller(hass, controller, entry)

    _LOGGER.debug(f"Config entry setup for {connection_type} connection: {connection_id}, slave {slave}")

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


    hass.data[DOMAIN].setdefault("data_retrieval", {})
    hass.data[DOMAIN]["data_retrieval"][entry.entry_id] = DataRetrieval(hass, controller)

    return True

async def async_migrate_to_serial_ids(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate entities and config entry to use Serial Number."""

    config = {**entry.data, **entry.options}
    inverter_serial = config.get(CONF_INVERTER_SERIAL)
    host = config.get("host")
    identification = config.get("identification")

    # Double-check we have what we need
    if not inverter_serial:
        return False

    _LOGGER.info("Starting migration of entities to Serial: %s", inverter_serial)

    # Setup the mock controller for ID generation
    from types import SimpleNamespace
    controller = SimpleNamespace()
    controller.device_serial_number = inverter_serial
    controller.identification = identification
    controller.host = host

    # Get the Entity Registry
    ent_reg = homeassistant.helpers.entity_registry.async_get(hass)

    def safe_migrate_entity(platform, old_uid, new_uid):
        """Safely migrates an entity ID, handling collisions."""
        old_entity_id = ent_reg.async_get_entity_id(platform, DOMAIN, old_uid)
        if not old_entity_id:
            return

        new_entity_id = ent_reg.async_get_entity_id(platform, DOMAIN, new_uid)
        if new_entity_id:
            if new_entity_id == old_entity_id:
                return
            _LOGGER.warning("Migration collision: Removing %s to migrate %s", new_entity_id, old_entity_id)
            ent_reg.async_remove(new_entity_id)

        try:
            _LOGGER.info("Migrating %s -> %s", old_uid, new_uid)
            ent_reg.async_update_entity(old_entity_id, new_unique_id=new_uid)
        except ValueError as e:
            _LOGGER.error("Migration failed for %s: %s", old_entity_id, e)

    # --- SENSOR LOGIC (Same as before) ---
    inverter_model = config.get("model")
    if inverter_model is None:
        old_type = config.get("type", "hybrid")
        inverter_model = "S6-EH3P" if old_type == "hybrid" else (
            "WAVESHARE" if old_type == "hybrid-waveshare" else "S6-GR1P")

    inverter_config: InverterConfig = next(
        (inv for inv in SOLIS_INVERTERS if inv.model == inverter_model), None
    )

    if inverter_config:
        if inverter_config.type in [InverterType.STRING, InverterType.GRID]:
            from .sensor_data.string_sensors import string_sensors, string_sensors_derived
            sensors = string_sensors
            sensors_derived = string_sensors_derived
        else:
            from .sensor_data.hybrid_sensors import hybrid_sensors, hybrid_sensors_derived
            sensors = hybrid_sensors
            sensors_derived = hybrid_sensors_derived

        from .sensor_data.time_sensors import get_time_sensors
        from .helpers import unique_id_generator

        def get_old_id(uid, ctrl):
            if ctrl.identification:
                return f"{DOMAIN}_{ctrl.identification}_{uid}"
            return f"{DOMAIN}_{ctrl.host}_{uid}"

        # A. Standard Sensors
        for group in sensors:
            feature_requirement = group.get("feature_requirement", [])
            if feature_requirement and not any(feature in inverter_config.features for feature in feature_requirement):
                continue
            for entity in group.get("entities", []):
                if entity.get("type") == "reserve": continue
                uid_key = entity.get("unique", "reserve")
                new_uid = unique_id_generator(controller, uid_key)
                old_uid = get_old_id(uid_key, controller)
                if new_uid != old_uid:
                    safe_migrate_entity(Platform.SENSOR, old_uid, new_uid)

        # B. Derived Sensors
        for entity in sensors_derived:
            uid_key = entity.get("unique", "reserve")
            new_uid = unique_id_generator(controller, uid_key)
            if identification:
                old_uid_derived = f"{DOMAIN}_{identification}_{uid_key}"
            else:
                old_uid_derived = f"{DOMAIN}_{uid_key}"
            if new_uid != old_uid_derived:
                safe_migrate_entity(Platform.SENSOR, old_uid_derived, new_uid)

        # C. Time Entities
        for entity in get_time_sensors(inverter_config):
            uid_key = entity.get("unique", "reserve")
            new_uid = unique_id_generator(controller, uid_key)
            old_uid = get_old_id(uid_key, controller)
            if new_uid != old_uid:
                safe_migrate_entity(Platform.TIME, old_uid, new_uid)

    # --- CONFIG ENTRY LOGIC ---
    if entry.unique_id != inverter_serial:
        _LOGGER.info("Migrating Config Entry ID from %s to %s", entry.unique_id, inverter_serial)
        hass.config_entries.async_update_entry(entry, unique_id=inverter_serial)

    return True

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version <= 2:
        # Check if we have the serial right now
        if config_entry.data.get(CONF_INVERTER_SERIAL):
            await async_migrate_to_serial_ids(hass, config_entry)
        else:
            _LOGGER.info("Migration deferred: Waiting for Serial Number reconfigure.")
            return False

        hass.config_entries.async_update_entry(config_entry, version = 3)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
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
        # 1. Stop Data Retrieval
        if "data_retrieval" in hass.data[DOMAIN]:
            data_retrieval = hass.data[DOMAIN]["data_retrieval"].pop(entry.entry_id, None)
            if data_retrieval:
                await data_retrieval.async_stop()

        # 2. Close and REMOVE the specific controller for this entry
        if CONTROLLER in hass.data[DOMAIN]:
            controller = hass.data[DOMAIN][CONTROLLER].pop(entry.entry_id, None)
            if controller:
                _LOGGER.debug("Closing Modbus connection for entry %s", entry.entry_id)
                controller.close_connection()

    return unload_ok