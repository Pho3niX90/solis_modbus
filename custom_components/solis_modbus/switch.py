import logging
from typing import List

from homeassistant.config_entries import ConfigEntry

from custom_components.solis_modbus import ModbusController, get_controller
from custom_components.solis_modbus.const import DOMAIN, ENTITIES, SWITCH_ENTITIES
from custom_components.solis_modbus.data.enums import InverterType
from custom_components.solis_modbus.sensors.solis_binary_sensor import SolisBinaryEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    modbus_controller: ModbusController = get_controller(hass, config_entry.data.get("host"), config_entry.data.get("slave", 1))

    switch_sensors = [
        {
            "register": 90005,
            "entities": [
                {"bit_position": 0, "name": "Solis Modbus Enabled"},
            ]
        }]

    if modbus_controller.inverter_config.type == InverterType.HYBRID:
        switch_sensors.extend([
            {
            "register": 43007,
            "entities": [
                {"name": "Power State", "on_value": 190, "off_value": 222},
            ]
            },
            {
                "register": 43110,
                "entities": [
                    # Adheres to RS485_MODBUS ESINV-33000ID Hybrid Inverter V3.2 / Appendix 8
                    { "bit_position": 0, "name": "Self-Use Mode", "conflicts_with": [6, 11] },
                    { "bit_position": 1, "name": "Time of Use", "requires_any": [0,6] },
                    { "bit_position": 2, "name": "Off-Grid Mode", "conflicts_with": [0, 1, 6, 11] },
                    { "bit_position": 3, "name": "Battery Wakeup Switch" },
                    { "bit_position": 4, "name": "Reserve Battery Mode", "conflicts_with": [11] },
                    { "bit_position": 5, "name": "Allow Grid to Charge the Battery" },
                    { "bit_position": 6, "name": "Feed-In Priority Mode", "conflicts_with": [0, 11] },
                    { "bit_position": 7, "name": "Batt OVC" },
                    { "bit_position": 8, "name": "Battery Forcecharge Peakshaving" },
                    { "bit_position": 9, "name": "Battery Current Correction" },
                    { "bit_position": 10, "name": "Battery Healing Mode" },
                    { "bit_position": 11, "name": "Peak Shaving Mode", "conflicts_with": [0, 4, 6] }
                ]
            },{
                "register": 43365,
                "entities": [
                    {"bit_position": 0, "name": "Generator connection position"},
                    {"bit_position": 1, "name": "With Generator"},
                    {"bit_position": 2, "name": "Generator enable signal"},
                    {"bit_position": 3, "name": "AC Coupling Position (off = GEN port, on = Backup port)"},
                    {"bit_position": 4, "name": "Generator access location"},
                ]
            },{
                "register": 43815,
                "entities": [
                    {"bit_position": 0, "name": "Generator charging period 1 switch"},
                    {"bit_position": 1, "name": "Generator charging period 2 switch"},
                    {"bit_position": 2, "name": "Generator charging period 3 switch"},
                    {"bit_position": 3, "name": "Generator charging period 4 switch"},
                    {"bit_position": 4, "name": "Generator charging period 5 switch"},
                    {"bit_position": 5, "name": "Generator charging period 6 switch"},
                ]
            },{
                "register": 43340,
                "entities": [
                    {"bit_position": 0, "name": "Generator Input Mode (off = Manual, on = Auto)"},
                    {"bit_position": 1, "name": "Generator Charge Enable"},
                ]
            },{
                "register": 43483,
                "entities": [
                    {"bit_position": 0, "name": "Dual Backup Enable"},
                    {"bit_position": 1, "name": "AC Coupling Enable"},
                    {"bit_position": 2, "name": "Smart load port grid-connected forced output"},
                    {"bit_position": 3, "name": "Allow export switch under self-generation and self-use"},
                    {"bit_position": 4, "name": "Backup2Load manual/automatic switch (off = Manual, on = Automatic)"},
                    {"bit_position": 5, "name": "Backup2Load manual enable"},
                    {"bit_position": 6, "name": "Smart load port stops output when off-grid"},
                    {"bit_position": 7, "name": "Grid Peak-shaving power enable"},
                ]
            }, {
                "register": 43249,
                "entities": [
                    {"bit_position": 0, "name": "MPPT Parallel Function"},
                    {"bit_position": 1, "name": "IgFollow"},
                    {"bit_position": 2, "name": "Relay Protection"},
                    {"bit_position": 3, "name": "I-Leak Protection"},
                    {"bit_position": 4, "name": "PV ISO Protection"},
                    {"bit_position": 5, "name": "Grid-Interference Protection"},
                    {"bit_position": 6, "name": "The DC component of the grid current protection switch"},
                    {"bit_position": 7, "name": "Const Voltage Mode Enable Const Voltage"},
                ]
            }, {
                "register": 43135,
                "entities": [
                    {"name": "RC Force Battery Charge",  "on_value": 1},
                    {"name": "RC Force Battery Discharge", "on_value": 2},
                ]
            },{
                "register": 43363,
                "entities": [
                    {"name": "Force Start Generator", "on_value": 1},
                ]
            },{
                "register": 43292,
                "entities": [
                    {"name": "Flexible Export Enabling Switch", "on_value": 170},
                ]
            }, {
                "register": 43707,
                "entities": [
                    {"name": "Grid Time of Use Charging Period 1", "bit_position": 0},
                    {"name": "Grid Time of Use Charging Period 2", "bit_position": 1},
                    {"name": "Grid Time of Use Charging Period 3", "bit_position": 2},
                    {"name": "Grid Time of Use Charging Period 4", "bit_position": 3},
                    {"name": "Grid Time of Use Charging Period 5", "bit_position": 4},
                    {"name": "Grid Time of Use Charging Period 6", "bit_position": 5},
                    {"name": "Grid Time of Use Discharge Period 1", "bit_position": 6},
                    {"name": "Grid Time of Use Discharge Period 2", "bit_position": 7},
                    {"name": "Grid Time of Use Discharge Period 3", "bit_position": 8},
                    {"name": "Grid Time of Use Discharge Period 4", "bit_position": 9},
                    {"name": "Grid Time of Use Discharge Period 5", "bit_position": 10},
                    {"name": "Grid Time of Use Discharge Period 6", "bit_position": 11},
                ]
            }
        ])
    elif modbus_controller.inverter_config.type == InverterType.GRID or modbus_controller.inverter_config.type == InverterType.STRING:
        switch_sensors.extend([{
            "read_register": 3089,
            "write_register": 3069,
            "entities": [
                {"on_value": 0xAA, "off_value": 0x55, "name": "Enable power limit feature"},
            ]
        }])

    switchEntities: List[SolisBinaryEntity] = []

    for main_entity in switch_sensors:
        for child_entity in main_entity[ENTITIES]:
           child_entity['register'] = main_entity['register']
           switchEntities.append(SolisBinaryEntity(hass, modbus_controller, child_entity))

    hass.data[DOMAIN][SWITCH_ENTITIES] = switchEntities
    async_add_devices(switchEntities, True)

    return True


