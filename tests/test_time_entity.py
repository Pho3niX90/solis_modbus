import unittest
from types import SimpleNamespace
from datetime import time as dt_time
from unittest.mock import MagicMock

from custom_components.solis_modbus.const import (
    CONTROLLER,
    DOMAIN,
    REGISTER,
    SLAVE,
    VALUE,
    VALUES,
)
from custom_components.solis_modbus.time import SolisTimeEntity


class TestSolisTimeEntity(unittest.TestCase):
    """Unit tests for SolisTimeEntity."""

    def setUp(self):
        self.register = 43143

        self.hass = MagicMock()
        self.hass.bus.async_listen = MagicMock()
        self.hass.data = {DOMAIN: {VALUES: {str(self.register): 10, str(self.register + 1): 30}}}

        self.controller = MagicMock()
        self.controller.host = "1.2.3.4"
        self.controller.slave = 1
        self.controller.device_id = 1
        self.controller.identification = "unit"
        self.controller.device_identification = ""
        self.controller.model = "Test"
        self.controller.sw_version = "1.0"

        self.entity = SolisTimeEntity(
            self.hass,
            self.controller,
            {"name": "Slot 1 Start", "register": self.register},
        )
        # Avoid relying on HA internals for scheduling updates
        self.entity.schedule_update_ha_state = MagicMock()

    def test_handle_modbus_update_uses_internal_hass_reference(self):
        """Ensure the entity reads from the stored hass reference when updating."""
        event = SimpleNamespace(
            data={
                REGISTER: self.register,
                VALUE: 1,
                CONTROLLER: self.controller.host,
                SLAVE: self.controller.slave,
            }
        )

        # Simulate an update for the tracked register
        self.entity.handle_modbus_update(event)

        # The native value should be updated using the cached hour/minute pair
        self.assertEqual(self.entity._attr_native_value, dt_time(hour=10, minute=30))
        self.assertTrue(self.entity._attr_available)
        self.entity.schedule_update_ha_state.assert_called_once()


if __name__ == "__main__":
    unittest.main()
