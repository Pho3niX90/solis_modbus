import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, VALUES
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

    config_entry.runtime_data.entities["sensor"] = sensor_entities
    config_entry.runtime_data.entities["sensor_derived"] = sensor_derived_entities

    async_add_entities(sensor_entities, True)
    async_add_entities(sensor_derived_entities, True)

    @callback
    def update(now):
        """Update Modbus data periodically."""

    return True
