import pytest
from unittest.mock import MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from custom_components.solis_modbus.const import DOMAIN, CONTROLLER
from pytest_homeassistant_custom_component.common import MockConfigEntry
from tests.test_integration_setup import auto_enable_custom_integrations

@pytest.mark.skip(reason="Migration logic not implemented yet")
@pytest.mark.asyncio
async def test_unique_id_migration(hass: HomeAssistant, auto_enable_custom_integrations):
    """Test that entities with old unique IDs (no port) are migrated to new IDs (with port)."""
    
    # 1. Setup Config Entry with non-standard port
    host = "1.2.3.4"
    port = 9999
    slave = 1
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{host}_{slave}",
        data={
            "name": "Solis",
            "host": host,
            "port": port,
            "slave": slave,
            "model": "S6-GR1P", # Simple model
        }
    )
    entry.add_to_hass(hass)
    
    # 2. Pre-seed Entity Registry with "Old" Unique ID
    # Old ID format: solis_modbus_{host}_{slave}_{sensor_unique}
    # (Assuming SolisSensorGroup/Derived used generic logic or we focus on one example)
    # Let's use a common sensor, e.g., 'active_power' from string_sensors or similar.
    # We need to know the 'unique' suffix from the sensor definition.
    # For 'S6-GR1P', let's pick a sensor. 'active_power' usually has unique 'active_power'.
    
    registry = er.async_get(hass)
    old_unique_id = f"{DOMAIN}_{host}_{slave}_active_power"
    reg_entry = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id="solis_active_power",
        config_entry=entry
    )
    entity_id = reg_entry.entity_id
    
    # Verify entity exists with old ID
    assert registry.async_get(entity_id).unique_id == old_unique_id
    
    # 3. Setup Integration
    # We need to mock get_controller to avoid actual connection, 
    # but ALLOW async_setup_entry to run logic.
    
    mock_controller = MagicMock()
    mock_controller.host = host
    mock_controller.port = port
    mock_controller.device_id = slave
    mock_controller.inverter_config = MagicMock()
    mock_controller.inverter_config.type = "string" # or whatever matches S6-GR1P in logic
    mock_controller.inverter_config.features = []
    mock_controller.inverter_config.features = []
    
    # Create a mock sensor group with one sensor 'active_power'
    mock_sensor = MagicMock()
    mock_sensor.unique_key = "active_power"
    mock_sensor.name = "Active Power"
    
    mock_group = MagicMock()
    mock_group.sensors = [mock_sensor]
    mock_group.group_name = "MockGroup"
    
    mock_controller.sensor_groups = [mock_group]
    mock_controller.derived_sensors = [] # derived sensors also iterated
    
    # Needs poll_speed values for DataRetrieval
    mock_controller.poll_speed = {
        "fast": 5,
        "normal": 15,
        "slow": 30
    }
    
    # The plan is to implement migration in async_setup_entry.
    
    with patch("custom_components.solis_modbus.get_controller", return_value=mock_controller), \
         patch("custom_components.solis_modbus.ModbusController", return_value=mock_controller), \
         patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups", return_value=True):
    
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    # 4. Verify Migration
    # New ID format: solis_modbus_{host}_{port}_{slave}_{sensor_unique}
    new_unique_id = f"{DOMAIN}_{host}_{port}_{slave}_active_power"
    
    entry_entity = registry.async_get(entity_id)
    assert entry_entity.unique_id == new_unique_id
