from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from typing_extensions import List

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.helpers import get_controller
import logging

from custom_components.solis_modbus.sensors.solis_select_entity import SolisSelectEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_devices,
) -> None:
    controller: ModbusController = get_controller(hass, config_entry.data.get("host"))
    # We only want this platform to be set up via discovery.
    _LOGGER.info("Options %s", len(config_entry.options))

    platform_config = config_entry.data or {}
    if len(config_entry.options) > 0:
        platform_config = config_entry.options

    _LOGGER.info(f"Solis platform_config: {platform_config}")

    sensor_groups = [
        {
            "register": 43135,
            "name": "RC Force Charge/Discharge",
            "entities": [
                {"name": "None", "on_value": 0},
                {"name": "Solis RC Force Battery Charge",  "on_value": 1},
                {"name": "Solis RC Force Battery Discharge", "on_value": 2},
            ]
        },
        {
            "register": 43110,
            "name": "Work Mode",
            "entities": [
                {"bit_position": 0, "name": "Self-Use Mode", "work_mode": (0,1,2,6,11)},
                {"bit_position": 1, "name": "Time Of Use Mode", "work_mode": (0,1,2)},
                {"bit_position": 2, "name": "OFF-Grid Mode", "work_mode": (0,1,2)},
                {"bit_position": 6, "name": "Feed In Priority Mode", "work_mode": (0,6,11)},
                {"bit_position": 11, "name": "Solis Peak-shaving Mode", "work_mode": (0,4,6,11)},
            ]
        }
    ]

    sensors: List[SolisSelectEntity] = []
    for sensor_group in sensor_groups:
        sensors.append(SolisSelectEntity(hass, controller, sensor_group))
    _LOGGER.info(f"Select entities = {len(sensors)}")
    async_add_devices(sensors, True)