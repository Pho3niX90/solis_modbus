from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.solis_modbus.const import CONTROLLER, REGISTER, SLAVE, VALUE
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor


@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.slave = 1
    controller.model = "TestModel"
    controller.device_id = 1
    return controller


@pytest.fixture
def mock_base_sensor(mock_controller):
    sensor = MagicMock()
    sensor.controller = mock_controller
    sensor.name = "Test Sensor"
    sensor.unique_id = "test_derived_id"
    sensor.registrars = [33095]
    sensor.multiplier = 1
    sensor.device_class = None
    sensor.unit_of_measurement = None
    sensor.hidden = False
    sensor.state_class = "measurement"  # Add missing attr
    return sensor


def test_derived_sensor_status(hass: HomeAssistant, mock_base_sensor):
    sensor = SolisDerivedSensor(hass, mock_base_sensor)

    # Simulate status update (33095)
    # 3 = "Generating"
    mock_base_sensor.get_value = 3
    event_data = {REGISTER: 33095, VALUE: 3, CONTROLLER: "1.2.3.4", SLAVE: 1}

    with patch.object(sensor, "schedule_update_ha_state"):
        sensor.handle_modbus_update(event_data)

    assert sensor.native_value == "Generating"


def test_derived_sensor_dc_power(hass: HomeAssistant, mock_base_sensor):
    mock_base_sensor.registrars = [33049, 33050]  # Voltage, Current
    sensor = SolisDerivedSensor(hass, mock_base_sensor)

    # Prime first value
    sensor._received_values[33049] = 200

    event_data = {REGISTER: 33050, VALUE: 10, CONTROLLER: "1.2.3.4", SLAVE: 1}

    with patch.object(sensor, "schedule_update_ha_state"):
        sensor.handle_modbus_update(event_data)

    assert sensor.native_value == 2000


def test_derived_sensor_string_dc_power(hass: HomeAssistant, mock_base_sensor):
    """String inverter DC power: raw V and A each scaled ×0.1, product in watts."""
    mock_base_sensor.registrars = [3021, 3022]
    mock_base_sensor.multiplier = 0.1
    sensor = SolisDerivedSensor(hass, mock_base_sensor)

    sensor._received_values[3021] = 400  # 40.0 V

    event_data = {REGISTER: 3022, VALUE: 50, CONTROLLER: "1.2.3.4", SLAVE: 1}

    with patch.object(sensor, "schedule_update_ha_state"):
        sensor.handle_modbus_update(event_data)

    assert sensor.native_value == 200  # 40 * 5 W * 0.1


def test_derived_sensor_wrong_controller(hass: HomeAssistant, mock_base_sensor):
    sensor = SolisDerivedSensor(hass, mock_base_sensor)

    event_data = {
        REGISTER: 33095,
        VALUE: 3,
        CONTROLLER: "9.9.9.9",  # Wrong IP
        SLAVE: 1,
    }

    with patch.object(sensor, "schedule_update_ha_state"):
        sensor.handle_modbus_update(event_data)

    assert sensor.native_value is None


def test_derived_sensor_incomplete_data(hass: HomeAssistant, mock_base_sensor):
    mock_base_sensor.registrars = [33049, 33050]
    sensor = SolisDerivedSensor(hass, mock_base_sensor)

    # Only send one value, missing the other
    event_data = {REGISTER: 33050, VALUE: 10, CONTROLLER: "1.2.3.4", SLAVE: 1}

    with patch.object(sensor, "schedule_update_ha_state"):
        sensor.handle_modbus_update(event_data)

    assert sensor.native_value is None
    assert sensor._received_values[33050] == 10
