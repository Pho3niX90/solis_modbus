import asyncio
import logging
from datetime import timedelta, datetime
from typing import List
from numbers import Number

from homeassistant.components.sensor import SensorEntity, RestoreSensor
from homeassistant.components.sensor.const import SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from custom_components.solis_modbus.const import DOMAIN, CONTROLLER, VERSION, POLL_INTERVAL_SECONDS, MANUFACTURER, \
    MODEL, DATA_RECEIVED, VALUES, SENSOR_DERIVED_ENTITIES, SENSOR_ENTITIES, DRIFT_COUNTER
from custom_components.solis_modbus.status_mapping import STATUS_MAPPING

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Set up Modbus sensors from a config entry."""
    modbus_controller = hass.data[DOMAIN][CONTROLLER][config_entry.data.get("host")]
    sensor_entities: List[SensorEntity] = []
    sensor_derived_entities: List[SensorEntity] = []
    hass.data[DOMAIN][VALUES] = {}
    hass.data[DOMAIN][DATA_RECEIVED] = False

    inverter_type = config_entry.data.get("type", "hybrid")

    if inverter_type == "string":
        from .data.string_sensors import string_sensors as sensors
        from .data.string_sensors import string_sensors_derived as sensors_derived
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
        for controller in hass.data[DOMAIN][CONTROLLER]:
            hass.create_task(get_modbus_updates(hass, controller))

            asyncio.gather(
                *[asyncio.to_thread(entity.update) for entity in hass.data[DOMAIN][SENSOR_ENTITIES]],
                *[asyncio.to_thread(entity.update) for entity in hass.data[DOMAIN][SENSOR_DERIVED_ENTITIES]]
            )

    async def get_modbus_updates(hass, controller):
        if not controller.connected():
            await controller.connect()

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

            hass.data[DOMAIN][DATA_RECEIVED] = True

    async_track_time_interval(hass, update, timedelta(seconds=POLL_INTERVAL_SECONDS))
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


class SolisDerivedSensor(RestoreSensor, SensorEntity):
    """Representation of a Modbus derived/calculated sensor."""

    def __init__(self, hass, modbus_controller, entity_definition):
        self._hass = hass
        self._modbus_controller = modbus_controller
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

            if isinstance(n_value, Number):
                self._attr_available = True
                self._attr_native_value = n_value * self._display_multiplier
                self._state = n_value * self._display_multiplier
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
        self._attr_has_entity_name = True
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
        if state and state.native_value is not None:
            self._attr_native_value = state.native_value * self._display_multiplier
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
                    and self._hass.data[DOMAIN][DATA_RECEIVED] is not True):
                n_value = self.async_get_last_sensor_data()

            if n_value is not None:
                self._attr_available = True
                self._attr_native_value = n_value * self._display_multiplier
                self._state = n_value * self._display_multiplier
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
            model=MODEL,
            name=f"{MANUFACTURER} {MODEL}",
            sw_version=VERSION,
        )
