import logging
from datetime import timedelta
from typing import List

from homeassistant.components.sensor import SensorEntity, RestoreSensor
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfFrequency, UnitOfTemperature, \
    UnitOfElectricPotential, UnitOfElectricCurrent, UnitOfPower, \
    UnitOfApparentPower, PERCENTAGE, UnitOfEnergy, POWER_VOLT_AMPERE_REACTIVE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, VERSION, POLL_INTERVAL_SECONDS, MANUFACTURER, MODEL
from custom_components.solis_modbus.status_mapping import STATUS_MAPPING

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Set up Modbus sensors from a config entry."""
    modbus_controller = hass.data[DOMAIN][CONTROLLER]
    sensor_entities: List[SensorEntity] = []
    sensor_derived_entities: List[SensorEntity] = []
    hass.data[DOMAIN]['values'] = {}

    sensors = [
        {
            "register_start": 33000,
            "scan_interval": 0,
            "entities": [
                {"type": "SS", "name": "Solis Model No", "unique": "solis_modbus_inverter_model_no",
                 "register": ['33000'], "multiplier": 0},
                {"type": "SS", "name": "Solis DSP Version", "unique": "solis_modbus_inverter_dsp_version",
                 "register": ['33001'], "multiplier": 0},
                {"type": "SS", "name": "Solis HMI Version", "unique": "solis_modbus_inverter_hmi_version",
                 "register": ['33002'], "multiplier": 0},
                {"type": "SS", "name": "Solis Protocol Version", "unique": "solis_modbus_inverter_protocol_version",
                 "register": ['33003'], "multiplier": 0},
                {"type": "SS", "name": "Solis Serial Number", "unique": "solis_modbus_inverter_serial_number",
                 "register": [
                     '33004', '33005', '33006', '33007', '33008', '33009', '33010', '33011', '33012', '33013', '33014',
                     '33015', '33016', '33017', '33018', '33019',
                 ], "multiplier": 0}
            ]
        },
        {
            "register_start": 33025,
            "scan_interval": 60,
            "entities": [

                {"type": "SS", "name": "Solis Clock (Hours)",
                 "unique": "solis_modbus_inverter_clock_hours",
                 "register": ['33025'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Clock (Minutes)",
                 "unique": "solis_modbus_inverter_clock_minutes",
                 "register": ['33026'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Clock (Seconds)",
                 "unique": "solis_modbus_inverter_clock_seconds",
                 "register": ['33027'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.SECONDS, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "reserve", "register": ['33028']},

                {"type": "SS", "name": "Solis PV Total Energy Generation",
                 "unique": "solis_modbus_inverter_pv_total_generation",
                 "register": ['33029', '33030'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis PV Current Month Energy Generation",
                 "unique": "solis_modbus_inverter_pv_current_month_generation",
                 "register": ['33031', '33032'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis PV Last Month Energy Generation",
                 "unique": "solis_modbus_inverter_pv_last_month_generation",
                 "register": ['33033', '33034'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis PV Today Energy Generation",
                 "unique": "solis_modbus_inverter_pv_today_generation",
                 "register": ['33035'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis PV Yesterday Energy Generation",
                 "unique": "solis_modbus_inverter_pv_yesterday_generation",
                 "register": ['33036'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis PV This Year Energy Generation",
                 "unique": "solis_modbus_inverter_pv_this_year_generation",
                 "register": ['33037', '33038'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis PV Last Year Energy Generation",
                 "unique": "solis_modbus_inverter_pv_last_year_generation",
                 "register": ['33039', '33040'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
            ]
        },
        {
            "register_start": 33049,
            "scan_interval": 5,
            "entities": [
                {"type": "SS", "name": "Solis PV Voltage 1",
                 "unique": "solis_modbus_inverter_dc_voltage_1",
                 "register": ['33049'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis PV Current 1",
                 "unique": "solis_modbus_inverter_dc_current_1",
                 "register": ['33050'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis PV Voltage 2 ",
                 "unique": "solis_modbus_inverter_dc_voltage_2",
                 "register": ['33051'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis PV Current 2",
                 "unique": "solis_modbus_inverter_dc_current_2",
                 "register": ['33052'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis PV Voltage 3",
                 "unique": "solis_modbus_inverter_dc_voltage_3",
                 "register": ['33053'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis PV Current 3",
                 "unique": "solis_modbus_inverter_dc_current_3",
                 "register": ['33054'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis PV Voltage 4",
                 "unique": "solis_modbus_inverter_dc_voltage_4",
                 "register": ['33055'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis PV Current 4",
                 "unique": "solis_modbus_inverter_dc_current_4",
                 "register": ['33056'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Total PV Power",
                 "unique": "solis_modbus_inverter_total_dc_output",
                 "register": ['33057', '33058'], "device_class": SensorDeviceClass.POWER, "multiplier": 0,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
            ]
        },
        {
            "register_start": 33072,
            "scan_interval": 5,
            "entities": [
                {"type": "SS", "name": "Solis PV Bus Half Voltage",
                 "unique": "solis_modbus_inverter_dc_bus_half_voltage",
                 "register": ['33072'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis A Phase Voltage",
                 "unique": "solis_modbus_inverter_a_phase_voltage",
                 "register": ['33073'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis B Phase Voltage",
                 "unique": "solis_modbus_inverter_b_phase_voltage",
                 "register": ['33074'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis C Phase Voltage",
                 "unique": "solis_modbus_inverter_c_phase_voltage",
                 "register": ['33075'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis A Phase Current",
                 "unique": "solis_modbus_inverter_a_phase_current",
                 "register": ['33076'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis B Phase Current",
                 "unique": "solis_modbus_inverter_b_phase_current",
                 "register": ['33077'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis C Phase Current",
                 "unique": "solis_modbus_inverter_c_phase_current",
                 "register": ['33078'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Active Power",
                 "unique": "solis_modbus_inverter_active_power",
                 "register": ['33079', '33080'], "device_class": SensorDeviceClass.POWER, "multiplier": 0.001,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Reactive Power",
                 "unique": "solis_modbus_inverter_reactive_power",
                 "register": ['33081', '33082'], "device_class": SensorDeviceClass.REACTIVE_POWER, "multiplier": 0,
                 "unit_of_measurement": POWER_VOLT_AMPERE_REACTIVE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Apparent Power",
                 "unique": "solis_modbus_inverter_apparent_power",
                 "register": ['33083', '33084'], "device_class": SensorDeviceClass.APPARENT_POWER, "multiplier": 0,
                 "unit_of_measurement": UnitOfApparentPower.VOLT_AMPERE, "state_class": SensorStateClass.MEASUREMENT}
            ]
        },
        {
            "register_start": 33093,
            "scan_interval": 5,
            "entities": [
                {"type": "SS", "name": "Solis Temperature", "unique": "solis_modbus_inverter_temperature",
                 "register": ['33093'], "device_class": SensorDeviceClass.TEMPERATURE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfTemperature.CELSIUS, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Grid Frequency", "unique": "solis_modbus_inverter_grid_frequency",
                 "register": ['33094'], "device_class": SensorDeviceClass.FREQUENCY, "multiplier": 0.01,
                 "unit_of_measurement": UnitOfFrequency.HERTZ, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Status", "unique": "solis_modbus_inverter_current_status",
                 "register": ['33095'], "multiplier": 0, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Lead-acid Battery Temperature", "unique": "solis_modbus_inverter_lead_acid_temp",
                 "register": ['33096'], "device_class": SensorDeviceClass.TEMPERATURE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfTemperature.CELSIUS, "state_class": SensorStateClass.MEASUREMENT},
            ]
        },
        {
            "register_start": 33132,
            "scan_interval": 5,
            "entities": [
                {"type": "SS", "name": "Solis Storage Control Switching Value",
                 "unique": "solis_modbus_inverter_storage_control_switching_value", "register": ['33132'],
                 "multiplier": 0, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Voltage",
                 "unique": "solis_modbus_inverter_battery_voltage", "register": ['33133'], "device_class": SensorDeviceClass.VOLTAGE,
                 "multiplier": 0.1, "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Current",
                 "unique": "solis_modbus_inverter_battery_current", "register": ['33134'], "device_class": SensorDeviceClass.CURRENT,
                 "multiplier": 0.1, "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Current Direction",
                 "unique": "solis_modbus_inverter_battery_current_direction",
                 "register": ['33135'],
                 "multiplier": 0,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis LLC Bus Voltage",
                 "unique": "solis_modbus_inverter_llc_bus_voltage",
                 "register": ['33136'], "device_class": SensorDeviceClass.VOLTAGE,
                 "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Backup AC Voltage Phase A",
                 "unique": "solis_modbus_inverter_backup_ac_voltage_phase_a",
                 "register": ['33137'], "device_class": SensorDeviceClass.VOLTAGE,
                 "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Backup AC Current Phase A",
                 "unique": "solis_modbus_inverter_backup_ac_current_phase_a",
                 "register": ['33138'], "device_class": SensorDeviceClass.CURRENT,
                 "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Battery SOC",
                 "unique": "solis_modbus_inverter_battery_soc",
                 "register": ['33139'], "device_class": SensorDeviceClass.BATTERY,
                 "multiplier": 0,
                 "unit_of_measurement": PERCENTAGE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery SOH",
                 "unique": "solis_modbus_inverter_battery_soh", "register": ['33140'], "multiplier": 0,
                 "unit_of_measurement": PERCENTAGE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Voltage (BMS)",
                 "unique": "solis_modbus_inverter_battery_voltage_bms",
                 "register": ['33141'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.01,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Current (BMS)",
                 "unique": "solis_modbus_inverter_battery_current_bms",
                 "register": ['33142'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Charge Current Limitation (BMS)",
                 "unique": "solis_modbus_inverter_battery_charge_current_limitation_bms",
                 "register": ['33143'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Discharge Current Limitation (BMS)",
                 "unique": "solis_modbus_inverter_battery_discharge_current_limitation_bms",
                 "register": ['33144'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Fault Status 1 (BMS)",
                 "unique": "solis_modbus_inverter_battery_fault_status_1_bms", "register": ['33145'], "multiplier": 0.1,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Fault Status 2 (BMS)",
                 "unique": "solis_modbus_inverter_battery_fault_status_2_bms", "register": ['33146'], "multiplier": 0.1,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Household load power",
                 "unique": "solis_modbus_inverter_household_load_power",
                 "register": ['33147'], "device_class": SensorDeviceClass.POWER, "multiplier": 0,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Backup Load power",
                 "unique": "solis_modbus_inverter_backup_load_power",
                 "register": ['33148'], "device_class": SensorDeviceClass.POWER, "multiplier": 0,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Power",
                 "unique": "solis_modbus_inverter_battery_power",
                 "register": ['33149', '33150'], "device_class": SensorDeviceClass.POWER, "multiplier": 0,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis AC Grid Port Power",
                 "unique": "solis_modbus_inverter_ac_grid_port_power",
                 "register": ['33151', '33152'], "device_class": SensorDeviceClass.POWER, "multiplier": 0,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
            ]
        },
        {
            "register_start": 33161,
            "scan_interval": 5,
            "entities": [
                {"type": "SS", "name": "Solis Total Battery Charge Energy",
                 "unique": "solis_modbus_inverter_total_battery_charge_energy",
                 "register": ['33161', '33162'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

                {"type": "SS", "name": "Solis Today Battery Charge Energy",
                 "unique": "solis_modbus_inverter_today_battery_charge_energy",
                 "register": ['33163'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Yesterday Battery Charge Energy",
                 "unique": "solis_modbus_inverter_yesterday_battery_charge_energy",
                 "register": ['33164'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Total Battery Discharge Energy",
                 "unique": "solis_modbus_inverter_total_battery_discharge_energy",
                 "register": ['33165', '33166'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

                {"type": "SS", "name": "Solis Today Battery Discharge Energy",
                 "unique": "solis_modbus_inverter_today_battery_discharge_energy",
                 "register": ['33167'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Yesterday Battery Discharge Energy",
                 "unique": "solis_modbus_inverter_yesterday_battery_discharge_energy",
                 "register": ['33168'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

                {"type": "SS", "name": "Solis Total Energy Imported From Grid",
                 "unique": "solis_modbus_inverter_total_energy_imported_from_grid",
                 "register": ['33169', '33170'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Today Energy Imported From Grid",
                 "unique": "solis_modbus_inverter_today_energy_imported_from_grid",
                 "register": ['33171'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Yesterday Energy Imported From Grid",
                 "unique": "solis_modbus_inverter_yesterday_energy_imported_from_grid",
                 "register": ['33172'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

                {"type": "SS", "name": "Solis Total Energy Fed Into Grid",
                 "unique": "solis_modbus_inverter_total_energy_fed_into_grid",
                 "register": ['33173', '33174'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Today Energy Fed Into Grid",
                 "unique": "solis_modbus_inverter_today_energy_fed_into_grid",
                 "register": ['33175'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Yesterday Energy Fed Into Grid",
                 "unique": "solis_modbus_inverter_yesterday_energy_fed_into_grid",
                 "register": ['33176'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},

                {"type": "SS", "name": "Solis Total Energy Consumption",
                 "unique": "solis_modbus_inverter_total_energy_consumption",
                 "register": ['33177', '33178'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Today Energy Consumption",
                 "unique": "solis_modbus_inverter_today_energy_consumption",
                 "register": ['33179'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Yesterday Energy Consumption",
                 "unique": "solis_modbus_inverter_yesterday_energy_consumption",
                 "register": ['33180'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
            ]
        },
        {
            "register_start": 33251,
            "scan_interval": 5,
            "entities": [
                {"type": "SS", "name": "Solis Meter AC Voltage A",
                 "unique": "solis_modbus_inverter_meter_ac_voltage_a",
                 "register": ['33251'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Meter AC Current A",
                 "unique": "solis_modbus_inverter_meter_ac_current_a",
                 "register": ['33252'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.01,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Meter AC Voltage B",
                 "unique": "solis_modbus_inverter_meter_ac_voltage_b",
                 "register": ['33253'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Meter AC Current B",
                 "unique": "solis_modbus_inverter_meter_ac_current_b",
                 "register": ['33254'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.01,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Meter AC Voltage C",
                 "unique": "solis_modbus_inverter_meter_ac_voltage_c",
                 "register": ['33255'], "device_class": SensorDeviceClass.VOLTAGE, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Meter AC Current C",
                 "unique": "solis_modbus_inverter_meter_ac_current_c",
                 "register": ['33256'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.01,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Meter Active Power A",
                 "unique": "solis_modbus_inverter_meter_active_power_a",
                 "register": ['33257', '33258'], "device_class": SensorDeviceClass.POWER, "multiplier": 0,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Meter Active Power B",
                 "unique": "solis_modbus_inverter_meter_active_power_b",
                 "register": ['33259', '33260'], "device_class": SensorDeviceClass.POWER, "multiplier": 0,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Meter Active Power C",
                 "unique": "solis_modbus_inverter_meter_active_power_c",
                 "register": ['33261', '33262'], "device_class": SensorDeviceClass.POWER, "multiplier": 0,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Meter Total Active Power",
                 "unique": "solis_modbus_inverter_meter_total_active_power",
                 "register": ['33263', '33264'], "device_class": SensorDeviceClass.POWER, "multiplier": 0,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT}
            ]
        },
        {
            "register_start": 33580,
            "scan_interval": 60,
            "entities": [
                {"type": "SS", "name": "Solis Household Load Total Energy",
                 "unique": "solis_modbus_inverter_household_total_energy",
                 "register": ['33580', '33581'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Household Load Year Energy",
                 "unique": "solis_modbus_inverter_household_year_energy",
                 "register": ['33582', '33583'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Household Load Month Energy",
                 "unique": "solis_modbus_inverter_household_month_energy",
                 "register": ['33584', '33585'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Household Load Today Energy",
                 "unique": "solis_modbus_inverter_household_today_energy",
                 "register": ['33586'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "reserve", "register": ['33587', '33588', '33589']},

                {"type": "SS", "name": "Solis Backup Load Total Energy",
                 "unique": "solis_modbus_inverter_backup_total_energy",
                 "register": ['33590', '33591'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Backup Load Year Energy",
                 "unique": "solis_modbus_inverter_backup_year_energy",
                 "register": ['33592', '33593'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Backup Load Month Energy",
                 "unique": "solis_modbus_inverter_backup_month_energy",
                 "register": ['33594', '33595'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Backup Load Today Energy",
                 "unique": "solis_modbus_inverter_backup_today_energy",
                 "register": ['33596'], "device_class": SensorDeviceClass.ENERGY, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "state_class": SensorStateClass.TOTAL_INCREASING},
            ]
        },
        {
            "register_start": 43011,
            "scan_interval": 10,
            "entities": [

                {"type": "SS", "name": "Solis Overcharge SOC",
                 "unique": "solis_modbus_inverter_overcharge_soc", "register": ['43010'], "multiplier": 0,
                 "unit_of_measurement": PERCENTAGE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Overdischarge SOC",
                 "unique": "solis_modbus_inverter_overdischarge_soc", "register": ['43011'], "multiplier": 0,
                 "unit_of_measurement": PERCENTAGE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "reserve", "register": ['43012', '43013', '43014', '43015', '43016', '43017']},

                {"type": "SS", "name": "Solis Force Charge SOC",
                 "unique": "solis_modbus_inverter_force_charge_soc", "register": ['43018'], "multiplier": 0,
                 "unit_of_measurement": PERCENTAGE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "reserve", "register": ['43019', '43020', '43021', '43022', '43023']},

                {"type": "SS", "name": "Solis Backup SOC",
                 "unique": "solis_modbus_inverter_backup_soc", "register": ['43024'], "multiplier": 0,
                 "unit_of_measurement": PERCENTAGE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "reserve", "register": ['43025', '43026']},
                {"type": "SS", "name": "Solis Battery Force-charge Power Limitation",
                 "unique": "solis_modbus_inverter_battery_force_charge_limit",
                 "register": ['43027'], "device_class": SensorDeviceClass.POWER, "multiplier": 0, "display_multiplier": 10,
                 "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Battery Force Charge Source",
                 "unique": "solis_modbus_inverter_battery_force_charge_source", "register": ['43028'], "multiplier": 0,
                 "state_class": SensorStateClass.MEASUREMENT}
            ]
        },
        {
            "register_start": 43141,
            "scan_interval": 10,
            "entities": [
                {"type": "SS", "name": "Solis Time-Charging Charge Current",
                 "unique": "solis_modbus_inverter_time_charging_charge_current",
                 "register": ['43141'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Discharge Current",
                 "unique": "solis_modbus_inverter_time_charging_discharge_current",
                 "register": ['43142'], "device_class": SensorDeviceClass.CURRENT, "multiplier": 0.1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Time-Charging Charge Start Hour (Slot 1)",
                 "unique": "solis_modbus_inverter_time_charging_start_hour_slot1",
                 "register": ['43143'], "multiplier": 0, "unit_of_measurement": UnitOfTime.HOURS,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Charge Start Minute (Slot 1)",
                 "unique": "solis_modbus_inverter_time_charging_start_minute_slot1",
                 "register": ['43144'], "multiplier": 0, "unit_of_measurement": UnitOfTime.MINUTES,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Charge End Hour (Slot 1)",
                 "unique": "solis_modbus_inverter_time_charging_end_hour_slot1",
                 "register": ['43145'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Charge End Minute (Slot 1)",
                 "unique": "solis_modbus_inverter_time_charging_end_minute_slot1",
                 "register": ['43146'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Time-Charging Discharge Start Hour (Slot 1)",
                 "unique": "solis_modbus_inverter_time_discharge_start_hour_slot1", "register": ['43147'],
                 "multiplier": 0, "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Discharge Start Minute (Slot 1)",
                 "unique": "solis_modbus_inverter_time_discharge_start_minute_slot1", "register": ['43148'],
                 "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Discharge End Hour (Slot 1)",
                 "unique": "solis_modbus_inverter_time_discharge_end_hour_slot1", "register": ['43149'],
                 "multiplier": 0, "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Discharge End Minute (Slot 1)",
                 "unique": "solis_modbus_inverter_time_discharge_end_minute_slot1", "register": ['43150'],
                 "multiplier": 0, "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "reserve", "register": ['43051', '43052', '43052']},

                {"type": "SS", "name": "Solis Time-Charging Charge Start Hour (Slot 2)",
                 "unique": "solis_modbus_inverter_time_charging_start_hour_slot2", "register": ['43153'],
                 "multiplier": 0, "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Charge Start Minute (Slot 2)",
                 "unique": "solis_modbus_inverter_time_charging_start_minute_slot2", "register": ['43154'],
                 "multiplier": 0, "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Charge End Hour (Slot 2)",
                 "unique": "solis_modbus_inverter_time_charging_end_hour_slot2", "register": ['43155'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Charge End Minute (Slot 2)",
                 "unique": "solis_modbus_inverter_time_charging_end_minute_slot2",
                 "register": ['43156'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Time-Charging Discharge Start Hour (Slot 2)",
                 "unique": "solis_modbus_inverter_time_discharge_start_hour_slot2",
                 "register": ['43157'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Discharge Start Minute (Slot 2)",
                 "unique": "solis_modbus_inverter_time_discharge_start_minute_slot2",
                 "register": ['43158'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Discharge End Hour (Slot 2)",
                 "unique": "solis_modbus_inverter_time_discharge_end_hour_slot2",
                 "register": ['43159'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Discharge End Minute (Slot 2)",
                 "unique": "solis_modbus_inverter_time_discharge_end_minute_slot2",
                 "register": ['43160'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "reserve", "register": ['43061', '43062', '43062']},

                {"type": "SS", "name": "Solis Time-Charging Charge Start Hour (Slot 3)",
                 "unique": "solis_modbus_inverter_time_charging_start_hour_slot3",
                 "register": ['43163'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Charge Start Minute (Slot 3)",
                 "unique": "solis_modbus_inverter_time_charging_start_minute_slot3",
                 "register": ['43164'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Charge End Hour (Slot 3)",
                 "unique": "solis_modbus_inverter_time_charging_end_hour_slot3",
                 "register": ['43165'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Charge End Minute (Slot 3)",
                 "unique": "solis_modbus_inverter_time_charging_end_minute_slot3",
                 "register": ['43166'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Time-Charging Discharge Start Hour (Slot 3)",
                 "unique": "solis_modbus_inverter_time_discharge_start_hour_slot3",
                 "register": ['43167'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Discharge Start Minute (Slot 3)",
                 "unique": "solis_modbus_inverter_time_discharge_start_minute_slot3",
                 "register": ['43168'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Discharge End Hour (Slot 3)",
                 "unique": "solis_modbus_inverter_time_discharge_end_hour_slot3",
                 "register": ['43169'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.HOURS, "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Time-Charging Discharge End Minute (Slot 3)",
                 "unique": "solis_modbus_inverter_time_discharge_end_minute_slot3",
                 "register": ['43170'], "multiplier": 0,
                 "unit_of_measurement": UnitOfTime.MINUTES, "state_class": SensorStateClass.MEASUREMENT},
            ]
        },
    ]

    sensors_derived = [
        {"type": "SDS", "name": "Solis Status String",
         "unique": "solis_modbus_inverter_current_status_string", "multiplier": 0,
         "register": ['33095']},

        {"type": "SDS", "name": "Solis PV Power 1",
         "unique": "solis_modbus_inverter_dc_power_1", "device_class": SensorDeviceClass.POWER, "multiplier": 0.1,
         "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT,
         "register": ['33049', '33050']},

        {"type": "SDS", "name": "Solis PV Power 2",
         "unique": "solis_modbus_inverter_dc_power_2", "device_class": SensorDeviceClass.POWER, "multiplier": 0.1,
         "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT,
         "register": ['33051', '33052']},

        {"type": "SDS", "name": "Solis Battery Charge Power",
         "unique": "solis_modbus_inverter_battery_charge_power", "device_class": SensorDeviceClass.POWER,
         "multiplier": 0.1,
         "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT,
         "register": ['33149', '33150', '33135', '0']},
        {"type": "SDS", "name": "Solis Battery Discharge Power",
         "unique": "solis_modbus_inverter_battery_discharge_power", "device_class": SensorDeviceClass.POWER,
         "multiplier": 0.1,
         "unit_of_measurement": UnitOfPower.WATT, "state_class": SensorStateClass.MEASUREMENT,
         "register": ['33149', '33150', '33135', '1']}
    ]

    for sensor_group in sensors:
        for entity_definition in sensor_group['entities']:
            for register in entity_definition['register']:
                hass.data[DOMAIN]['values'][register] = 0
            type = entity_definition["type"]
            if type == 'SS':
                sensor_entities.append(SolisSensor(hass, modbus_controller, entity_definition))

    for sensor_group in sensors_derived:
        type = sensor_group["type"]
        if type == 'SDS':
            sensor_derived_entities.append(SolisDerivedSensor(hass, sensor_group))

    hass.data[DOMAIN]['sensor_entities'] = sensor_entities
    hass.data[DOMAIN]['sensor_derived_entities'] = sensor_derived_entities
    async_add_entities(sensor_entities, True)
    async_add_entities(sensor_derived_entities, True)

    @callback
    def async_update(now):
        """Update Modbus data periodically."""
        controller = hass.data[DOMAIN][CONTROLLER]

        if not controller.connected():
            controller.connect()

        for sensor_group in sensors:
            start_register = sensor_group['register_start']

            count = sum(len(entity.get('register', [])) for entity in sensor_group.get('entities', []))

            if start_register >= 40000:
                values = controller.read_holding_register(start_register, count)
            else:
                values = controller.read_input_register(start_register, count)

            # Store each value with a unique key
            for i, value in enumerate(values):
                register_key = f"{start_register + i}"
                hass.data[DOMAIN]['values'][register_key] = value
                _LOGGER.debug(f'register_key = {register_key}, value = {value}')

        for entity in hass.data[DOMAIN]["sensor_entities"]:
            entity.update()
        for entity in hass.data[DOMAIN]["sensor_derived_entities"]:
            entity.update()

    async_track_time_interval(hass, async_update, timedelta(seconds=POLL_INTERVAL_SECONDS))
    return True


def get_value(self):
    if len(self._register) >= 15:
        values = [self._hass.data[DOMAIN]['values'][reg] for reg in self._register]
        n_value = extract_serial_number(values)
    elif len(self._register) > 1:
        s32_values = [self._hass.data[DOMAIN]['values'][reg] for reg in self._register]
        # These are two 16-bit values representing a 32-bit signed integer (S32)
        high_word = s32_values[0] - (1 << 16) if s32_values[0] & (1 << 15) else s32_values[0]
        low_word = s32_values[1] - (1 << 16) if s32_values[1] & (1 << 15) else s32_values[1]

        # Combine the high and low words to form a 32-bit signed integer
        combined_value = (high_word << 16) | (low_word & 0xFFFF)
        if self._multiplier == 0:
            n_value = round(combined_value)
        else:
            n_value = combined_value * self._multiplier
    else:
        # Treat it as a single register (U16)
        if self._multiplier == 0:
            n_value = round(self._hass.data[DOMAIN]['values'][self._register[0]])
        else:
            n_value = self._hass.data[DOMAIN]['values'][self._register[0]] * self._multiplier

    return n_value


def hex_to_ascii(hex_value):
    # Convert hexadecimal to decimal
    decimal_value = hex_value

    # Split into bytes
    byte1 = (decimal_value >> 8) & 0xFF
    byte2 = decimal_value & 0xFF

    # Convert bytes to ASCII characters
    ascii_chars = ''.join([chr(byte) for byte in [byte1, byte2]])

    return ascii_chars


def extract_serial_number(values):
    return ''.join([hex_to_ascii(hex_value) for hex_value in values])


class SolisDerivedSensor(RestoreSensor, SensorEntity):
    """Representation of a Modbus derived/calculated sensor."""

    def __init__(self, hass, entity_definition):
        self._hass = hass
        self._attr_name = entity_definition["name"]
        self._attr_unique_id = "{}_{}".format(DOMAIN, entity_definition["unique"])

        self._device_class = SwitchDeviceClass.SWITCH

        self._register: List[int] = entity_definition["register"]
        self._state = None
        self._unit_of_measurement = entity_definition.get("unit_of_measurement", None)
        self._device_class = entity_definition.get("device_class", None)

        # Visible Instance Attributes Outside Class
        self.is_added_to_hass = False

        # Hidden Inherited Instance Attributes
        self._attr_available = False
        self._attr_device_class = entity_definition.get("device_class", None)
        self._attr_state_class = entity_definition.get("state_class", None)
        self._attr_native_unit_of_measurement = entity_definition.get("unit_of_measurement", None)
        self._attr_should_poll = False

        # Hidden Class Extended Instance Attributes
        self._device_attribute = entity_definition.get("attribute", None)
        self._multiplier = entity_definition.get("multiplier", 1)
        self._display_multiplier = entity_definition.get("display_multiplier", 1)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value
        self.is_added_to_hass = True

    def update(self):
        """Update the sensor value."""
        try:
            if not self.is_added_to_hass:
                return

            n_value = None
            if '33095' in self._register:
                n_value = round(get_value(self))
                n_value = STATUS_MAPPING.get(n_value, "Unknown")
            if '33049' in self._register or '33051' in self._register:
                r1_value = self._hass.data[DOMAIN]['values'][self._register[0]] * self._multiplier
                r2_value = self._hass.data[DOMAIN]['values'][self._register[1]] * self._multiplier
                n_value = round(r1_value * r2_value)
            if '33135' in self._register and len(self._register) == 4:
                registers = self._register.copy()
                self._register = registers[:2]

                p_value = get_value(self)
                d_w_value = registers[3]
                d_value = self._hass.data[DOMAIN]['values'][registers[2]]

                self._register = registers

                if str(d_value) == str(d_w_value):
                    n_value = round(p_value * 10)
                else:
                    n_value = 0

            self._attr_available = True
            self._attr_native_value = n_value * self._display_multiplier
            self._state = n_value * self._display_multiplier
            self.async_write_ha_state()

        except ValueError as e:
            _LOGGER.error(e)
            self._state = None
            self._attr_available = False

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._hass.data[DOMAIN][CONTROLLER].host)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"{MANUFACTURER} {MODEL}",
            sw_version=VERSION,
        )


class SolisSensor(RestoreSensor, SensorEntity):
    """Representation of a Modbus sensor."""

    def __init__(self, hass, modbus_controller, entity_definition):
        self._hass = hass
        self._modbus_controller = modbus_controller

        self._attr_name = entity_definition["name"]
        self._attr_unique_id = "{}_{}_{}".format(DOMAIN, self._modbus_controller.host, entity_definition["unique"])

        self._register: List[int] = entity_definition["register"]
        self._state = None
        self._unit_of_measurement = entity_definition.get("unit_of_measurement", None)
        self._device_class = entity_definition.get("device_class", None)

        # Visible Instance Attributes Outside Class
        self.is_added_to_hass = False

        # Hidden Inherited Instance Attributes
        self._attr_available = False
        self._attr_device_class = entity_definition.get("device_class", None)
        self._attr_state_class = entity_definition.get("state_class", None)
        self._attr_native_unit_of_measurement = entity_definition.get("unit_of_measurement", None)
        self._attr_should_poll = False

        # Hidden Class Extended Instance Attributes
        self._device_attribute = entity_definition.get("attribute", None)
        self._multiplier = entity_definition.get("multiplier", 1)
        self._display_multiplier = entity_definition.get("display_multiplier", 1)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value * self._display_multiplier
        self.is_added_to_hass = True

    def update(self):
        """Update the sensor value."""
        try:
            if not self.is_added_to_hass:
                return

            if len(self._register) == 1 and self._register[0] in ('33001', '33002', '33003'):
                n_value = hex(round(get_value(self)))[2:]
            else:
                n_value = get_value(self)

            self._attr_available = True
            self._attr_native_value = n_value * self._display_multiplier
            self._state = n_value * self._display_multiplier
            self.async_write_ha_state()
        except ValueError as e:
            _LOGGER.error(e)
            # Handle communication or reading errors
            self._state = None
            self._attr_available = False

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._modbus_controller.host)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"{MANUFACTURER} {MODEL}",
            sw_version=VERSION,
        )
