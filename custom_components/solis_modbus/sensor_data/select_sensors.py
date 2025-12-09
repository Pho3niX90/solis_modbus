from custom_components.solis_modbus.data.enums import InverterType, InverterFeature

def get_select_sensors(inverter_config):
    sensor_groups = []

    if inverter_config.type == InverterType.HYBRID:
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

        if InverterFeature.HV_BATTERY in inverter_config.features:
            sensor_groups.append({
                "register": 43009,
                "name": "Battery Model",
                "entities": [
                    { "name": "No battery", "on_value": 0x0000 },
                    { "name": "PYLON_HV", "on_value": 0x0100 },
                    { "name": "User define", "on_value": 0x0200 },
                    { "name": "B_BOX_HV BYD", "on_value": 0x0300 },
                    { "name": "LG_HV LG", "on_value": 0x0400 },
                    { "name": "SOLUNA_HV", "on_value": 0x0500 },
                    { "name": "Dyness HV", "on_value": 0x0600 },
                    { "name": "Aoboet HV", "on_value": 0x0700 },
                    { "name": "WECO HV", "on_value": 0x0800 },
                    { "name": "Alpha HV", "on_value": 0x0900 },
                    { "name": "GS Energy", "on_value": 0x0A00 },
                    { "name": "BYD-HVS/HVM/HVL", "on_value": 0x0B00 },
                    { "name": "Jinko", "on_value": 0x0C00 },
                    { "name": "FOX", "on_value": 0x0D00 },
                    { "name": "LG_16H", "on_value": 0x0E00 },
                    { "name": "PureDrive", "on_value": 0x0F00 },
                    { "name": "UZ ENERGY", "on_value": 0x1000 },
                    { "name": "Reserve017", "on_value": 0x1100 },
                    { "name": "Lotus", "on_value": 0x1200 },
                    { "name": "Fortress", "on_value": 0x1300 },
                    { "name": "AMPACE_HV", "on_value": 0x1400 },
                    { "name": "WTS", "on_value": 0x1500 },
                    { "name": "J-PACK-HV", "on_value": 0x1600 },
                    { "name": "SUNWODA HV", "on_value": 0x1700 },
                    { "name": "LG Enblock S", "on_value": 0x2600 },
                    { "name": "General-LiBat-HV", "on_value": 0x6300 },
                ]
            })
        else:
            sensor_groups.append({
                "register": 43009,
                "name": "Battery Model",
                "entities": [
                    { "name": "No battery", "on_value": 0 },
                    { "name": "PYLON_LV", "on_value": 1 },
                    { "name": "User define", "on_value": 2 },
                    { "name": "B_BOX_LV BYD", "on_value": 3 },
                    { "name": "Dyness LV", "on_value": 4 },
                    { "name": "PureDrive", "on_value": 5 },
                    { "name": "LG Chem LV LG", "on_value": 6 },
                    { "name": "AoBo LV", "on_value": 7 },
                    { "name": "JiaWei LV", "on_value": 8 },
                    { "name": "WECO LV", "on_value": 9 },
                    { "name": "FreedomWon LV", "on_value": 10 },
                    { "name": "Soluna LV", "on_value": 11 },
                    { "name": "GSL LV", "on_value": 12 },
                    { "name": "Rita LV", "on_value": 13 },
                    { "name": "RiSheng", "on_value": 14 },
                    { "name": "Alpha", "on_value": 15 },
                    { "name": "UZ ENERGY", "on_value": 16 },
                    { "name": "ATL", "on_value": 17 },
                    { "name": "Zeta", "on_value": 18 },
                    { "name": "Highstar", "on_value": 19 },
                    { "name": "KODAK", "on_value": 20 },
                    { "name": "FOX", "on_value": 21 },
                    { "name": "EXIDE", "on_value": 22 },
                    { "name": "HD Energy", "on_value": 23 },
                    { "name": "Pytes", "on_value": 24 },
                    { "name": "ARVIO", "on_value": 25 },
                    { "name": "PAND", "on_value": 26 },
                    { "name": "WANKE", "on_value": 27 },
                    { "name": "Dowell", "on_value": 28 },
                    { "name": "ROSEN ESS", "on_value": 29 },
                    { "name": "ZRGP", "on_value": 30 },
                    { "name": "Narada", "on_value": 31 },
                    { "name": "BST", "on_value": 32 },
                    { "name": "Cegasa", "on_value": 33 },
                    { "name": "Meterboost", "on_value": 34 },
                    { "name": "MOURA", "on_value": 35 },
                    { "name": "Tecloman", "on_value": 36 },
                    { "name": "Upower UE-H", "on_value": 37 },
                    { "name": "Upower UE-I", "on_value": 38 },
                    { "name": "SUNWODA", "on_value": 39 },
                    { "name": "CFE", "on_value": 40 },
                    { "name": "DMEGC", "on_value": 41 },
                    { "name": "J-Pack-LV", "on_value": 42 },
                    { "name": "HY4850", "on_value": 43 },
                    { "name": "JA-L", "on_value": 84 },
                    { "name": "Lithium Battery LV(RS485)", "on_value": 99 },
                    { "name": "General-LiBat-LV", "on_value": 100 },
                    { "name": "Lead Acid", "on_value": 101 },
                    { "name": "48V-LiBat-LV", "on_value": 102 },
                    { "name": "51.2V-LiBat-LV", "on_value": 103 }
                ]
            })

    # Add unique key to all
    for x in sensor_groups:
        x['unique'] = f"select_entity_{x['register']}"
        
    return sensor_groups
