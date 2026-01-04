from unittest.mock import MagicMock

import pytest

from custom_components.solis_modbus.const import DOMAIN, CONTROLLER
from custom_components.solis_modbus.data.enums import InverterType
from custom_components.solis_modbus.switch import async_setup_entry


@pytest.mark.asyncio
async def test_switch_bit_position_requires_combinations_are_unique():
    # 1. Setup ConfigEntry with a specific ID
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry_switch_123"  # Critical: Must match key in hass.data
    config_entry.data = {"host": "10.0.0.1", "slave": 1}
    config_entry.options = {}

    # 2. Setup the Controller Mock
    controller = MagicMock()
    controller.host = "10.0.0.1"
    controller.device_id = 1
    controller.connected.return_value = True

    # Mock Inverter Config
    controller.inverter_config = MagicMock()
    controller.inverter_config.type = InverterType.HYBRID
    controller.inverter_config.features = set()
    controller.model = "S6"
    controller.device_identification = "XYZ"
    controller.sw_version = "1.0"

    # 3. Setup Hass Data using the NEW structure (Key = Entry ID)
    hass = MagicMock()
    hass.create_task = MagicMock()
    hass.data = {
        DOMAIN: {
            CONTROLLER: {
                config_entry.entry_id: controller  # <--- FIX: Use Entry ID as key
            }
        }
    }

    captured_entities = []

    async def capture_add_devices(entities, update_immediately=False):
        captured_entities.extend(entities)

    # 4. Run Setup
    await async_setup_entry(hass, config_entry, capture_add_devices)

    # 5. Assertions
    seen_keys = set()
    for entity in captured_entities:
        # Guard: Ensure entity has expected attributes
        if not hasattr(entity, "_register") or not hasattr(entity, "_bit_position"):
            continue

        register = entity._register
        bit = entity._bit_position
        requires = tuple(sorted(entity._requires)) if entity._requires else ()

        if bit is None:
            continue

        key = (register, bit, requires)
        assert key not in seen_keys, f"Duplicate (register, bit_position, requires): {key} in entity: {entity._attr_name}"
        seen_keys.add(key)
