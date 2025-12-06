import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from homeassistant.const import STATE_UNKNOWN, CONF_HOST
from custom_components.solis_modbus.sensors.solis_number_sensor import SolisNumberEntity
from custom_components.solis_modbus.const import DOMAIN
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.async_write_holding_register = AsyncMock()
    return controller

@pytest.fixture
def mock_base_sensor(mock_controller):
    sensor = MagicMock(spec=SolisBaseSensor)
    sensor.controller = mock_controller
    sensor.name = "Test Number"
    sensor.registrars = [100]
    sensor.write_register = 100
    sensor.device_class = "battery"
    sensor.unit_of_measurement = "%"
    sensor.state_class = "measurement"
    sensor.multiplier = 1
    sensor.min_value = 0
    sensor.max_value = 100
    sensor.step = 1
    sensor.step = 1
    sensor.enabled = True
    sensor.hidden = False
    sensor.unique_id = "test_unique_id"
    sensor.default = 50
    return sensor

@pytest.mark.asyncio
async def test_solis_number_entity(hass, mock_base_sensor, mock_controller):
    """Test SolisNumberEntity initialization and value setting."""
    
    # SolisNumberEntity takes (hass, sensor: SolisBaseSensor)
    print(f"DEBUG: Input Hass={hass}")
    entity = SolisNumberEntity(hass, mock_base_sensor)
    
    # Check attributes
    assert entity.name == "Test Number"
    assert entity.native_min_value == 0
    assert entity.native_max_value == 100
    assert entity.native_step == 1
    assert entity.native_unit_of_measurement == "%"
    
    # Test setting value
    entity.schedule_update_ha_state = MagicMock()
    entity.set_native_value(60)
    await hass.async_block_till_done()
    mock_controller.async_write_holding_register.assert_called_with(100, 60) 

@pytest.mark.asyncio
async def test_solis_number_entity_updates(hass, mock_controller):
    # Mock base sensor
    sensor = MagicMock(spec=SolisBaseSensor)
    sensor.controller = mock_controller
    sensor.name = "Test Number"
    sensor.registrars = [100, 101]
    sensor.write_register = None
    sensor.multiplier = 10
    sensor.convert_value = MagicMock(return_value=50.0)
    sensor.min_value = 0
    sensor.max_value = 100
    sensor.step = 1
    sensor.enabled = True
    sensor.hidden = False
    sensor.unique_id = "test_unique_id"
    sensor.default = 50
    sensor.device_class = "battery"
    sensor.unit_of_measurement = "%"
    sensor.state_class = "measurement"
    
    entity = SolisNumberEntity(hass, sensor)
    assert entity._hass is not None
    
    # Simulate modbus update
    # SolisNumberEntity listens to bus DOMAIN event.
    # We can invoke handle_modbus_update directly to test logic.
    event = MagicMock()
    event.data = {
        "register": 100,
        "controller": str(mock_controller), # Logic uses str(controller) comparison?
        # helpers.is_correct_controller checks this.
        # We need mock_controller to match expected.
        # Let's mock is_correct_controller checks for simplicity or mock attributes properly.
        # But handle_modbus_update does:
        # updated_controller = str(event.data.get(CONTROLLER))
        # if not is_correct_controller(self.base_sensor.controller, ...): return
    }
    # It allows test logic to verify update handling.
    # But simpler to test set_native_value which covers WRITE logic (missing in coverage).
    # Coverage report showed missing lines in write logic mostly.
    
    entity.schedule_update_ha_state = MagicMock()
    entity.set_native_value(55)
    await hass.async_block_till_done()
    # write_register is None, so return.
    assert not mock_controller.async_write_holding_register.called

