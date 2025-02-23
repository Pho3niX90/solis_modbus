from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower, UnitOfTime, UnitOfEnergy, UnitOfElectricCurrent, UnitOfElectricPotential

from custom_components.solis_modbus.data.enums import PollSpeed

# base on RS485_MODBUS Communication Protocol Ver18
string_sensors = [
    # offset by -1
    {
        "register_start": 2999,
        "poll_speed": PollSpeed.FAST,
        "entities": [
            {"name": "Product Model", "unique": "solis_modbus_product_model",
             "unit_of_measurement": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['2999'], "multiplier": 1},
            {"name": "DSP Software Version", "unique": "solis_modbus_dsp_software_version",
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3000'], "multiplier": 1},
            {"name": "HMI Major Version", "unique": "solis_modbus_hmi_major_version",
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3001'], "multiplier": 1},
            {"name": "AC Output Type", "unique": "solis_modbus_ac_output_type",
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3002'], "multiplier": 1},
            {"name": "DC Input Type", "unique": "solis_modbus_dc_input_type",
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3003'], "multiplier": 1},
            {"name": "Active Power", "unique": "solis_modbus_active_power",
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3004','3005'], "multiplier": 1},
            {"name": "Total DC Output Power", "unique": "solis_modbus_total_dc_output_power",
             "unit_of_measurement": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3006','3007'], "multiplier": 1},
        ]
    },
    # offset by -1
    {
        "register_start": 3021,
        "poll_speed": PollSpeed.FAST,
        "entities": [
            {"name": "DC Voltage 1", "unique": "solis_modbus_dc_voltage_1",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3021'], "multiplier": 0.1},
            {"name": "DC Current 1", "unique": "solis_modbus_dc_current_1",
             "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3022'], "multiplier": 0.1},
            {"name": "DC Voltage 2", "unique": "solis_modbus_dc_voltage_2",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3023'], "multiplier": 0.1},
            {"name": "DC Current 2", "unique": "solis_modbus_dc_current_2",
             "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3024'], "multiplier": 0.1},
            {"name": "DC Voltage 3", "unique": "solis_modbus_dc_voltage_3",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3025'], "multiplier": 0.1},
            {"name": "DC Current 3", "unique": "solis_modbus_dc_current_3",
             "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3026'], "multiplier": 0.1},
            {"name": "DC Voltage 4", "unique": "solis_modbus_dc_voltage_4",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3027'], "multiplier": 0.1},
            {"name": "DC Current 4", "unique": "solis_modbus_dc_current_4",
             "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3028'], "multiplier": 0.1},
        ]
    },
    {
        "register_start": 3179,
        "poll_speed": PollSpeed.FAST,
        "entities": [
            {"name": "Shading MPPT Scan Enable", "unique": "solis_modbus_shading_mppt_scan_enable",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3179'], "multiplier": 0.1},
            {"name": "Shading MPPT Scan Time Interval", "unique": "solis_modbus_shading_mppt_scan_interval",
             "unit_of_measurement": UnitOfTime.MINUTES,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3180'], "multiplier": 1, "editable": True, "min": 10, "max": 180},
        ]
    },
    {
        "register_start": 3250,
        "poll_speed": PollSpeed.FAST,
        "entities": [
            {"name": "Meter AC Voltage A", "unique": "solis_modbus_meter_ac_voltage_a",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3250'], "multiplier": 0.1},
            {"name": "Meter AC Current A", "unique": "solis_modbus_meter_ac_current_a",
             "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3251'], "multiplier": 0.01},
            {"name": "Meter AC Voltage B", "unique": "solis_modbus_meter_ac_voltage_b",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3252'], "multiplier": 0.1},
            {"name": "Meter AC Current B", "unique": "solis_modbus_meter_ac_current_b",
             "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3253'], "multiplier": 0.01},
            {"name": "Meter AC Voltage C", "unique": "solis_modbus_meter_ac_voltage_c",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3254'], "multiplier": 0.1},
            {"name": "Meter AC Current C", "unique": "solis_modbus_meter_ac_current_c",
             "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3255'], "multiplier": 0.01},
            {"name": "Meter AC Active Power A", "unique": "solis_modbus_meter_ac_active_power_a",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3256','3257'], "multiplier": 0.001},
            {"name": "Meter AC Active Power B", "unique": "solis_modbus_meter_ac_active_power_b",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3258','3259'], "multiplier": 0.001},
            {"name": "Meter AC Active Power C", "unique": "solis_modbus_meter_ac_active_power_c",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3260','3261'], "multiplier": 0.001},
            {"name": "Meter AC Active Power Total", "unique": "solis_modbus_meter_ac_active_power_total",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3262','3263'], "multiplier": 0.001},
        ]
    },
    {
        "register_start": 36013,
        "scan_interval": 0,
        "entities": [
            {"name": "Model No", "unique": "solis_modbus_inverter_model_no",
             "register": ['36013'], "multiplier": 0},
            {"name": "Inverter EPM Firmware Version", "unique": "solis_modbus_inverter_epm_firmware_version",
             "register": ['36014'], "multiplier": 0},
        ]
    },
    {
        "register_start": 36022,
        "scan_interval": 60,
        "entities": [

            {"name": "Clock (Hours)",
             "unique": "solis_modbus_inverter_clock_hours",
             "register": ['36022'], "multiplier": 0,
             "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
            {"name": "Clock (Minutes)",
             "unique": "solis_modbus_inverter_clock_minutes",
             "register": ['36023'], "multiplier": 0,
             "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
            {"name": "Clock (Seconds)",
             "unique": "solis_modbus_inverter_clock_seconds",
             "register": ['36024'], "multiplier": 0,
             "unit_of_measurement": UnitOfTime.SECONDS, "state_class": SensorStateClass.MEASUREMENT},
        ]
    },
    {
        "register_start": 36028,
        "poll_speed": PollSpeed.FAST,
        "entities": [
            {"name": "Total Load power",
             "unique": "solis_modbus_inverter_total_load_power",
             "register": ['36028', '36029'], "device_class": SensorDeviceClass.POWER, "multiplier": 100,
             "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT}
        ]
    },
    {
        "register_start": 36050,
        "poll_speed": PollSpeed.SLOW,
        "entities": [
            {"name": "Total Generation Energy",
             "unique": "solis_modbus_inverter_total_generation_energy",
             "register": ['36050', '36051'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

            {"name": "Load Total Consumption Energy",
             "unique": "solis_modbus_inverter_total_load_power",
             "register": ['36052', '36053'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

            {"name": "Grid Import Total Active Energy",
             "unique": "solis_modbus_inverter_grid_import_total_active_energy",
             "register": ['36054', '36055'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

            {"name": "Grid Export Total Active Energy",
             "unique": "solis_modbus_inverter_grid_export_total_active_energy",
             "register": ['36056', '36057'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.01,
             "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
        ]
    },
    {
        "register_start": 33005,
        "poll_speed": PollSpeed.FAST,
        "entities": [
            {"name": "Active Power",
             "unique": "solis_modbus_inverter_active_power",
             "register": ['33005', '33006'], "device_class": SensorDeviceClass.POWER, "multiplier": 1,
             "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},

            {"name": "Total DC Output Power",
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
