import unittest
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors, hybrid_sensors_derived
from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors, string_sensors_derived

def extract_all_entities(sensor_groups):
    for group in sensor_groups:
        for entity in group.get("entities", []):
            yield group["register_start"], entity

class TestSensorDefinitions(unittest.TestCase):

    def check_group(self, name, sensor_groups, derived_sensors):
        for group in sensor_groups:
            entities = group.get("entities", [])
            if not entities:
                continue

            # 1. register_start matches first register
            self.assertTrue(
                    entities[0].get("register"),
                    f"{name}: Entity {entities[0].get('name')} has no registers defined"
                )
            first_register = int(entities[0]["register"][0])
            self.assertEqual(
                group["register_start"], first_register,
                f"{name}: Group starting at {group['register_start']} != first entity register {first_register}"
            )

            # 4. Ensure register sequence is contiguous
            all_regs = []
            for entity in entities:
                all_regs.extend(int(r) for r in entity["register"])
            all_regs_sorted = sorted(all_regs)
            expected_sequence = list(range(min(all_regs_sorted), max(all_regs_sorted) + 1))
            self.assertEqual(
                all_regs_sorted, expected_sequence,
                f"{name}: Registers in group starting at {group['register_start']} are not sequential: {all_regs_sorted}"
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
            key = (entity.get("name", ""), tuple(entity["register"]))
            self.assertNotIn(key, seen_keys, f"{name}: Duplicate entity {key}")
            seen_keys.add(key)

        for entity in derived_sensors:
            key = (entity.get("name", ""), tuple(entity.get("register", [])))
            self.assertNotIn(key, seen_keys, f"{name}: Duplicate derived entity {key}")
            seen_keys.add(key)

    def test_hybrid_sensors(self):
        self.check_group("Hybrid", hybrid_sensors, hybrid_sensors_derived)

    def test_string_sensors(self):
        self.check_group("String", string_sensors, string_sensors_derived)

if __name__ == "__main__":
    unittest.main()
