from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower, UnitOfTime, UnitOfEnergy, UnitOfElectricCurrent, UnitOfElectricPotential, \
    UnitOfTemperature, UnitOfFrequency, UnitOfApparentPower, UnitOfReactivePower

from custom_components.solis_modbus.data.enums import PollSpeed

# base on RS485_MODBUS Communication Protocol Ver19
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
             "state_class": SensorStateClass.MEASUREMENT, "device_class": SensorDeviceClass.POWER,
             "unit_of_measurement": UnitOfPower.WATT,
             "register": ['3004','3005'], "multiplier": 1},
            {"name": "Total DC Output Power", "unique": "solis_modbus_total_dc_output_power",
             "unit_of_measurement": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3006','3007'], "multiplier": 1},
            {"name": "Total Energy", "unique": "solis_modbus_total_energy",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3008', '3009'], "multiplier": 1},
            {"name": "Energy This Month", "unique": "solis_modbus_energy_this_month",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3010', '3011'], "multiplier": 1},
            {"name": "Energy Last Month", "unique": "solis_modbus_energy_last_month",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3012', '3013'], "multiplier": 1},
            {"name": "Energy Today", "unique": "solis_modbus_energy_today",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3014'], "multiplier": 0.1},
            {"name": "Energy Yesterday", "unique": "solis_modbus_energy_yesterday",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3015'], "multiplier": 0.1},
            {"name": "Energy This Year", "unique": "solis_modbus_energy_this_year",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3016','3017'], "multiplier": 1},
            {"name": "Energy Last Year", "unique": "solis_modbus_energy_last_year",
             "unit_of_measurement": UnitOfPower.KILO_WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3018','3019'], "multiplier": 1},

            {"type": "reserve", "register": ['3020']},

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
             "register": ['3028'], "multiplier": 0.1}, #30
        ]
    },
    {
        "register_start": 3033,
        "poll_speed": PollSpeed.FAST,
        "entities": [

            {"name": "A Phase Voltage", "unique": "solis_modbus_inverter_a_phase_voltage",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3033'], "multiplier": 0.1},
            {"name": "B Phase Voltage", "unique": "solis_modbus_inverter_b_phase_voltage",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3034'], "multiplier": 0.1},
            {"name": "C Phase Voltage", "unique": "solis_modbus_inverter_c_phase_voltage",
             "unit_of_measurement": UnitOfElectricPotential.VOLT, "device_class": SensorDeviceClass.VOLTAGE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3035'], "multiplier": 0.1},

            {"name": "A Phase Current", "unique": "solis_modbus_inverter_a_phase_current",
             "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3036'], "multiplier": 0.1},
            {"name": "B Phase Current", "unique": "solis_modbus_inverter_b_phase_current",
             "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3037'], "multiplier": 0.1},
            {"name": "C Phase Current", "unique": "solis_modbus_inverter_c_phase_current",
             "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "device_class": SensorDeviceClass.CURRENT,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3038'], "multiplier": 0.1},

            {"type": "reserve", "register": ['3039', '3040']},

            {"name": "Inverter Temperature", "unique": "solis_modbus_inverter_temperature",
             "unit_of_measurement": UnitOfTemperature.CELSIUS, "device_class": SensorDeviceClass.TEMPERATURE,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3041'], "multiplier": 0.1},
            {"name": "Grid Frequency", "unique": "solis_modbus_grid_frequency",
             "unit_of_measurement": UnitOfFrequency.HERTZ, "device_class": SensorDeviceClass.FREQUENCY,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3042'], "multiplier": 0.01},
            {"name": "Inverter Status", "unique": "solis_modbus_inverter_status",
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3043'], "multiplier": 1},
            {"name": "Limited active power adjustment rated power output value", "unique": "solis_modbus_inverter_limited_active_power_output_value",
             "unit_of_measurement": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3044', '3045'], "multiplier": 1},
            {"name": "Reactive power regulation rated power output value", "unique": "solis_modbus_inverter_reactive_power_regulation_rated_power_output_value",
             "unit_of_measurement": UnitOfReactivePower.VOLT_AMPERE_REACTIVE, "device_class": SensorDeviceClass.REACTIVE_POWER,
             "state_class": SensorStateClass.MEASUREMENT,
             "register": ['3046', '3047'], "multiplier": 1},
        ]
    },
    {
        "register_start": 3179,
        "poll_speed": PollSpeed.SLOW,
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
    }
]

string_sensors_derived = [
]
