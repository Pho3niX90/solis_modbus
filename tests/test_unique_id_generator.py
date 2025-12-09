import unittest
from unittest.mock import MagicMock
from custom_components.solis_modbus.helpers import unique_id_generator
from custom_components.solis_modbus.const import DOMAIN

class TestUniqueIdGenerator(unittest.TestCase):
    def setUp(self):
        self.controller = MagicMock()
        # Defaults
        self.controller.device_serial_number = None
        self.controller.identification = None
        self.controller.host = "192.168.1.10"
        self.entity_def = {"unique": "test_sensor"}

    def test_serial_number_set(self):
        """Test Case 1: Serial number set, identification None."""
        self.controller.device_serial_number = "SN123456"
        self.controller.identification = None
        
        unique_id = unique_id_generator(self.controller, self.entity_def.get("unique", "reserve"))
        expected_id = f"{DOMAIN}_SN123456_test_sensor"
        self.assertEqual(unique_id, expected_id)

    def test_identification_set(self):
        """Test Case 2: Serial number None, identification set."""
        self.controller.device_serial_number = None
        self.controller.identification = "ID789"
        
        unique_id = unique_id_generator(self.controller, self.entity_def.get("unique", "reserve"))
        expected_id = f"{DOMAIN}_ID789_test_sensor"
        self.assertEqual(unique_id, expected_id)

    def test_neither_set(self):
        """Test Case 3: Neither set (Fallback to host)."""
        self.controller.device_serial_number = None
        self.controller.identification = None
        
        unique_id = unique_id_generator(self.controller, self.entity_def.get("unique", "reserve"))
        expected_id = f"{DOMAIN}_192.168.1.10_test_sensor"
        self.assertEqual(unique_id, expected_id)

    def test_both_set(self):
        """Test Case 4: Both set (Priority to Serial Number)."""
        self.controller.device_serial_number = "SN123456"
        self.controller.identification = "ID789"
        
        unique_id = unique_id_generator(self.controller, self.entity_def.get("unique", "reserve"))
        expected_id = f"{DOMAIN}_SN123456_test_sensor"
        self.assertEqual(unique_id, expected_id, "Serial Number should take precedence over Identification")

if __name__ == "__main__":
    unittest.main()
