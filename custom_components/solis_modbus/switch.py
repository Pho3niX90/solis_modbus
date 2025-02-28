import logging
from typing import List

from homeassistant.config_entries import ConfigEntry

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, CONTROLLER,  ENTITIES, SWITCH_ENTITIES
from custom_components.solis_modbus.data.enums import InverterType
from custom_components.solis_modbus.data.solis_config import InverterConfig
from custom_components.solis_modbus.sensors.solis_binary_sensor import SolisBinaryEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    modbus_controller: ModbusController = hass.data[DOMAIN][CONTROLLER][config_entry.data.get("host")]

    switch_sensors = []

    if modbus_controller.inverter_config.type == InverterType.HYBRID:
        switch_sensors.extend([
            {
                "register": 5,
                "entities": [
                    {"type": "SBS", "bit_position": 0, "name": "Solis Modbus Enabled"},
                ]
            },
            {
                "register": 43110,
                "entities": [
                    {"type": "SBS", "bit_position": 0, "name": "Solis Self-Use Mode", "work_mode": (0,6,11)},
                    {"type": "SBS", "bit_position": 1, "name": "Solis Time Of Use Mode"},
                    {"type": "SBS", "bit_position": 2, "name": "Solis OFF-Grid Mode"},
                    {"type": "SBS", "bit_position": 3, "name": "Solis Battery Wakeup Switch"},
                    {"type": "SBS", "bit_position": 4, "name": "Solis Reserve Battery Mode", "work_mode": (4,11)},
                    {"type": "SBS", "bit_position": 5, "name": "Solis Allow Grid To Charge The Battery"},
                    {"type": "SBS", "bit_position": 6, "name": "Solis Feed In Priority Mode", "work_mode": (0,6,11)},
                    {"type": "SBS", "bit_position": 7, "name": "Solis Batt OVC"},
                    {"type": "SBS", "bit_position": 8, "name": "Solis Battery Forcecharge Peakshaving"},
                    {"type": "SBS", "bit_position": 9, "name": "Solis Battery current correction"},
                    {"type": "SBS", "bit_position": 10, "name": "Solis Battery healing mode"},
                    {"type": "SBS", "bit_position": 11, "name": "Solis Peak-shaving Mode", "work_mode": (0,4,6,11)},
                ]
            },{
                "register": 43365,
                "entities": [
                    {"type": "SBS", "bit_position": 0, "name": "Solis Generator connection position"},
                    {"type": "SBS", "bit_position": 1, "name": "Solis With Generator"},
                    {"type": "SBS", "bit_position": 2, "name": "Solis Generator enable signal"},
                    {"type": "SBS", "bit_position": 3, "name": "Solis AC Coupling Position (off = GEN port, on = Backup port)"},
                    {"type": "SBS", "bit_position": 4, "name": "Solis Generator access location"},
                ]
            },{
                "register": 43815,
                "entities": [
                    {"type": "SBS", "bit_position": 0, "name": "Solis Generator charging period 1 switch"},
                    {"type": "SBS", "bit_position": 1, "name": "Solis Generator charging period 2 switch"},
                    {"type": "SBS", "bit_position": 2, "name": "Solis Generator charging period 3 switch"},
                    {"type": "SBS", "bit_position": 3, "name": "Solis Generator charging period 4 switch"},
                    {"type": "SBS", "bit_position": 4, "name": "Solis Generator charging period 5 switch"},
                    {"type": "SBS", "bit_position": 5, "name": "Solis Generator charging period 6 switch"},
                ]
            },{
                "register": 43340,
                "entities": [
                    {"type": "SBS", "bit_position": 0, "name": "Solis Generator Input Mode (off = Manual, on = Auto)"},
                    {"type": "SBS", "bit_position": 1, "name": "Solis Generator Charge Enable"},
                ]
            },{
                "register": 43483,
                "entities": [
                    {"type": "SBS", "bit_position": 0, "name": "Solis Dual Backup Enable"},
                    {"type": "SBS", "bit_position": 1, "name": "Solis AC Coupling Enable"},
                    {"type": "SBS", "bit_position": 2, "name": "Solis Smart load port grid-connected forced output"},
                    {"type": "SBS", "bit_position": 3, "name": "Solis Allow export switch under self-generation and self-use"},
                    {"type": "SBS", "bit_position": 4, "name": "Solis Backup2Load manual/automatic switch (off = Manual, on = Automatic"},
                    {"type": "SBS", "bit_position": 5, "name": "Solis Backup2Load manual enable"},
                    {"type": "SBS", "bit_position": 6, "name": "Solis Smart load port stops output when off-grid"},
                    {"type": "SBS", "bit_position": 7, "name": "Solis Grid Peak-shaving power enable"},
                ]
            }, {
                "register": 43249,
                "entities": [
                    {"type": "SBS", "bit_position": 0, "name": "MPPT Parallel Function"},
                    {"type": "SBS", "bit_position": 1, "name": "IgFollow"},
                    {"type": "SBS", "bit_position": 2, "name": "Relay Protection"},
                    {"type": "SBS", "bit_position": 3, "name": "I-Leak Protection"},
                    {"type": "SBS", "bit_position": 4, "name": "PV ISO Protection"},
                    {"type": "SBS", "bit_position": 5, "name": "Grid-Interference Protection"},
                    {"type": "SBS", "bit_position": 6, "name": "The DC component of the grid current protection switch"},
                    {"type": "SBS", "bit_position": 7, "name": "Const Voltage Mode Enable Const Voltage"},
                ]
            }, {
                "register": 43135,
                "entities": [
                    {"type": "SBS", "name": "Solis RC Force Battery Discharge", "on_value": 1},
                    {"type": "SBS", "name": "Solis RC Force Battery Charge",  "on_value": 2}
                ]
            },{
                "register": 43363,
                "entities": [
                    {"type": "SBS", "name": "Solis Force Start Generator", "on_value": 1},
                ]
            }, {
                "register": 43707,
                "entities": [
                    {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 1", "bit_position": 0},
                    {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 2", "bit_position": 1},
                    {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 3", "bit_position": 2},
                    {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 4", "bit_position": 3},
                    {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 5", "bit_position": 4},
                    {"type": "SBS", "name": "Solis Grid Time of Use Charging Period 6", "bit_position": 5},
                    {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 1", "bit_position": 6},
                    {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 2", "bit_position": 7},
                    {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 3", "bit_position": 8},
                    {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 4", "bit_position": 9},
                    {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 5", "bit_position": 10},
                    {"type": "SBS", "name": "Solis Grid Time of Use Discharge Period 6", "bit_position": 11},
                ]
            }
        ])

    switchEntities: List[SolisBinaryEntity] = []

    for main_entity in switch_sensors:
        for child_entity in main_entity[ENTITIES]:
           child_entity['register'] = main_entity['register']
           switchEntities.append(SolisBinaryEntity(hass, modbus_controller, child_entity))

    hass.data[DOMAIN][SWITCH_ENTITIES] = switchEntities
    async_add_devices(switchEntities, True)

    return True


