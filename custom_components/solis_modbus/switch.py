import logging
from typing import List

from homeassistant.config_entries import ConfigEntry

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.helpers import get_controller_from_entry
from custom_components.solis_modbus.const import DOMAIN, ENTITIES, SWITCH_ENTITIES
from custom_components.solis_modbus.sensors.solis_binary_sensor import SolisBinaryEntity
from custom_components.solis_modbus.sensor_data.switch_sensors import get_switch_sensors

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    modbus_controller: ModbusController = get_controller_from_entry(hass, config_entry)


    switch_sensors = get_switch_sensors(modbus_controller.inverter_config)

    switchEntities: List[SolisBinaryEntity] = []

    for main_entity in switch_sensors:
        for child_entity in main_entity[ENTITIES]:
           child_entity['register'] = main_entity.get('register',main_entity.get('read_register'))
           child_entity['write_register'] = main_entity.get('write_register', None)
           switchEntities.append(SolisBinaryEntity(hass, modbus_controller, child_entity))

    hass.data[DOMAIN][SWITCH_ENTITIES] = switchEntities
    async_add_devices(switchEntities, True)

    return True


