import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, SENSOR_DERIVED_ENTITIES, SENSOR_ENTITIES, VALUES
from custom_components.solis_modbus.helpers import get_controller_from_entry
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor
from custom_components.solis_modbus.sensors.solis_sensor import SolisSensor

_LOGGER = logging.getLogger(__name__)

# Read-only platform — no write serialization needed.
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Set up Modbus sensors from a config entry."""
    controller: ModbusController = get_controller_from_entry(hass, config_entry)
    sensor_entities: list[SolisSensor] = []
    sensor_derived_entities: list[SensorEntity] = []
    hass.data.setdefault(DOMAIN, {})
    # Never wipe the shared register cache on setup/reload — keys are namespaced
    # per link+slave, so other controllers' cached values must survive.
    hass.data[DOMAIN].setdefault(VALUES, {})

    for sensor_group in controller.sensor_groups:
        for sensor in sensor_group.sensors:
            if sensor.name != "reserve":
                sensor_entities.append(SolisSensor(hass, sensor))

    for sensor in controller.derived_sensors:
        sensor_derived_entities.append(SolisDerivedSensor(hass, sensor))

    # Key entity buckets by entry_id so a second inverter doesn't clobber the first.
    hass.data[DOMAIN].setdefault(SENSOR_ENTITIES, {})[config_entry.entry_id] = sensor_entities
    hass.data[DOMAIN].setdefault(SENSOR_DERIVED_ENTITIES, {})[config_entry.entry_id] = sensor_derived_entities

    async_add_entities(sensor_entities, True)
    async_add_entities(sensor_derived_entities, True)

    @callback
    def update(now):
        """Update Modbus data periodically."""

    return True
