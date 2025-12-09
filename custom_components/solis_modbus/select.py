import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from typing_extensions import List

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.helpers import get_controller_from_entry
from custom_components.solis_modbus.sensor_data.select_sensors import get_select_sensors
from custom_components.solis_modbus.sensors.solis_select_entity import SolisSelectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_devices,
) -> None:
    controller: ModbusController = get_controller_from_entry(hass, config_entry)
    # We only want this platform to be set up via discovery.
    _LOGGER.info("Options %s", len(config_entry.options))

    platform_config = config_entry.data or {}
    inverter_type = controller.inverter_config.type

    if len(config_entry.options) > 0:
        platform_config = config_entry.options

    _LOGGER.info(f"Solis platform_config: {platform_config}")

    sensor_groups = get_select_sensors(controller.inverter_config)

    sensors: List[SolisSelectEntity] = []
    for sensor_group in sensor_groups:
        sensors.append(SolisSelectEntity(hass, controller, sensor_group))
    _LOGGER.info(f"Select entities = {len(sensors)}")
    async_add_devices(sensors, True)
