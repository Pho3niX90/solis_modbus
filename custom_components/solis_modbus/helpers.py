import logging
import struct
from datetime import datetime
from typing import List

from homeassistant.core import HomeAssistant
from custom_components.solis_modbus import DOMAIN
from custom_components.solis_modbus.const import DRIFT_COUNTER, VALUES, CONTROLLER

_LOGGER = logging.getLogger(__name__)

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
    packed = struct.pack('>' + 'H'*len(values), *values)
    return packed.decode('ascii', errors='ignore').strip('\x00\r\n ')


def clock_drift_test(hass, controller, hours, minutes, seconds):
    current_time = datetime.now()
    device_time = datetime(current_time.year, current_time.month, current_time.day, hours, minutes, seconds)
    total_drift = (current_time - device_time).total_seconds()

    # Ensure structure
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    drift_counter = hass.data[DOMAIN].get(DRIFT_COUNTER, 0)
    clock_adjusted = False

    if abs(total_drift) > 60:
        if drift_counter > 5:
            if controller.connected():
                hass.create_task(controller.async_write_holding_registers(
                    43003, [current_time.hour, current_time.minute, current_time.second]
                ))
                clock_adjusted = True
        else:
            hass.data[DOMAIN][DRIFT_COUNTER] = drift_counter + 1
    else:
        hass.data[DOMAIN][DRIFT_COUNTER] = 0

    _LOGGER.debug(f"Drift: {total_drift}s, Counter: {drift_counter}, Adjusted: {clock_adjusted}")
    return clock_adjusted


def decode_inverter_model(hex_value):
    """
    Decodes an inverter model code into its protocol version and description.

    :param hex_value: The hexadecimal or decimal inverter model code.
    :return: A tuple (protocol_version, model_description)
    """
    # Convert hexadecimal string to integer if necessary
    if isinstance(hex_value, str):
        hex_value = int(hex_value, 16)

    # Extract high byte (protocol version) and low byte (inverter model)
    protocol_version = (hex_value >> 8) & 0xFF
    inverter_model = hex_value & 0xFF

    inverter_models = {
        0x00: "No definition",
        0x10: "1-Phase Grid-Tied Inverter (0.7-8K1P / 7-10K1P)",
        0x20: "3-Phase Grid-Tied Inverter (3-20K 3P)",
        0x21: "3-Phase Grid-Tied Inverter (25-50K / 50-70K / 80-110K / 90-136K / 125K / 250K)",
        0x30: "1-Phase LV Hybrid Inverter",
        0x31: "1-Phase LV AC Coupled Energy Storage Inverter",
        0x32: "5-15kWh All-in-One Hybrid",
        0x40: "1-Phase HV Hybrid Inverter",
        0x50: "3-Phase LV Hybrid Inverter",
        0x60: "3-Phase HV Hybrid Inverter (5G)",
        0x70: "S6 3-Phase HV Hybrid (5-10kW)",
        0x71: "S6 3-Phase HV Hybrid (12-20kW)",
        0x72: "S6 3-Phase LV Hybrid (10-15kW)",
        0x73: "S6 3-Phase HV Hybrid (50kW)",
        0x80: "1-Phase HV Hybrid Inverter (S6)",
        0x90: "1-Phase LV Hybrid Inverter (S6)",
        0x91: "S6 1-Phase LV AC Coupled Hybrid",
        0xA0: "OGI Off-Grid Inverter",
        0xA1: "S6 1-Phase LV Off-Grid Hybrid",
    }

    # Get model description or default to "Unknown Model"
    model_description = inverter_models.get(inverter_model, "Unknown Model")

    return protocol_version, model_description

def cache_save(hass: HomeAssistant, register: str | int, value):
    hass.data[DOMAIN][VALUES][str(register)] = value

def cache_get(hass: HomeAssistant, register: str | int):
    return hass.data[DOMAIN][VALUES].get(str(register), None)

def set_controller(hass: HomeAssistant, controller):
    hass.data[DOMAIN][CONTROLLER]["{}_{}".format(controller.host, controller.slave)] = controller

def get_controller(hass: HomeAssistant, controller_host: str, controller_slave: int):
    controller = hass.data[DOMAIN][CONTROLLER]["{}_{}".format(controller_host, controller_slave)]
    if controller:
        return controller
    return hass.data[DOMAIN][CONTROLLER][controller_host]

def split_s32(s32_values: List[int]):
    high_word = s32_values[0] - (1 << 16) if s32_values[0] & (1 << 15) else s32_values[0]
    low_word = s32_values[1] - (1 << 16) if s32_values[1] & (1 << 15) else s32_values[1]

    # Combine the high and low words to form a 32-bit signed/unsigned integer
    return  (high_word << 16) | (low_word & 0xFFFF)

def _any_in(target: List[int], collection: set[int]) -> bool:
    return any(item in collection for item in target)