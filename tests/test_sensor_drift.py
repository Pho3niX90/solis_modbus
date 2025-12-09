import unittest
import json
import os

from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors, hybrid_sensors_derived
from custom_components.solis_modbus.helpers import unique_id_generator, unique_id_generator_binary
from custom_components.solis_modbus.const import DOMAIN

class TestSensorDrift(unittest.TestCase):
    
    def check_drift(self, filename, serial=None, identification=None, host="1.2.3.4"):
        known_sensors_path = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(known_sensors_path):
            self.fail(f"{filename} not found. Run generate_known_sensors.py to create it.")
            
        with open(known_sensors_path, "r") as f:
            known_sensors = set(json.load(f))

        class MockController:
            pass
        
        controller = MockController()
        controller.device_serial_number = serial
        controller.identification = identification
        controller.host = host
            
        current_sensors = set()

        # Standard Sensors
        for group in hybrid_sensors:
            for entity in group.get("entities", []):
                 if entity.get("type") == "reserve":
                     continue
                 uid = unique_id_generator(controller, entity.get("unique", "reserve"))
                 current_sensors.add(uid)
                 
        # Derived Sensors
        for entity in hybrid_sensors_derived:
             uid = f"{DOMAIN}_{entity['unique']}" 
             current_sensors.add(uid)
             
        # New Entity Types
        from custom_components.solis_modbus.data.solis_config import InverterConfig, InverterType
        from custom_components.solis_modbus.sensor_data.switch_sensors import get_switch_sensors
        from custom_components.solis_modbus.sensor_data.select_sensors import get_select_sensors
        from custom_components.solis_modbus.sensor_data.time_sensors import get_time_sensors
        
        config = InverterConfig(model="TEST", type=InverterType.HYBRID, wattage=[5000], phases=[1])
        
        # Switch
        for group in get_switch_sensors(config):
             for entity in group['entities']:
                 register = group.get("register", group.get("read_register")) + entity.get("offset", 0)
                 bit_position = entity.get("bit_position")
                 on_value = entity.get("on_value")
                 uid = unique_id_generator_binary(controller, register, bit_position, on_value)
                 current_sensors.add(uid)
                 
        # Select
        for entity in get_select_sensors(config):
             uid = unique_id_generator(controller, entity["register"], "select")
             current_sensors.add(uid)
             
        # Time
        for entity in get_time_sensors(config):
             uid = unique_id_generator(controller, entity.get("unique", "reserve"))
             current_sensors.add(uid)
             
        # Check for missing sensors (Drift)
        missing_sensors = known_sensors - current_sensors
        
        new_sensors = current_sensors - known_sensors
        
        if new_sensors:
            print(f"NOTICE [{filename}]: {len(new_sensors)} NEW sensors detected.")

        if missing_sensors:
            report_content = f"### ⚠️ Sensor Drift Detected ({filename})\n\n"
            report_content += "The following sensors are missing or have been renamed:\n\n"
            for s in missing_sensors:
                report_content += f"- `{s}`\n"
            
            # Append to report
            with open("drift_report.md", "a") as f:
                f.write(report_content + "\n")

        self.assertFalse(missing_sensors, f"Drift Detected in {filename}! Missing:\n{missing_sensors}")

    def test_drift_serial(self):
        self.check_drift("known_sensors_serial.json", serial="SN_SNAPSHOT", identification="ID_FAIL", host="FAIL_IP")

    def test_drift_identification(self):
         self.check_drift("known_sensors_identification.json", serial=None, identification="ID_SNAPSHOT", host="FAIL_IP")

    def test_drift_host(self):
         self.check_drift("known_sensors_host.json", serial=None, identification=None, host="1.2.3.4")

if __name__ == "__main__":
    # Clear previous report
    if os.path.exists("drift_report.md"):
        os.remove("drift_report.md")
    unittest.main()
