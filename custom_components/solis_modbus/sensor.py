import asyncio
import logging
from datetime import timedelta
from typing import List

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, VALUES, SENSOR_DERIVED_ENTITIES, \
    SENSOR_ENTITIES
from custom_components.solis_modbus.helpers import get_controller
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor
from custom_components.solis_modbus.sensors.solis_sensor import SolisSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Set up Modbus sensors from a config entry."""
    controller: ModbusController = get_controller(hass, config_entry.data.get("host"))
    sensor_entities: List[SensorEntity] = []
    sensor_derived_entities: List[SensorEntity] = []
    hass.data[DOMAIN][VALUES] = {}

    for sensor_group in controller.sensor_groups:
        for sensor in sensor_group.sensors:
            if sensor.name != "reserve":
                sensor_entities.append(SolisSensor(hass, sensor))

    for sensor in controller.sensor_derived_groups:
        sensor_derived_entities.append(SolisDerivedSensor(hass, sensor))

    hass.data[DOMAIN][SENSOR_ENTITIES] = sensor_entities
    hass.data[DOMAIN][SENSOR_DERIVED_ENTITIES] = sensor_derived_entities

    async_add_entities(sensor_entities, True)
    async_add_entities(sensor_derived_entities, True)

    @callback
    def update(now):
        """Update Modbus data periodically."""
    return True