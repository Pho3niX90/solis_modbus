import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.helpers import get_controller_from_entry, is_essential_only
from custom_components.solis_modbus.sensor_data.select_sensors import get_select_sensors
from custom_components.solis_modbus.sensors.solis_select_entity import SolisSelectEntity

_LOGGER = logging.getLogger(__name__)

# Serialize control writes — a single Modbus link can't take concurrent writes.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices,
) -> None:
    controller: ModbusController = get_controller_from_entry(hass, config_entry)

    if is_essential_only(config_entry):
        # Read-only mode (#149): setting registers aren't polled — skip select entities.
        _LOGGER.info("Essential-only mode: select entities suppressed (read-only)")
        return

    sensor_groups = get_select_sensors(controller.inverter_config)

    sensors: list[SolisSelectEntity] = []
    for sensor_group in sensor_groups:
        sensors.append(SolisSelectEntity(hass, controller, sensor_group))
    _LOGGER.info(f"Select entities = {len(sensors)}")
    async_add_devices(sensors, True)
