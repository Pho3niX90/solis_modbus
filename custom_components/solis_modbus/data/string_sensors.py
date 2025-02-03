from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfElectricPotential, UnitOfElectricCurrent, UnitOfPower, UnitOfTime, UnitOfEnergy, \
    UnitOfReactivePower, UnitOfFrequency, UnitOfTemperature, UnitOfApparentPower, PERCENTAGE

string_sensors = [
    {
        "register_start": 3257,
        "scan_interval": 0,
        "entities": [
            {"type": "SS", "name": "Solis Inverter Power A", "unique": "solis_modbus_inverter_power_a",
             "register": ['3257', '3258'], "multiplier": 1,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
            {"type": "SS", "name": "Solis Inverter Power B", "unique": "solis_modbus_inverter_power_b",
             "register": ['3259', '3260'], "multiplier": 1,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
            {"type": "SS", "name": "Solis Inverter Power C", "unique": "solis_modbus_inverter_power_c",
             "register": ['3261', '3262'], "multiplier": 1,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
            {"type": "SS", "name": "Solis Inverter Total Active Power", "unique": "solis_modbus_inverter_total_active_power",
             "register": ['3263', '3264'], "multiplier": 1,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
        ]
    },
    {
        "register_start": 36011,
        "scan_interval": 0,
        "entities": [
            {"type": "SS", "name": "Solis Inverter Total Power", "unique": "solis_modbus_inverter_total_power",
             "register": ['36011', '36012'], "multiplier": 100,
             "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
        ]
    },
    {
        "register_start": 36028,
        "scan_interval": 0,
        "entities": [
            {"type": "SS", "name": "Solis Inverter Total Load Power", "unique": "solis_modbus_inverter_total_load_power",
             "register": ['36028', '36029'], "multiplier": 100,
             "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
        ]
    },
    {
        "register_start": 36050,
        "scan_interval": 0,
        "entities": [
            {"type": "SS", "name": "Solis Inverter Total Generation Energy", "unique": "solis_modbus_inverter_total_generation_energy",
             "register": ['36050', '36051'], "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
            {"type": "SS", "name": "Solis Inverter Total Consumption Energy", "unique": "solis_modbus_inverter_total_consumption_energy",
             "register": ['36052', '36053'], "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
            {"type": "SS", "name": "Solis Inverter Total Grid Import Active Energy", "unique": "solis_modbus_inverter_total_grid_import_active_energy",
             "register": ['36054', '36055'], "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
            {"type": "SS", "name": "Solis Inverter Total Grid Export Active Energy", "unique": "solis_modbus_inverter_total_grid_export_active_energy",
             "register": ['36056', '36057'], "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
            {"type": "SS", "name": "Solis Inverter EPM Transmission Switch", "unique": "solis_modbus_inverter_epm_transmission_switch",
             "register": ['36058'], "multiplier": 0.01},
            {"type": "SS", "name": "Solis Inverter Batch Upgrade Flag", "unique": "solis_modbus_inverter_batch_upgrade_flag",
             "register": ['36060'], "multiplier": 1},
            {"type": "SS", "name": "Solis Inverter EPM Model", "unique": "solis_modbus_inverter_epm_model",
             "register": ['36060'], "multiplier": 1},
        ]
    },
]

string_sensors_derived = [

]