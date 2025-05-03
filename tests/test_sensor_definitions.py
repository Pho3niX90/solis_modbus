import unittest
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors, hybrid_sensors_derived
from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors, string_sensors_derived

def extract_all_entities(sensor_groups):
    for group in sensor_groups:
        for entity in group.get("entities", []):
            yield group["register_start"], entity

class TestSensorDefinitions(unittest.TestCase):

    def check_group(self, name, sensor_groups, derived_sensors):
        # 1. register_start must match the first child register
        for group in sensor_groups:
            if not group["entities"]:
                continue
            first_register = int(group["entities"][0]["register"][0])
            self.assertEqual(
                group["register_start"], first_register,
                f"{name}: Group starting at {group['register_start']} != first entity register {first_register}"
            )

        # 2. all unique fields must be unique
        seen_uniques = set()
        for _, entity in extract_all_entities(sensor_groups):
            uid = entity.get("unique")
            if uid:
                self.assertNotIn(uid, seen_uniques, f"{name}: Duplicate unique '{uid}' in sensor group")
                seen_uniques.add(uid)
        for entity in derived_sensors:
            uid = entity.get("unique")
            if uid:
                self.assertNotIn(uid, seen_uniques, f"{name}: Duplicate unique '{uid}' in derived sensors")
                seen_uniques.add(uid)

        # 3. no duplicate entity name + register
        seen_keys = set()
        for _, entity in extract_all_entities(sensor_groups):
            key = (entity.get("name", tuple(entity["register"])), tuple(entity["register"]))
            self.assertNotIn(key, seen_keys, f"{name}: Duplicate entity {key}")
            seen_keys.add(key)

    def test_hybrid_sensors(self):
        self.check_group("Hybrid", hybrid_sensors, hybrid_sensors_derived)

    def test_string_sensors(self):
        self.check_group("String", string_sensors, string_sensors_derived)

if __name__ == "__main__":
    unittest.main()
