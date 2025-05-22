import pytest
from unittest.mock import MagicMock

from custom_components.solis_modbus.const import DOMAIN, CONTROLLER
from custom_components.solis_modbus.data.enums import InverterType
from custom_components.solis_modbus.select import async_setup_entry

@pytest.mark.asyncio
async def test_select_bit_position_requires_combinations_are_unique():
    controller = MagicMock()
    controller.host = "10.0.0.1"
    controller.connected.return_value = True
    controller.inverter_config = MagicMock()
    controller.inverter_config.type = InverterType.HYBRID
    controller.inverter_config.features = set()  # test LV battery config
    controller.identification = "abc"
    controller.model = "S6"
    controller.device_identification = "XYZ"
    controller.sw_version = "1.0"

    hass = MagicMock()
    hass.create_task = MagicMock()
    hass.data = {
        DOMAIN: {
            CONTROLLER: {
                "10.0.0.1": controller
            }
        }
    }

    config_entry = MagicMock()
    config_entry.data = {"host": "10.0.0.1"}
    config_entry.options = {}

    captured_entities = []

    async def capture_add_devices(entities, update_immediately):
        captured_entities.extend(entities)

    await async_setup_entry(hass, config_entry, capture_add_devices)

    seen_keys = set()
    for entity in captured_entities:
        register = entity._register
        for raw in entity._attr_options_raw:
            bit = raw.get("bit_position")
            if bit is None:
                continue  # ignore value-based selects like battery model
            requires = tuple(sorted(raw.get("requires", ())))
            key = (register, bit, requires)
            assert key not in seen_keys, f"Duplicate (register, bit_position, requires): {key} in entity: {raw.get('name')}"
            seen_keys.add(key)
