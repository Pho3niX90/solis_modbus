from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower, UnitOfTime, UnitOfEnergy

# base on RS485_MODBUS Communication Protocol Ver18
string_sensors = [
    {
        "register_start": 36013,
        "scan_interval": 0,
        "entities": [
            {"type": "SS", "name": "Model No", "unique": "solis_modbus_inverter_model_no",
             "register": ['36013'], "multiplier": 0},
            {"type": "SS", "name": "Inverter EPM Firmware Version", "unique": "solis_modbus_inverter_epm_firmware_version",
             "register": ['36014'], "multiplier": 0},
        ]
    },
    {
        "register_start": 36022,
        "scan_interval": 60,
        "entities": [

            {"type": "SS", "name": "Clock (Hours)",
             "unique": "solis_modbus_inverter_clock_hours",
             "register": ['36022'], "multiplier": 0,
             "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
            {"type": "SS", "name": "Clock (Minutes)",
             "unique": "solis_modbus_inverter_clock_minutes",
             "register": ['36023'], "multiplier": 0,
             "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
            {"type": "SS", "name": "Clock (Seconds)",
             "unique": "solis_modbus_inverter_clock_seconds",
             "register": ['36024'], "multiplier": 0,
             "unit_of_measurement": UnitOfTime.SECONDS, "state_class": SensorStateClass.MEASUREMENT},
        ]
    },
    {
        "register_start": 36028,
        "scan_interval": 60,
        "entities": [
            {"type": "SS", "name": "Total Load power",
             "unique": "solis_modbus_inverter_total_load_power",
             "register": ['36028', '36029'], "device_class": SensorDeviceClass.POWER, "multiplier": 100,
             "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT}
        ]
    },
    {
        "register_start": 36050,
        "scan_interval": 60,
        "entities": [
            {"type": "SS", "name": "Total Generation Energy",
             "unique": "solis_modbus_inverter_total_generation_energy",
             "register": ['36050', '36051'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

            {"type": "SS", "name": "Load Total Consumption Energy",
             "unique": "solis_modbus_inverter_total_load_power",
             "register": ['36052', '36053'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

            {"type": "SS", "name": "Grid Import Total Active Energy",
             "unique": "solis_modbus_inverter_grid_import_total_active_energy",
             "register": ['36054', '36055'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

            {"type": "SS", "name": "Grid Export Total Active Energy",
             "unique": "solis_modbus_inverter_grid_export_total_active_energy",
             "register": ['36056', '36057'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
        ]
    },
    {
        "register_start": 33005,
        "scan_interval": 15,
        "entities": [
            {"type": "SS", "name": "Active Power",
             "unique": "solis_modbus_inverter_active_power",
             "register": ['33005', '33006'], "device_class": SensorDeviceClass.POWER, "multiplier": 1,
             "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},

            {"type": "SS", "name": "Total DC Output Power",
             "unique": "solis_modbus_inverter_total_dc_output_power",
             "register": ['33007', '33008'], "device_class": SensorDeviceClass.POWER, "multiplier": 1,
             "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
        ]
    },
]

string_sensors_derived = [
    {"type": "SDS", "name": "Status String",
     "unique": "solis_modbus_inverter_current_status_string", "multiplier": 0,
     "register": ['33095']},

    {"type": "SDS", "name": "PV Power 1",
     "unique": "solis_modbus_inverter_dc_power_1", "device_class": SensorDeviceClass.POWER, "multiplier": 0.1,
     "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT,
     "register": ['33049', '33050']},

    {"type": "SDS", "name": "PV Power 2",
     "unique": "solis_modbus_inverter_dc_power_2", "device_class": SensorDeviceClass.POWER, "multiplier": 0.1,
     "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT,
     "register": ['33051', '33052']},

    {"type": "SDS", "name": "PV Power 3",
     "unique": "solis_modbus_inverter_dc_power_3", "device_class": SensorDeviceClass.POWER, "multiplier": 0.1,
     "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT,
     "register": ['33053', '33054']},

    {"type": "SDS", "name": "PV Power 4",
     "unique": "solis_modbus_inverter_dc_power_4", "device_class": SensorDeviceClass.POWER, "multiplier": 0.1,
     "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT,
     "register": ['33055', '33056']},

    {"type": "SDS", "name": "Battery Charge Power",
     "unique": "solis_modbus_inverter_battery_charge_power", "device_class": SensorDeviceClass.POWER,
     "multiplier": 0.1,
     "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT,
     "register": ['33149', '33150', '33135', '0']},
    {"type": "SDS", "name": "Battery Discharge Power",
     "unique": "solis_modbus_inverter_battery_discharge_power", "device_class": SensorDeviceClass.POWER,
     "multiplier": 0.1,
     "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT,
     "register": ['33149', '33150', '33135', '1']}
]