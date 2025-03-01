import logging
from typing import List

from homeassistant.config_entries import ConfigEntry

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.helpers import get_controller

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    """Set up the number platform."""
    controller: ModbusController = get_controller(hass, config_entry.data.get("host"))
    # We only want this platform to be set up via discovery.
    _LOGGER.info("Options %s", len(config_entry.options))

    platform_config = config_entry.data or {}
    if len(config_entry.options) > 0:
        platform_config = config_entry.options

    _LOGGER.info(f"Solis platform_config: {platform_config}")

    sensors: List[SolisNumberEntity] = []
    for sensor_group in controller.sensor_groups:
        for sensor in sensor_group.sensors:
            if sensor.name != "reserve" and sensor.editable:
                sensors.append(SolisNumberEntity(hass, sensor))

    _LOGGER.info(f"Select entities = {len(sensors)}")
    async_add_devices(sensors, True)
    return True