from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from typing_extensions import List

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.data.enums import InverterFeature, InverterType
from custom_components.solis_modbus.helpers import get_controller
import logging

from custom_components.solis_modbus.sensors.solis_select_entity import SolisSelectEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_devices,
) -> None:
    controller: ModbusController = get_controller(hass, config_entry.data.get("host"), config_entry.data.get("slave", 1))
    # We only want this platform to be set up via discovery.
    _LOGGER.info("Options %s", len(config_entry.options))

    platform_config = config_entry.data or {}
    inverter_type = controller.inverter_config.type

    if len(config_entry.options) > 0:
        platform_config = config_entry.options

    _LOGGER.info(f"Solis platform_config: {platform_config}")

    sensor_groups = []

    if inverter_type == InverterType.HYBRID:
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
                    # Adheres to RS485_MODBUS ESINV-33000ID Hybrid Inverter V3.2 / Appendix 8
                    { "bit_position": 0, "name": "Self-Use", "conflicts_with": [0, 6, 11] },
                    { "bit_position": 0, "name": "Self-Use + TOU", "conflicts_with": [0, 6, 11], "requires": [1] },
                    { "bit_position": 2, "name": "Off-Grid Operation", "conflicts_with": [0, 1, 2] },
                    { "bit_position": 6, "name": "Feed-in Priority", "conflicts_with": [0, 6, 11] },
                    { "bit_position": 6, "name": "Feed-in + TOU", "conflicts_with": [0, 6, 11] ,"requires": [1] },
                    { "bit_position": 11, "name": "Peak Shaving", "conflicts_with": [0, 4, 6, 11] }
                ]
            }
        ]

        if InverterFeature.HV_BATTERY in controller.inverter_config.features:
            sensor_groups.append({
                "register": 43009,
                "name": "Battery Model",
                "entities": [
                    { "name": "No battery", "on_value": 000 },
                    { "name": "PYLON_HV", "on_value": 100 },
                    { "name": "User define", "on_value": 200 },
                    { "name": "B_BOX_HV BYD", "on_value": 300 },
                    { "name": "LG_HV LG", "on_value": 400 },
                    { "name": "SOLUNA_HV", "on_value": 500 },
                    { "name": "Dyness HV", "on_value": 600 },
                    { "name": "Aoboet HV", "on_value": 700 },
                    { "name": "WECO HV", "on_value": 800 },
                    { "name": "Alpha HV", "on_value": 900 },
                    { "name": "GS Energy", "on_value": A00 },
                    { "name": "BYD-HVS/HVM/HVL", "on_value": B00 },
                    { "name": "Jinko", "on_value": C00 },
                    { "name": "FOX", "on_value": D00 },
                    { "name": "LG_16H", "on_value": E00 },
                    { "name": "PureDrive", "on_value": F00 },
                    { "name": "UZ ENERGY", "on_value": 1000 },
                    { "name": "Reserve017", "on_value": 1100 },
                    { "name": "Lotus", "on_value": 1200 },
                    { "name": "Fortress", "on_value": 1300 },
                    { "name": "AMPACE_HV", "on_value": 1400 },
                    { "name": "WTS", "on_value": 1500 },
                    { "name": "J-PACK-HV", "on_value": 1600 },
                    { "name": "SUNWODA HV", "on_value": 1700 },
                    { "name": "LG Enblock S", "on_value": 2600 },
                    { "name": "General-LiBat-HV", "on_value": 6300 },
                ]
            })
        else:
            sensor_groups.append({
                "register": 43009,
                "name": "Battery Model",
                "entities": [
                    { "name": "No battery", "on_value": 000 },
                    { "name": "PYLON_LV", "on_value": 001},
                    { "name": "User define", "on_value": 002 },
                    { "name": "B_BOX_LV BYD", "on_value": 003 },
                    { "name": "Dyness LV", "on_value": 004 },
                    { "name": "PureDrive", "on_value": 005 },
                    { "name": "LG Chem LV LG", "on_value": 006 },
                    { "name": "AoBo LV", "on_value": 007 },
                    { "name": "JiaWei LV", "on_value": 008 },
                    { "name": "WECO LV", "on_value": 009 },
                    { "name": "FreedomWon LV", "on_value": 00A },
                    { "name": "Soluna LV", "on_value": 00B },
                    { "name": "GSL LV", "on_value": 00C },
                    { "name": "Rita LV", "on_value": 00D },
                    { "name": "RiSheng", "on_value": 00E },
                    { "name": "Alpha", "on_value": 00F },
                    { "name": "CATL", "on_value": 010 },
                    { "name": "ATL", "on_value": 011 },
                    { "name": "Zeta", "on_value": 012 },
                    { "name": "Highstar", "on_value": 013 },
                    { "name": "KODAK", "on_value": 014 },
                    { "name": "FOX", "on_value": 015 },
                    { "name": "EXIDE", "on_value": 016 },
                    { "name": "HD Energy LV", "on_value": 017 },
                    { "name": "Pytes", "on_value": 018 },
                    { "name": "ARVIO", "on_value": 019 },
                    { "name": "PAND", "on_value": 01A },
                    { "name": "WANKE", "on_value": 01B },
                    { "name": "Dowell", "on_value": 01C },
                    { "name": "ROSEN ESS", "on_value": 01D },
                    { "name": "ZRGP", "on_value": 01E },
                    { "name": "Narada", "on_value": 01F },
                    { "name": "BST", "on_value": 020 },
                    { "name": "Cegasa", "on_value": 021 },
                    { "name": "Meterboost", "on_value": 022 },
                    { "name": "MOURA", "on_value": 023 },
                    { "name": "Tecloman", "on_value": 024 },
                    { "name": "Upower UE-H", "on_value": 025 },
                    { "name": "Upower UE-I", "on_value": 026 },
                    { "name": "SUNWODA", "on_value": 027 },
                    { "name": "CFE", "on_value": 028 },
                    { "name": "Lead Acid", "on_value": 064 },
                    { "name": "48V-LiBat-LV", "on_value": 065 },
                    { "name": "51.2V-LiBat-LV", "on_value": 066 }
                ]
            })

    sensors: List[SolisSelectEntity] = []
    for sensor_group in sensor_groups:
        sensors.append(SolisSelectEntity(hass, controller, sensor_group))
    _LOGGER.info(f"Select entities = {len(sensors)}")
    async_add_devices(sensors, True)
