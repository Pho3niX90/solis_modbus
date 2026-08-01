import logging

from homeassistant.config_entries import ConfigEntry

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.helpers import get_controller_from_entry, is_essential_only
from custom_components.solis_modbus.sensors.solis_number_sensor import SolisNumberEntity

_LOGGER = logging.getLogger(__name__)

# Serialize control writes — a single Modbus link can't take concurrent writes.
PARALLEL_UPDATES = 1


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    """Set up the number platform."""
    controller: ModbusController = get_controller_from_entry(hass, config_entry)

    if is_essential_only(config_entry):
        # Read-only mode (#149): setting registers aren't polled — skip number entities.
        _LOGGER.info("Essential-only mode: number entities suppressed (read-only)")
        return

    sensors: list[SolisNumberEntity] = []
    for sensor_group in controller.sensor_groups:
        for sensor in sensor_group.sensors:
            if sensor.name != "reserve" and sensor.editable:
                sensors.append(SolisNumberEntity(hass, sensor))
    config_entry.runtime_data.entities["number"] = sensors
    _LOGGER.info(f"Number entities = {len(sensors)}")
    async_add_devices(sensors, True)
    return True
