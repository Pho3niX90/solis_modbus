import pytest
from unittest.mock import MagicMock, patch
from homeassistant.core import HomeAssistant, Event
from custom_components.solis_modbus.sensors.solis_derived_sensor import SolisDerivedSensor
from custom_components.solis_modbus.const import DOMAIN, REGISTER, VALUE, CONTROLLER, SLAVE

@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.slave = 1
    controller.identification = None
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
    sensor.state_class = "measurement" # Add missing attr
    return sensor

def test_derived_sensor_status(hass: HomeAssistant, mock_base_sensor):
    sensor = SolisDerivedSensor(hass, mock_base_sensor)
    
    # Simulate status update (33095)
    # 3 = "Generating"
    mock_base_sensor.get_value = 3
    event_data = {
        REGISTER: 33095,
        VALUE: 3,
        CONTROLLER: "1.2.3.4",
        SLAVE: 1
    }
    
    with patch.object(sensor, 'schedule_update_ha_state'):
        sensor.handle_modbus_update(Event(DOMAIN, data=event_data))
    
    assert sensor.native_value == "Generating"

def test_derived_sensor_dc_power(hass: HomeAssistant, mock_base_sensor):
    mock_base_sensor.registrars = [33049, 33050] # Voltage, Current
    sensor = SolisDerivedSensor(hass, mock_base_sensor)
    
    # Prime first value
    sensor._received_values[33049] = 200
    
    event_data = {
        REGISTER: 33050,
        VALUE: 10,
        CONTROLLER: "1.2.3.4",
        SLAVE: 1
    }
    
    with patch.object(sensor, 'schedule_update_ha_state'):
        sensor.handle_modbus_update(Event(DOMAIN, data=event_data))
    
    assert sensor.native_value == 2000

def test_derived_sensor_wrong_controller(hass: HomeAssistant, mock_base_sensor):
    sensor = SolisDerivedSensor(hass, mock_base_sensor)
    
    event_data = {
        REGISTER: 33095,
        VALUE: 3,
        CONTROLLER: "9.9.9.9", # Wrong IP
        SLAVE: 1
    }
    
    with patch.object(sensor, 'schedule_update_ha_state'):
        sensor.handle_modbus_update(Event(DOMAIN, data=event_data))
    
    assert sensor.native_value is None

def test_derived_sensor_incomplete_data(hass: HomeAssistant, mock_base_sensor):
    mock_base_sensor.registrars = [33049, 33050]
    sensor = SolisDerivedSensor(hass, mock_base_sensor)
    
    # Only send one value, missing the other
    event_data = {
        REGISTER: 33050,
        VALUE: 10,
        CONTROLLER: "1.2.3.4",
        SLAVE: 1
    }
    
    with patch.object(sensor, 'schedule_update_ha_state'):
        sensor.handle_modbus_update(Event(DOMAIN, data=event_data))
    
    assert sensor.native_value is None
    assert sensor._received_values[33050] == 10
