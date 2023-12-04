import logging
from datetime import timedelta
from typing import List

from homeassistant.components.sensor import SensorEntity, RestoreSensor
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfFrequency, UnitOfTemperature, \
    UnitOfElectricPotential, UnitOfElectricCurrent, UnitOfPower, \
    UnitOfApparentPower, PERCENTAGE, UnitOfEnergy, POWER_VOLT_AMPERE_REACTIVE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus import DOMAIN, CONTROLLER
from custom_components.solis_modbus.const import VERSION, POLL_INTERVAL_SECONDS
from custom_components.solis_modbus.status_mapping import STATUS_MAPPING

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Set up Modbus sensors from a config entry."""
    modbus_controller = hass.data[DOMAIN][CONTROLLER]
    sensorEntities: List[SensorEntity] = []
    sensorDerivedEntities: List[SensorEntity] = []
    hass.data[DOMAIN]['values'] = {}

    sensors = [
        {
            "register_start": 33049,
            "entities": [
                {"type": "SS", "name": "Solis Inverter DC Voltage 1",
                 "unique": "solis_modbus_inverter_dc_voltage_1",
                 "register": ['33049'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter DC Current 1",
                 "unique": "solis_modbus_inverter_dc_current_1",
                 "register": ['33050'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter DC Voltage 2 ",
                 "unique": "solis_modbus_inverter_dc_voltage_2",
                 "register": ['33051'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter DC Current 2",
                 "unique": "solis_modbus_inverter_dc_current_2",
                 "register": ['33052'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter DC Voltage 3",
                 "unique": "solis_modbus_inverter_dc_voltage_3",
                 "register": ['33053'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter DC Current 3",
                 "unique": "solis_modbus_inverter_dc_current_3",
                 "register": ['33054'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter DC Voltage 4",
                 "unique": "solis_modbus_inverter_dc_voltage_4",
                 "register": ['33055'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter DC Current 4",
                 "unique": "solis_modbus_inverter_dc_current_4",
                 "register": ['33056'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter Total DC Output",
                 "unique": "solis_modbus_inverter_total_dc_output",
                 "register": ['33057', '33058'], "device_class": SensorDeviceClass.POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfPower.WATT,
                 "state_class": SensorStateClass.MEASUREMENT},
            ]
        },
        {
            "register_start": 33072,
            "entities": [
                {"type": "SS", "name": "Solis Inverter DC Bus Half Voltage",
                 "unique": "solis_modbus_inverter_dc_bus_half_voltage",
                 "register": ['33072'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter A Phase Voltage",
                 "unique": "solis_modbus_inverter_a_phase_voltage",
                 "register": ['33073'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter B Phase Voltage",
                 "unique": "solis_modbus_inverter_b_phase_voltage",
                 "register": ['33074'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter C Phase Voltage",
                 "unique": "solis_modbus_inverter_c_phase_voltage",
                 "register": ['33075'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter A Phase Current",
                 "unique": "solis_modbus_inverter_a_phase_current",
                 "register": ['33076'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter B Phase Current",
                 "unique": "solis_modbus_inverter_b_phase_current",
                 "register": ['33077'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter C Phase Current",
                 "unique": "solis_modbus_inverter_c_phase_current",
                 "register": ['33078'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter Active Power",
                 "unique": "solis_modbus_inverter_active_power",
                 "register": ['33079', '33080'], "device_class": SensorDeviceClass.POWER,
                 "decimal_places": 3,
                 "unit_of_measurement": UnitOfPower.WATT,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter Reactive Power",
                 "unique": "solis_modbus_inverter_reactive_power",
                 "register": ['33081', '33082'], "device_class": SensorDeviceClass.REACTIVE_POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": POWER_VOLT_AMPERE_REACTIVE,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter Apparent Power",
                 "unique": "solis_modbus_inverter_apparent_power",
                 "register": ['33083', '33084'], "device_class": SensorDeviceClass.APPARENT_POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfApparentPower.VOLT_AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT}
            ]
        },
        {
            "register_start": 33093,
            "entities": [
                {"type": "SS", "name": "Solis Inverter Temperature",
                 "unique": "solis_modbus_inverter_temperature",
                 "register": ['33093'], "device_class": SensorDeviceClass.TEMPERATURE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfTemperature.CELSIUS,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter Grid Frequency",
                 "unique": "solis_modbus_inverter_grid_frequency",
                 "register": ['33094'], "device_class": SensorDeviceClass.FREQUENCY,
                 "decimal_places": 2,
                 "unit_of_measurement": UnitOfFrequency.HERTZ,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter Current Status",
                 "unique": "solis_modbus_inverter_current_status",
                 "register": ['33095'],
                 "decimal_places": 0,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Lead-acid Battery Temperature",
                 "unique": "solis_modbus_inverter_lead_acid_temp",
                 "register": ['33096'], "device_class": SensorDeviceClass.TEMPERATURE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfTemperature.CELSIUS,
                 "state_class": SensorStateClass.MEASUREMENT},
            ]
        },
        {
            "register_start": 33132,
            "entities": [
                {"type": "SS", "name": "Solis Inverter Storage Control Switching Value",
                 "unique": "solis_modbus_inverter_storage_control_switching_value",
                 "register": ['33132'],
                 "decimal_places": 0,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery Voltage",
                 "unique": "solis_modbus_inverter_battery_voltage",
                 "register": ['33133'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery Current",
                 "unique": "solis_modbus_inverter_battery_current",
                 "register": ['33134'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery Current Direction",
                 "unique": "solis_modbus_inverter_battery_current_direction",
                 "register": ['33135'],
                 "decimal_places": 0,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter LLC Bus Voltage",
                 "unique": "solis_modbus_inverter_llc_bus_voltage",
                 "register": ['33136'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Backup AC Voltage Phase A",
                 "unique": "solis_modbus_inverter_backup_ac_voltage_phase_a",
                 "register": ['33137'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Backup AC Current Phase A",
                 "unique": "solis_modbus_inverter_backup_ac_current_phase_a",
                 "register": ['33138'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter Battery SOC",
                 "unique": "solis_modbus_inverter_battery_soc",
                 "register": ['33139'], "device_class": SensorDeviceClass.BATTERY,
                 "decimal_places": 0,
                 "unit_of_measurement": PERCENTAGE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery SOH",
                 "unique": "solis_modbus_inverter_battery_soh",
                 "register": ['33140'],
                 "decimal_places": 0,
                 "unit_of_measurement": PERCENTAGE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery Voltage (BMS)",
                 "unique": "solis_modbus_inverter_battery_voltage_bms",
                 "register": ['33141'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery Current (BMS)",
                 "unique": "solis_modbus_inverter_battery_current_bms",
                 "register": ['33142'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery Charge Current Limitation (BMS)",
                 "unique": "solis_modbus_inverter_battery_charge_current_limitation_bms",
                 "register": ['33143'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery Discharge Current Limitation (BMS)",
                 "unique": "solis_modbus_inverter_battery_discharge_current_limitation_bms",
                 "register": ['33144'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery Fault Status 1 (BMS)",
                 "unique": "solis_modbus_inverter_battery_fault_status_1_bms",
                 "register": ['33145'],
                 "decimal_places": 1,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery Fault Status 2 (BMS)",
                 "unique": "solis_modbus_inverter_battery_fault_status_2_bms",
                 "register": ['33146'],
                 "decimal_places": 1,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Household load power",
                 "unique": "solis_modbus_inverter_household_load_power",
                 "register": ['33147'], "device_class": SensorDeviceClass.POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfPower.WATT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Backup load power",
                 "unique": "solis_modbus_inverter_backup_load_power",
                 "register": ['33148'], "device_class": SensorDeviceClass.POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfPower.WATT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Battery Power",
                 "unique": "solis_modbus_inverter_battery_power",
                 "register": ['33149', '33150'], "device_class": SensorDeviceClass.POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfPower.WATT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter AC Grid Port Power",
                 "unique": "solis_modbus_inverter_ac_grid_port_power",
                 "register": ['33151', '33152'], "device_class": SensorDeviceClass.POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfPower.WATT,
                 "state_class": SensorStateClass.MEASUREMENT},
            ]
        },
        {
            "register_start": 33163,
            "entities": [
                {"type": "SS", "name": "Solis Inverter Today Battery Charge Energy",
                 "unique": "solis_modbus_inverter_today_battery_charge_energy",
                 "register": ['33163'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Inverter Yesterday Battery Charge Energy",
                 "unique": "solis_modbus_inverter_yesterday_battery_charge_energy",
                 "register": ['33164'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Inverter Total Battery Discharge Energy",
                 "unique": "solis_modbus_inverter_total_battery_discharge_energy",
                 "register": ['33165', '33166'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},

                {"type": "SS", "name": "Solis Inverter Today Battery Discharge Energy",
                 "unique": "solis_modbus_inverter_today_battery_discharge_energy",
                 "register": ['33167'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Inverter Yesterday Battery Discharge Energy",
                 "unique": "solis_modbus_inverter_yesterday_battery_discharge_energy",
                 "register": ['33168'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},

                {"type": "SS", "name": "Solis Inverter Total Energy Imported From Grid",
                 "unique": "solis_modbus_inverter_total_energy_imported_from_grid",
                 "register": ['33169', '33170'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Inverter Today Energy Imported From Grid",
                 "unique": "solis_modbus_inverter_today_energy_imported_from_grid",
                 "register": ['33171'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Inverter Yesterday Energy Imported From Grid",
                 "unique": "solis_modbus_inverter_yesterday_energy_imported_from_grid",
                 "register": ['33172'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},

                {"type": "SS", "name": "Solis Inverter Total Energy Fed Into Grid",
                 "unique": "solis_modbus_inverter_total_energy_fed_into_grid",
                 "register": ['33173', '33174'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Inverter Today Energy Fed Into Grid",
                 "unique": "solis_modbus_inverter_today_energy_fed_into_grid",
                 "register": ['33175'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Inverter Yesterday Energy Fed Into Grid",
                 "unique": "solis_modbus_inverter_yesterday_energy_fed_into_grid",
                 "register": ['33176'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},

                {"type": "SS", "name": "Solis Inverter Total Energy Consumption",
                 "unique": "solis_modbus_inverter_total_energy_consumption",
                 "register": ['33177', '33178'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Inverter Today Energy Consumption",
                 "unique": "solis_modbus_inverter_today_energy_consumption",
                 "register": ['33179'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},
                {"type": "SS", "name": "Solis Inverter Yesterday Energy Consumption",
                 "unique": "solis_modbus_inverter_yesterday_energy_consumption",
                 "register": ['33180'], "device_class": SensorDeviceClass.ENERGY,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                 "state_class": SensorStateClass.TOTAL_INCREASING},
            ]
        },
        {
            "register_start": 33251,
            "entities": [
                {"type": "SS", "name": "Solis Inverter Meter AC Voltage A",
                 "unique": "solis_modbus_inverter_meter_ac_voltage_a",
                 "register": ['33251'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Meter AC Current A",
                 "unique": "solis_modbus_inverter_meter_ac_current_a",
                 "register": ['33252'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 2,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Meter AC Voltage B",
                 "unique": "solis_modbus_inverter_meter_ac_voltage_b",
                 "register": ['33253'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Meter AC Current B",
                 "unique": "solis_modbus_inverter_meter_ac_current_b",
                 "register": ['33254'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 2,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Meter AC Voltage C",
                 "unique": "solis_modbus_inverter_meter_ac_voltage_c",
                 "register": ['33255'], "device_class": SensorDeviceClass.VOLTAGE,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricPotential.VOLT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Meter AC Current C",
                 "unique": "solis_modbus_inverter_meter_ac_current_c",
                 "register": ['33256'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 2,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},

                {"type": "SS", "name": "Solis Inverter Meter Active Power A",
                 "unique": "solis_modbus_inverter_meter_active_power_a",
                 "register": ['33257', '33258'], "device_class": SensorDeviceClass.POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfPower.WATT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Meter Active Power B",
                 "unique": "solis_modbus_inverter_meter_active_power_b",
                 "register": ['33259', '33260'], "device_class": SensorDeviceClass.POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfPower.WATT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Meter Active Power C",
                 "unique": "solis_modbus_inverter_meter_active_power_c",
                 "register": ['33261', '33262'], "device_class": SensorDeviceClass.POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfPower.WATT,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Meter Total Active Power",
                 "unique": "solis_modbus_inverter_meter_total_active_power",
                 "register": ['33263', '33264'], "device_class": SensorDeviceClass.POWER,
                 "decimal_places": 0,
                 "unit_of_measurement": UnitOfPower.WATT,
                 "state_class": SensorStateClass.MEASUREMENT}
            ]
        },
        {
            "register_start": 43024,
            "entities": [
                {"type": "SS", "name": "Solis Inverter Backup SOC",
                 "unique": "solis_modbus_inverter_backup_soc",
                 "register": ['43024'],
                 "decimal_places": 0,
                 "unit_of_measurement": PERCENTAGE,
                 "state_class": SensorStateClass.MEASUREMENT}
            ]
        },
        # {
        #     "register_start": 43110,
        #     "entities": [
        #         {"type": "SS", "name": "Solis Inverter Storage Control Switch Value",
        #          "unique": "solis_modbus_inverter_storage_control_switch_value",
        #          "register": ['43110'],
        #          "decimal_places": 0,
        #          "state_class": SensorStateClass.MEASUREMENT}
        #     ]
        # },
        {
            "register_start": 43141,
            "entities": [
                {"type": "SS", "name": "Solis Inverter Time-Charging Charge Current",
                 "unique": "solis_modbus_inverter_time_charging_charge_current",
                 "register": ['43141'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},
                {"type": "SS", "name": "Solis Inverter Time-Charging Discharge Current",
                 "unique": "solis_modbus_inverter_time_charging_discharge_current",
                 "register": ['43142'], "device_class": SensorDeviceClass.CURRENT,
                 "decimal_places": 1,
                 "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                 "state_class": SensorStateClass.MEASUREMENT},
            ]
        }
    ]
    sensorsDerived = [
        {"type": "SDS", "name": "Solis Inverter Current Status String",
         "unique": "solis_modbus_inverter_current_status_string", "decimal_places": 0,
         "register": ['33095']},

        {"type": "SDS", "name": "Solis Inverter DC Power 1",
         "unique": "solis_modbus_inverter_dc_power_1", "device_class": SensorDeviceClass.POWER,
         "decimal_places": 1,
         "unit_of_measurement": UnitOfPower.WATT,
         "state_class": SensorStateClass.MEASUREMENT,
         "register": ['33049', '33050']},

        {"type": "SDS", "name": "Solis Inverter DC Power 2",
         "unique": "solis_modbus_inverter_dc_power_2", "device_class": SensorDeviceClass.POWER,
         "decimal_places": 1,
         "unit_of_measurement": UnitOfPower.WATT,
         "state_class": SensorStateClass.MEASUREMENT,
         "register": ['33051', '33052']},
        # {
        #  "type": "SDS", "name": "Solis Inverter Current Status String",
        #  "unique": "solis_modbus_inverter_current_status_string", "decimal_places": 0,
        #  "register": ['43110']
        #  }
    ]

    for sensor_group in sensors:
        for entity_definition in sensor_group['entities']:
            for register in entity_definition['register']:
                hass.data[DOMAIN]['values'][register] = 0
            type = entity_definition["type"]
            if type == 'SS':
                sensorEntities.append(SolisSensor(hass, modbus_controller, entity_definition))

    for sensor_group in sensorsDerived:
        type = sensor_group["type"]
        if type == 'SDS':
            sensorDerivedEntities.append(SolisDerivedSensor(hass, sensor_group))

    hass.data[DOMAIN]['sensor_entities'] = sensorEntities
    hass.data[DOMAIN]['sensor_derived_entities'] = sensorDerivedEntities
    async_add_entities(sensorEntities, True)
    async_add_entities(sensorDerivedEntities, True)

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

    # Schedule the update function to run every X seconds
    async_track_time_interval(hass, async_update, timedelta(seconds=POLL_INTERVAL_SECONDS))

    return True


def get_value(self):
    if len(self._register) > 1:
        s32_values = [self._hass.data[DOMAIN]['values'][reg] for reg in self._register]
        # These are two 16-bit values representing a 32-bit signed integer (S32)
        high_word = s32_values[0] - (1 << 16) if s32_values[0] & (1 << 15) else s32_values[0]
        low_word = s32_values[1] - (1 << 16) if s32_values[1] & (1 << 15) else s32_values[1]

        # Combine the high and low words to form a 32-bit signed integer
        combined_value = (high_word << 16) | (low_word & 0xFFFF)
        n_value = combined_value / (10 ** self._decimal_places)
    else:
        # Treat it as a single register (U16)
        n_value = self._hass.data[DOMAIN]['values'][self._register[0]] / (10 ** self._decimal_places)

    return n_value


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
        self._decimal_places = entity_definition.get("decimal_places", 1)

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
                r1_value = round(self._hass.data[DOMAIN]['values'][self._register[0]] / (10 ** self._decimal_places))
                r2_value = round(self._hass.data[DOMAIN]['values'][self._register[1]] / (10 ** self._decimal_places))
                n_value = round(r1_value * r2_value)

            self._attr_available = True
            self._attr_native_value = n_value
            self._state = n_value
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
            identifiers={(DOMAIN, self._hass.data[DOMAIN][CONTROLLER].host)},
            manufacturer="Solis",
            model="Solis S6",
            name="Solis S6",
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
        self._decimal_places = entity_definition.get("decimal_places", 1)

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

            n_value = get_value(self)

            self._attr_available = True
            self._attr_native_value = n_value
            self._state = n_value
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
            manufacturer="Solis",
            model="Solis S6",
            name="Solis S6",
            sw_version=VERSION,
        )
