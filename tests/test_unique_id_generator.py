import unittest
from unittest.mock import MagicMock

from custom_components.solis_modbus.const import DOMAIN
from custom_components.solis_modbus.helpers import register_cache_key, unique_id_generator


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

    def test_dict_argument_extracts_unique_key(self):
        """#452 safety net: dict args must not stringify the whole definition."""
        self.controller.device_serial_number = "SN123456"
        entity = {
            "name": "Backup Load Total Energy",
            "unique": "solis_modbus_inverter_backup_total_energy",
            "register": ["33590", "33591"],
            "data_type": "U32",
        }
        unique_id = unique_id_generator(self.controller, entity)
        self.assertEqual(unique_id, f"{DOMAIN}_SN123456_solis_modbus_inverter_backup_total_energy")
        self.assertNotIn("{", unique_id)
        self.assertNotIn("data_type", unique_id)

    def test_dict_argument_stable_when_keys_added(self):
        """Adding definition keys must not change the generated unique_id."""
        self.controller.device_serial_number = "SN123456"
        key = "solis_modbus_inverter_backup_total_energy"
        before = unique_id_generator(self.controller, {"unique": key})
        after = unique_id_generator(self.controller, {"unique": key, "data_type": "U32", "category": "LOAD"})
        self.assertEqual(before, after)


class TestRegisterCacheKey(unittest.TestCase):
    def test_parallel_slaves_distinct(self):
        c1 = MagicMock()
        c1.connection_id = "10.0.0.1:502"
        c1.device_id = 1
        c2 = MagicMock()
        c2.connection_id = "10.0.0.1:502"
        c2.device_id = 2
        self.assertEqual(register_cache_key(c1, 33139), "10.0.0.1:502|1|33139")
        self.assertEqual(register_cache_key(c2, 33139), "10.0.0.1:502|2|33139")
        self.assertNotEqual(register_cache_key(c1, 33139), register_cache_key(c2, 33139))


if __name__ == "__main__":
    unittest.main()
