import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors, hybrid_sensors_derived
from custom_components.solis_modbus.const import DOMAIN


def generate_scenario(filename, serial=None, identification=None, host="1.2.3.4"):
    class MockController:
        pass
        
    controller = MockController()
    controller.device_serial_number = serial
    controller.identification = identification
    controller.host = host
    
    from custom_components.solis_modbus.helpers import unique_id_generator, unique_id_generator_binary
    
    known_sensors = []
    
    # Process standard sensors
    for group in hybrid_sensors:
        for entity in group.get("entities", []):
             if entity.get("type") == "reserve":
                 continue
             uid = unique_id_generator(controller, entity.get("unique", "reserve"))
             known_sensors.append(uid)
             
    for entity in hybrid_sensors_derived:
        uid = f"{DOMAIN}_{entity['unique']}" 
        known_sensors.append(uid)

    from custom_components.solis_modbus.data.solis_config import InverterConfig, InverterType
    from custom_components.solis_modbus.sensor_data.switch_sensors import get_switch_sensors
    from custom_components.solis_modbus.sensor_data.select_sensors import get_select_sensors
    from custom_components.solis_modbus.sensor_data.time_sensors import get_time_sensors
    
    config = InverterConfig(model="TEST", type=InverterType.HYBRID, wattage=[5000], phases=[1])
    
    # Switch
    switch_groups = get_switch_sensors(config)
    for group in switch_groups:
         for entity in group['entities']:
             # Logic from SolisBinaryEntity
             # Switch entities get their register injected from the group in switch.py
             register = group.get("register", group.get("read_register")) + entity.get("offset", 0)
             bit_position = entity.get("bit_position")
             on_value = entity.get("on_value")
             uid = unique_id_generator_binary(controller, register, bit_position, on_value)
             known_sensors.append(uid)

    # Select
    select_groups = get_select_sensors(config)
    for entity in select_groups:
         # Logic from SolisSelectEntity
         # unique_id_generator(modbus_controller, entity_definition["register"], "select")
         uid = unique_id_generator(controller, entity["register"], "select")
         known_sensors.append(uid)

    # Time
    time_sensors = get_time_sensors(config)
    for entity in time_sensors:
         # Logic from SolisTimeEntity: unique_id_generator(controller, entity.get("unique", "reserve"))
         uid = unique_id_generator(controller, entity.get("unique", "reserve"))
         known_sensors.append(uid)

    known_sensors.sort()
    
    with open(f"tests/{filename}", "w") as f:
        json.dump(known_sensors, f, indent=2)
        print(f"Generated {len(known_sensors)} known sensors to tests/{filename}")

def generate_known_sensors():
    # 1. Serial Number Scenario (Priority 1)
    generate_scenario("known_sensors_serial.json", serial="SN_SNAPSHOT", identification="ID_FAIL", host="FAIL_IP")
    
    # 2. Identification Scenario (Priority 2)
    generate_scenario("known_sensors_identification.json", serial=None, identification="ID_SNAPSHOT", host="FAIL_IP")
    
    # 3. Host Scenario (Priority 3)
    generate_scenario("known_sensors_host.json", serial=None, identification=None, host="1.2.3.4") # Use a 'real-looking' IP

if __name__ == "__main__":
    generate_known_sensors()
