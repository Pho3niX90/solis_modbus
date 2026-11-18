from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)

from custom_components.solis_modbus.data.enums import Category, DataType, InverterFeature, PollSpeed

# --- Multi-MPPT string inverters (80-110K-5G class) --------------------------------
# MPPT 1-4 always come from DC Voltage/Current 1-4 below (3021-3028), so their
# entities, unique IDs and history are the same on every string model. MPPT 5-15 come
# from the protocol's per-MPPT block: voltage at doc 3500+n-1, current at doc 3530+n-1
# (wire = doc - 1). Voltage and current are read in ONE block, so DC Power [n] always
# multiplies a voltage and a current from the same read. Entities carry "mppt" (or
# "string") so setup can drop the ones above the entry's MPPT count
# (helpers.apply_mppt_count); the groups here describe the most the protocol allows.
FIRST_EXTENDED_MPPT = 5
MULTI_MPPT_MAX = 15
MULTI_MPPT_STRINGS = 20
MPPT_VOLTAGE_WIRE_BASE = 3498  # MPPT n voltage = 3498 + n (doc 3500 = MPPT 1)
MPPT_CURRENT_WIRE_BASE = 3528  # MPPT n current = 3528 + n (doc 3530 = MPPT 1)
STRING_CURRENT_WIRE_BASE = 3299  # string k current = 3299 + k (doc 3301 = PV1)


def _reserve(register: int) -> dict:
    return {"type": "reserve", "register": [str(register)]}


def _string_group() -> dict:
    """Doc 3287-3320: string combination, total PV voltage/current, PV string currents 1-20.

    Field-verified on a Solis-100K-5G: the string currents sum to Total PV Current and
    each MPPT current is the sum of its two strings. The Solis datalogger reads this
    range too (3287-3300 and 3301-3338).
    """
    entities = [
        {
            # 0 = one voltage for two string currents, 3 = one voltage for three.
            "name": "PV String Voltage Current Combination",
            "unique": "solis_modbus_pv_string_combination",
            "category": Category.BASIC_INFORMATION,
            "register": ["3286"],
            "multiplier": 1,
        },
        *(_reserve(r) for r in range(3287, 3298)),
        {
            "name": "Total PV Voltage",
            "unique": "solis_modbus_total_pv_voltage",
            "unit_of_measurement": UnitOfElectricPotential.VOLT,
            "device_class": SensorDeviceClass.VOLTAGE,
            "state_class": SensorStateClass.MEASUREMENT,
            "register": ["3298"],
            "multiplier": 0.1,
        },
        {
            "name": "Total PV Current",
            "unique": "solis_modbus_total_pv_current",
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
            "device_class": SensorDeviceClass.CURRENT,
            "state_class": SensorStateClass.MEASUREMENT,
            "register": ["3299"],
            "multiplier": 0.1,
            "data_type": DataType.S16,
        },
    ]
    for k in range(1, MULTI_MPPT_STRINGS + 1):
        entities.append(
            {
                "name": f"PV String Current {k}",
                "unique": f"solis_modbus_pv_string_current_{k}",
                "string": k,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": [str(STRING_CURRENT_WIRE_BASE + k)],
                "multiplier": 0.1,
            }
        )
    return {
        "register_start": 3286,
        "feature_requirement": [InverterFeature.MULTI_MPPT],
        "poll_speed": PollSpeed.NORMAL,
        "entities": entities,
    }


def _extended_mppt_group() -> dict:
    """DC Voltage/Current 5-15 (doc 3504-3514 and 3534-3544), with the registers between as reserves."""
    mppts = range(FIRST_EXTENDED_MPPT, MULTI_MPPT_MAX + 1)
    voltages = [
        {
            "name": f"DC Voltage {n}",
            "unique": f"solis_modbus_dc_voltage_{n}",
            "mppt": n,
            "unit_of_measurement": UnitOfElectricPotential.VOLT,
            "device_class": SensorDeviceClass.VOLTAGE,
            "state_class": SensorStateClass.MEASUREMENT,
            "register": [str(MPPT_VOLTAGE_WIRE_BASE + n)],
            "multiplier": 0.1,
        }
        for n in mppts
    ]
    gap = [_reserve(r) for r in range(MPPT_VOLTAGE_WIRE_BASE + MULTI_MPPT_MAX + 1, MPPT_CURRENT_WIRE_BASE + FIRST_EXTENDED_MPPT)]
    currents = [
        {
            "name": f"DC Current {n}",
            "unique": f"solis_modbus_dc_current_{n}",
            "mppt": n,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
            "device_class": SensorDeviceClass.CURRENT,
            "state_class": SensorStateClass.MEASUREMENT,
            "register": [str(MPPT_CURRENT_WIRE_BASE + n)],
            "multiplier": 0.1,
            "data_type": DataType.S16,
        }
        for n in mppts
    ]
    return {
        "register_start": MPPT_VOLTAGE_WIRE_BASE + FIRST_EXTENDED_MPPT,
        "feature_requirement": [InverterFeature.MULTI_MPPT],
        "poll_speed": PollSpeed.NORMAL,
        "entities": voltages + gap + currents,
    }


def multi_mppt_groups() -> list[dict]:
    return [_string_group(), _extended_mppt_group()]


def multi_mppt_derived() -> list[dict]:
    """DC Power 5-15 = DC Voltage [n] x DC Current [n] (signed); see SolisDerivedSensor."""
    return [
        {
            "name": f"DC Power {n}",
            "unique": f"solis_modbus_dc_power_{n}",
            "mppt": n,
            "device_class": SensorDeviceClass.POWER,
            "multiplier": 0.1,
            "unit_of_measurement": UnitOfPower.WATT,
            "state_class": SensorStateClass.MEASUREMENT,
            "register": [str(MPPT_VOLTAGE_WIRE_BASE + n), str(MPPT_CURRENT_WIRE_BASE + n)],
        }
        for n in range(FIRST_EXTENDED_MPPT, MULTI_MPPT_MAX + 1)
    ]


# base on RS485_MODBUS Communication Protocol Ver19
string_sensors = [
    # offset by -1
    {
        "register_start": 2999,
        "essential": True,
        "poll_speed": PollSpeed.FAST,
        "entities": [
            {
                "name": "Product Model",
                "unique": "solis_modbus_product_model",
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["2999"],
                "multiplier": 1,
            },
            {
                "name": "DSP Software Version",
                "unique": "solis_modbus_dsp_software_version",
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3000"],
                "multiplier": 1,
            },
            {
                "name": "HMI Major Version",
                "unique": "solis_modbus_hmi_major_version",
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3001"],
                "multiplier": 1,
            },
            {
                "name": "AC Output Type",
                "unique": "solis_modbus_ac_output_type",
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3002"],
                "multiplier": 1,
            },
            {
                "name": "DC Input Type",
                "unique": "solis_modbus_dc_input_type",
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3003"],
                "multiplier": 1,
            },
            {
                "name": "Active Power",
                "unique": "solis_modbus_active_power",
                "state_class": SensorStateClass.MEASUREMENT,
                "device_class": SensorDeviceClass.POWER,
                "unit_of_measurement": UnitOfPower.WATT,
                "register": ["3004", "3005"],
                "multiplier": 1,
            },
            {
                "name": "Total DC Output Power",
                "unique": "solis_modbus_total_dc_output_power",
                "unit_of_measurement": UnitOfPower.WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3006", "3007"],
                "multiplier": 1,
            },
            {
                "name": "Total Energy",
                "unique": "solis_modbus_total_energy",
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "register": ["3008", "3009"],
                "multiplier": 1,
                "data_type": DataType.U32,
            },
            {
                "name": "Energy This Month",
                "unique": "solis_modbus_energy_this_month",
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "register": ["3010", "3011"],
                "multiplier": 1,
                "data_type": DataType.U32,
            },
            {
                "name": "Energy Last Month",
                "unique": "solis_modbus_energy_last_month",
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "register": ["3012", "3013"],
                "multiplier": 1,
                "data_type": DataType.U32,
            },
            {
                "name": "Energy Today",
                "unique": "solis_modbus_energy_today",
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "register": ["3014"],
                "multiplier": 0.1,
            },
            {
                "name": "Energy Yesterday",
                "unique": "solis_modbus_energy_yesterday",
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "register": ["3015"],
                "multiplier": 0.1,
            },
            {
                "name": "Energy This Year",
                "unique": "solis_modbus_energy_this_year",
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "register": ["3016", "3017"],
                "multiplier": 1,
                "data_type": DataType.U32,
            },
            {
                "name": "Energy Last Year",
                "unique": "solis_modbus_energy_last_year",
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "register": ["3018", "3019"],
                "multiplier": 1,
                "data_type": DataType.U32,
            },
            {"type": "reserve", "register": ["3020"]},
            {
                "name": "DC Voltage 1",
                "unique": "solis_modbus_dc_voltage_1",
                "mppt": 1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3021"],
                "multiplier": 0.1,
            },
            {
                "name": "DC Current 1",
                "unique": "solis_modbus_dc_current_1",
                "mppt": 1,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3022"],
                "multiplier": 0.1,
            },
            {
                "name": "DC Voltage 2",
                "unique": "solis_modbus_dc_voltage_2",
                "mppt": 2,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3023"],
                "multiplier": 0.1,
            },
            {
                "name": "DC Current 2",
                "unique": "solis_modbus_dc_current_2",
                "mppt": 2,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3024"],
                "multiplier": 0.1,
            },
            {
                "name": "DC Voltage 3",
                "unique": "solis_modbus_dc_voltage_3",
                "mppt": 3,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3025"],
                "multiplier": 0.1,
            },
            {
                "name": "DC Current 3",
                "unique": "solis_modbus_dc_current_3",
                "mppt": 3,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3026"],
                "multiplier": 0.1,
            },
            {
                "name": "DC Voltage 4",
                "unique": "solis_modbus_dc_voltage_4",
                "mppt": 4,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3027"],
                "multiplier": 0.1,
            },
            {
                "name": "DC Current 4",
                "unique": "solis_modbus_dc_current_4",
                "mppt": 4,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3028"],
                "multiplier": 0.1,
            },  # 30
        ],
    },
    {
        "register_start": 3033,
        "essential": True,
        "poll_speed": PollSpeed.FAST,
        "entities": [
            {
                "name": "A Phase Voltage",
                "unique": "solis_modbus_inverter_a_phase_voltage",
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3033"],
                "multiplier": 0.1,
            },
            {
                "name": "B Phase Voltage",
                "unique": "solis_modbus_inverter_b_phase_voltage",
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3034"],
                "multiplier": 0.1,
            },
            {
                "name": "C Phase Voltage",
                "unique": "solis_modbus_inverter_c_phase_voltage",
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3035"],
                "multiplier": 0.1,
            },
            {
                "name": "A Phase Current",
                "unique": "solis_modbus_inverter_a_phase_current",
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3036"],
                "multiplier": 0.1,
            },
            {
                "name": "B Phase Current",
                "unique": "solis_modbus_inverter_b_phase_current",
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3037"],
                "multiplier": 0.1,
            },
            {
                "name": "C Phase Current",
                "unique": "solis_modbus_inverter_c_phase_current",
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3038"],
                "multiplier": 0.1,
            },
            {"type": "reserve", "register": ["3039"]},
            {
                "name": "Working Mode",
                "unique": "solis_modbus_inverter_working_mode",
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3040"],
                "multiplier": 1,
            },
            {
                "name": "Inverter Temperature",
                "unique": "solis_modbus_inverter_temperature",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
                "device_class": SensorDeviceClass.TEMPERATURE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3041"],
                "multiplier": 0.1,
                "data_type": DataType.S16,
            },
            {
                "name": "Grid Frequency",
                "unique": "solis_modbus_grid_frequency",
                "unit_of_measurement": UnitOfFrequency.HERTZ,
                "device_class": SensorDeviceClass.FREQUENCY,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3042"],
                "multiplier": 0.01,
            },
            {
                "name": "Inverter Status",
                "unique": "solis_modbus_inverter_status",
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3043"],
                "multiplier": 1,
            },
            {
                "name": "Limited active power adjustment rated power output value",
                "unique": "solis_modbus_inverter_limited_active_power_output_value",
                "unit_of_measurement": UnitOfPower.WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3044", "3045"],
                "multiplier": 1,
            },
            {
                "name": "Reactive power regulation rated power output value",
                "unique": "solis_modbus_inverter_reactive_power_regulation_rated_power_output_value",
                "unit_of_measurement": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                "device_class": SensorDeviceClass.REACTIVE_POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3046", "3047"],
                "multiplier": 1,
            },
            {"type": "reserve", "register": ["3048"]},
            {
                "name": "Actual Limited Active Power",
                "unique": "solis_modbus_inverter_actual_limited_active_power",
                "unit_of_measurement": PERCENTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3049"],
                "write_register": 3051,
                "multiplier": 0.01,
                "editable": True,
                "min": 0,
                # Grid code: 110% allows the over-100% setpoint some codes require.
                "max": 110,
            },
            {
                "name": "Actual Adjusted Power Factor",
                "unique": "solis_modbus_inverter_actual_adjusted_power_factor",
                "unit_of_measurement": PERCENTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3050"],
                "multiplier": 0.01,
            },
            {
                # READ-ONLY on purpose: with editable=True and no write_register this
                # fell back to writing wire 3051 = doc-3052 POWER LIMITATION with a
                # 0.001 scale — "setting PF 1.0" capped the inverter at 10% output.
                # The PF *setting* is doc-3053 (wire 3052) and needs enable 3071=0xA1.
                "name": "Actual Power Factor Adjustment",
                "unique": "solis_modbus_inverter_actual_power_factor_adjustment",
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3051"],
                "multiplier": 0.001,
            },
        ],
    },
    {
        "register_start": 3089,
        "poll_speed": PollSpeed.SLOW,
        "entities": [
            {
                "name": "Power Limitation Switch (89)",
                "unique": "solis_modbus_power_limitation_switch",
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
                "register": ["3089"],
                "multiplier": 1,
            },
        ],
    },
    {
        "register_start": 3179,
        "poll_speed": PollSpeed.SLOW,
        "entities": [
            {
                "name": "Shading MPPT Scan Enable",
                "unique": "solis_modbus_shading_mppt_scan_enable",
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3179"],
                "multiplier": 0.1,
            },
            {
                "name": "Shading MPPT Scan Time Interval",
                "unique": "solis_modbus_shading_mppt_scan_interval",
                "unit_of_measurement": UnitOfTime.MINUTES,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3180"],
                "multiplier": 1,
                "editable": True,
                "min": 10,
                # Guess: 10-180 min shading-scan interval. Unsourced.
                "max": 180,
            },
        ],
    },
    {
        "register_start": 3250,
        "poll_speed": PollSpeed.FAST,
        "entities": [
            {
                "name": "Meter AC Voltage A",
                "unique": "solis_modbus_meter_ac_voltage_a",
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3250"],
                "multiplier": 0.1,
            },
            {
                "name": "Meter AC Current A",
                "unique": "solis_modbus_meter_ac_current_a",
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3251"],
                "multiplier": 0.01,
            },
            {
                "name": "Meter AC Voltage B",
                "unique": "solis_modbus_meter_ac_voltage_b",
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3252"],
                "multiplier": 0.1,
            },
            {
                "name": "Meter AC Current B",
                "unique": "solis_modbus_meter_ac_current_b",
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3253"],
                "multiplier": 0.01,
            },
            {
                "name": "Meter AC Voltage C",
                "unique": "solis_modbus_meter_ac_voltage_c",
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3254"],
                "multiplier": 0.1,
            },
            {
                "name": "Meter AC Current C",
                "unique": "solis_modbus_meter_ac_current_c",
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3255"],
                "multiplier": 0.01,
            },
            {
                "name": "Meter AC Active Power A",
                "unique": "solis_modbus_meter_ac_active_power_a",
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3256", "3257"],
                "multiplier": 0.001,
            },
            {
                "name": "Meter AC Active Power B",
                "unique": "solis_modbus_meter_ac_active_power_b",
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3258", "3259"],
                "multiplier": 0.001,
            },
            {
                "name": "Meter AC Active Power C",
                "unique": "solis_modbus_meter_ac_active_power_c",
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3260", "3261"],
                "multiplier": 0.001,
            },
            {
                "name": "Meter AC Active Power Total",
                "unique": "solis_modbus_meter_ac_active_power_total",
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3262", "3263"],
                "multiplier": 0.001,
            },
        ],
    },
    {
        # Direct-meter grid energy counters (issue #410, field-verified on S5-GR3P +
        # Acrel DTSD1352-C against the meter's own display). Protocol §5.3: doc regs
        # 3281-3286 → wire 3280-3285. These come from the attached meter itself, unlike
        # the 36050 block which only exists on EPM-equipped inverters (exception code 2
        # otherwise). On meter-less models this group auto-disables via exc-2 recovery.
        "register_start": 3280,
        "poll_speed": PollSpeed.SLOW,
        "entities": [
            {
                "name": "Meter Power Factor",
                "unique": "solis_modbus_meter_power_factor",
                "state_class": SensorStateClass.MEASUREMENT,
                "device_class": SensorDeviceClass.POWER_FACTOR,
                "register": ["3280"],
                "multiplier": 0.001,
                "data_type": DataType.S16,
            },
            {
                "name": "Meter Grid Frequency",
                "unique": "solis_modbus_meter_grid_frequency",
                "unit_of_measurement": UnitOfFrequency.HERTZ,
                "device_class": SensorDeviceClass.FREQUENCY,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3281"],
                "multiplier": 0.01,
            },
            {
                "name": "Meter Grid Import Total Energy",
                "unique": "solis_modbus_meter_grid_import_total_energy",
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "register": ["3282", "3283"],
                "multiplier": 0.01,
                "data_type": DataType.U32,
            },
            {
                "name": "Meter Grid Export Total Energy",
                "unique": "solis_modbus_meter_grid_export_total_energy",
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "register": ["3284", "3285"],
                "multiplier": 0.01,
                "data_type": DataType.U32,
            },
        ],
    },
    {
        "register_start": 36013,
        "feature_requirement": [InverterFeature.EPM],
        "essential": True,
        "scan_interval": 0,
        "entities": [
            {"name": "EPM Model No", "unique": "solis_modbus_inverter_epm_model_no", "register": ["36013"], "multiplier": 0},
            {
                "name": "Inverter EPM Firmware Version",
                "unique": "solis_modbus_inverter_epm_firmware_version",
                "register": ["36014"],
                "multiplier": 0,
            },
        ],
    },
    {
        "register_start": 36022,
        "feature_requirement": [InverterFeature.EPM],
        "scan_interval": 60,
        "entities": [
            {
                "name": "Clock (Hours)",
                "unique": "solis_modbus_inverter_clock_hours",
                "register": ["36022"],
                "multiplier": 0,
                "unit_of_measurement": UnitOfTime.HOURS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "name": "Clock (Minutes)",
                "unique": "solis_modbus_inverter_clock_minutes",
                "register": ["36023"],
                "multiplier": 0,
                "unit_of_measurement": UnitOfTime.MINUTES,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "name": "Clock (Seconds)",
                "unique": "solis_modbus_inverter_clock_seconds",
                "register": ["36024"],
                "multiplier": 0,
                "unit_of_measurement": UnitOfTime.SECONDS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
        ],
    },
    {
        "register_start": 36028,
        "feature_requirement": [InverterFeature.EPM],
        "essential": True,
        "poll_speed": PollSpeed.FAST,
        "entities": [
            {
                "name": "Total Load power",
                "unique": "solis_modbus_inverter_total_load_power",
                "register": ["36028", "36029"],
                "device_class": SensorDeviceClass.POWER,
                "multiplier": 100,
                "unit_of_measurement": UnitOfPower.WATT,
                "state_class": SensorStateClass.MEASUREMENT,
                "data_type": DataType.S32_LE,
            }
        ],
    },
    {
        "register_start": 36050,
        "feature_requirement": [InverterFeature.EPM],
        "essential": True,
        "poll_speed": PollSpeed.SLOW,
        "entities": [
            {
                "name": "Total Generation Energy",
                "unique": "solis_modbus_inverter_total_generation_energy",
                "register": ["36050", "36051"],
                "device_class": SensorDeviceClass.ENERGY,
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "data_type": DataType.U32_LE,
            },
            {
                "name": "Load Total Consumption Energy",
                "unique": "solis_modbus_inverter_load_total_consumption_energy",
                "register": ["36052", "36053"],
                "device_class": SensorDeviceClass.ENERGY,
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "data_type": DataType.U32_LE,
            },
            {
                "name": "Grid Import Total Active Energy",
                "unique": "solis_modbus_inverter_grid_import_total_active_energy",
                "register": ["36054", "36055"],
                "device_class": SensorDeviceClass.ENERGY,
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "data_type": DataType.U32_LE,
            },
            {
                "name": "Grid Export Total Active Energy",
                "unique": "solis_modbus_inverter_grid_export_total_active_energy",
                "register": ["36056", "36057"],
                "device_class": SensorDeviceClass.ENERGY,
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "data_type": DataType.U32_LE,
            },
        ],
    },
    {
        # The inverter's own export limit (Internal EPM soft limit), issue #569.
        # Read back on input 3110-3113, written to holding 3151. Confirmed on an
        # S5-GC30K: 3111 = 189 matched the 18900 W limit SolisCloud shows.
        # Kept last: a unit that times out here ends the poll batch, and nothing
        # after it should go unread because of that.
        "register_start": 3110,
        "poll_speed": PollSpeed.SLOW,
        "feature_requirement": [InverterFeature.INTERNAL_EPM],
        "entities": [
            {
                # Read-only: the codes mean different things per power class
                # (0.7-8K 1P, 5-25K, 25-110K), so one select would mislabel some.
                # For 25-110K: 1 meter in grid, 2 meter in load, 3 off, 4 24H consumption.
                "name": "Export Control Mode",
                "unique": "solis_modbus_inverter_export_control_mode",
                "register": ["3110"],
                "multiplier": 1,
            },
            {
                # S16, 1 = 100 W, positive = to grid. Ignored while the mode is off.
                # No declared max: a grid-side limit, so never the inverter rating (#438).
                "name": "Export Power Limit",
                "unique": "solis_modbus_inverter_export_power_limit",
                "unit_of_measurement": UnitOfPower.WATT,
                "device_class": SensorDeviceClass.POWER,
                "register": ["3111"],
                "write_register": 3151,
                "multiplier": 100,
                "data_type": DataType.S16,
                "editable": True,
                "min": 0,
                "step": 100,
            },
            # Failsafe bits; the matching setting is holding 3152.
            {"type": "reserve", "register": ["3112"]},
            {
                "name": "Export Control Live Export Power",
                "unique": "solis_modbus_inverter_export_control_live_power",
                "unit_of_measurement": UnitOfPower.WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "register": ["3113"],
                "multiplier": 10,
            },
        ],
    },
    # Last of the normal groups: these registers are unconfirmed on some MULTI_MPPT
    # models, and a read that times out drops the link for the groups after it.
    *multi_mppt_groups(),
]

string_sensors_derived = [
    {
        "name": "DC Power 1",
        "unique": "solis_modbus_dc_power_1",
        "mppt": 1,
        "device_class": SensorDeviceClass.POWER,
        "multiplier": 0.1,
        "unit_of_measurement": UnitOfPower.WATT,
        "state_class": SensorStateClass.MEASUREMENT,
        "register": ["3021", "3022"],
    },
    {
        "name": "DC Power 2",
        "unique": "solis_modbus_dc_power_2",
        "mppt": 2,
        "device_class": SensorDeviceClass.POWER,
        "multiplier": 0.1,
        "unit_of_measurement": UnitOfPower.WATT,
        "state_class": SensorStateClass.MEASUREMENT,
        "register": ["3023", "3024"],
    },
    {
        "name": "DC Power 3",
        "unique": "solis_modbus_dc_power_3",
        "mppt": 3,
        "device_class": SensorDeviceClass.POWER,
        "multiplier": 0.1,
        "unit_of_measurement": UnitOfPower.WATT,
        "state_class": SensorStateClass.MEASUREMENT,
        "register": ["3025", "3026"],
    },
    {
        "name": "DC Power 4",
        "unique": "solis_modbus_dc_power_4",
        "mppt": 4,
        "device_class": SensorDeviceClass.POWER,
        "multiplier": 0.1,
        "unit_of_measurement": UnitOfPower.WATT,
        "state_class": SensorStateClass.MEASUREMENT,
        "register": ["3027", "3028"],
    },
    *multi_mppt_derived(),
]
