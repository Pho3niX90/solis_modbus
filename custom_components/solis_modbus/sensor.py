import asyncio
import fractions
import logging
import numbers
from datetime import timedelta, datetime
import decimal
from typing import List

from homeassistant.components.sensor import SensorEntity, RestoreSensor
from homeassistant.components.sensor.const import SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, MANUFACTURER, VALUES, SENSOR_DERIVED_ENTITIES, \
    SENSOR_ENTITIES, DRIFT_COUNTER
from custom_components.solis_modbus.status_mapping import STATUS_MAPPING

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Set up Modbus sensors from a config entry."""
    modbus_controller: ModbusController = hass.data[DOMAIN][CONTROLLER][config_entry.data.get("host")]
    sensor_entities: List[SensorEntity] = []
    sensor_derived_entities: List[SensorEntity] = []
    hass.data[DOMAIN][VALUES] = {}
    modbus_controller._data_received = False

    inverter_type = config_entry.data.get("type", "hybrid")

    if inverter_type in ["string", "grid"]:
        from .data.string_sensors import string_sensors as sensors
        from .data.string_sensors import string_sensors_derived as sensors_derived
    elif inverter_type == "hybrid-waveshare":
        from .data.hybrid_waveshare_sensors import hybrid_waveshare as sensors
        from .data.hybrid_waveshare_sensors import hybrid_waveshare_sensors_derived as sensors_derived
    else:
        from .data.hybrid_sensors import hybrid_sensors as sensors
        from .data.hybrid_sensors import hybrid_sensors_derived as sensors_derived

    for sensor_group in sensors:
        for entity_definition in sensor_group['entities']:
            for register in entity_definition['register']:
                hass.data[DOMAIN][VALUES][register] = 0
            type = entity_definition["type"]
            if type == 'SS':
                sensor_entities.append(SolisSensor(hass, modbus_controller, entity_definition))

    for sensor_group in sensors_derived:
        type = sensor_group["type"]
        if type == 'SDS':
            sensor_derived_entities.append(SolisDerivedSensor(hass, modbus_controller, sensor_group))

    hass.data[DOMAIN][SENSOR_ENTITIES] = sensor_entities
    hass.data[DOMAIN][SENSOR_DERIVED_ENTITIES] = sensor_derived_entities
    async_add_entities(sensor_entities, True)
    async_add_entities(sensor_derived_entities, True)

    @callback
    def update(now):
        """Update Modbus data periodically."""
        for controller in hass.data[DOMAIN][CONTROLLER].values():
            hass.create_task(get_modbus_updates(hass, controller))

            asyncio.gather(
                *[asyncio.to_thread(entity.update) for entity in hass.data[DOMAIN][SENSOR_ENTITIES]],
                *[asyncio.to_thread(entity.update) for entity in hass.data[DOMAIN][SENSOR_DERIVED_ENTITIES]]
            )

    async def get_modbus_updates(hass, controller: ModbusController):
        if not controller.enabled:
            return

        if not controller.connected():
            await controller.connect()

        if not controller.connected():
            return

        for sensor_group in sensors:
            start_register = sensor_group['register_start']

            count = sum(len(entity.get('register', [])) for entity in sensor_group.get('entities', []))

            if start_register >= 40000:
                values = await controller.async_read_holding_register(start_register, count)
            else:
                values = await controller.async_read_input_register(start_register, count)

            if values is None:
                continue

            # Store each value with a unique key
            for i, value in enumerate(values):
                register_key = f"{start_register + i}"
                hass.data[DOMAIN]['values'][register_key] = value
                _LOGGER.debug(f'register_key = {register_key}, value = {value}')

            controller._data_received = True

    async_track_time_interval(hass, update, timedelta(seconds=modbus_controller.poll_interval))
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
        if self._multiplier == 0 or self._multiplier == 1:
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


async def clock_drift_test(hass, controller, hours, minutes, seconds):
    # Get the current time
    current_time = datetime.now()

    # Extract hours, minutes, and seconds
    r_hours = current_time.hour
    r_minutes = current_time.minute
    r_seconds = current_time.second
    d_hours = r_hours - hours
    d_minutes = r_minutes - minutes
    d_seconds = r_seconds - seconds
    total_drift = (d_hours * 60 * 60) + (d_minutes * 60) + d_seconds

    drift_counter = hass.data[DOMAIN].get(DRIFT_COUNTER, 0)

    if abs(total_drift) > 5:
        """this is to make sure that we do not accidentally roll back the time, resetting all stats"""
        if drift_counter > 5:
            if controller.connected():
                await controller.async_write_holding_registers(43003, [current_time.hour, current_time.minute,
                                                                       current_time.second])
        else:
            hass.data[DOMAIN][DRIFT_COUNTER] = drift_counter + 1
    else:
        hass.data[DOMAIN][DRIFT_COUNTER] = 0


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


class SolisDerivedSensor(RestoreSensor, SensorEntity):
    """Representation of a Modbus derived/calculated sensor."""

    def __init__(self, hass, modbus_controller, entity_definition):
        self._hass = hass
        self._modbus_controller: ModbusController = modbus_controller
        self._attr_name = entity_definition["name"]
        self._attr_has_entity_name = True
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

            if '33049' in self._register or '33051' in self._register or '33053' in self._register or '33055' in self._register:
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

            # set after
            if '35000' in self._register:
                protocol_version, model_description = decode_inverter_model(n_value)
                self._modbus_controller._sw_version = protocol_version
                self._modbus_controller._model = model_description
                n_value = model_description + f"(Protocol {protocol_version})"

            if isinstance(n_value, (numbers.Number, decimal.Decimal, fractions.Fraction)):
                self._attr_available = True
                self._attr_native_value = n_value
                self._state = n_value
                self.schedule_update_ha_state()
            if isinstance(n_value, str):
                self._attr_available = True
                self._attr_native_value = n_value
                self._state = n_value
                self.schedule_update_ha_state()

        except ValueError as e:
            self._state = None
            self._attr_available = False

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._modbus_controller.host)},
            manufacturer=MANUFACTURER,
            model=self._modbus_controller.model,
            name=f"{MANUFACTURER} {self._modbus_controller.model}",
            sw_version=self._modbus_controller.sw_version,
        )


class SolisSensor(RestoreSensor, SensorEntity):
    """Representation of a Modbus sensor."""

    def __init__(self, hass, modbus_controller, entity_definition):
        self._hass = hass
        self._modbus_controller: ModbusController = modbus_controller

        self._attr_name = entity_definition["name"]
        self._attr_has_entity_name = True
        self._attr_unique_id = "{}_{}_{}".format(DOMAIN, self._modbus_controller.host, entity_definition["unique"])

        self._register: List[int] = entity_definition["register"]
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

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state and state.native_value is not None:
            self._attr_native_value = state.native_value
        self.is_added_to_hass = True

    def update(self):
        """Update the sensor value."""

        try:
            if not self.is_added_to_hass:
                return

            if '33027' in self._register:
                hours = self._hass.data[DOMAIN][VALUES][str(int(self._register[0]) - 2)]
                minutes = self._hass.data[DOMAIN][VALUES][str(int(self._register[0]) - 1)]
                seconds = self._hass.data[DOMAIN][VALUES][self._register[0]]
                self.hass.create_task(clock_drift_test(self._hass, self._modbus_controller, hours, minutes, seconds))

            if len(self._register) == 1 and self._register[0] in ('33001', '33002', '33003'):
                n_value = hex(round(get_value(self)))[2:]
            else:
                n_value = get_value(self)

            if (n_value == 0
                    and self.state_class != SensorStateClass.MEASUREMENT
                    and self._modbus_controller.data_received is not True):
                n_value = self.async_get_last_sensor_data()

            if n_value is not None and not asyncio.iscoroutine(n_value):
                self._attr_available = True
                self._attr_native_value = n_value
                self._state = n_value
                self.schedule_update_ha_state()

        except ValueError as e:
            self._state = None
            self._attr_available = False

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._modbus_controller.host)},
            manufacturer=MANUFACTURER,
            model=self._modbus_controller.model,
            name=f"{MANUFACTURER} {self._modbus_controller.model}",
            sw_version=self._modbus_controller.sw_version,
        )
