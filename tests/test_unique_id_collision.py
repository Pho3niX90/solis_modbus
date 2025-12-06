import unittest
from unittest.mock import MagicMock
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup
from custom_components.solis_modbus.modbus_controller import ModbusController
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.const import DOMAIN

class TestSensorCollision(unittest.TestCase):
    def setUp(self):
        self.hass = MagicMock()
        self.inverter_config = MagicMock()
        self.inverter_config.model = "Test"
        self.inverter_config.features = []

    def test_unique_id_collision(self):
        # Controller A: Host 192.168.1.10, Slave 1
        controller_a = MagicMock()
        controller_a.host = "192.168.1.10"
        controller_a.port = 502
        controller_a.device_id = 1
        controller_a.inverter_config = self.inverter_config

        # Controller B: Host 192.168.1.10, Slave 2
        controller_b = MagicMock()
        controller_b.host = "192.168.1.10"
        controller_b.port = 502
        controller_b.device_id = 2
        controller_b.inverter_config = self.inverter_config

        definition = {
            "poll_speed": PollSpeed.NORMAL,
            "entities": [
                {
                    "name": "Active Power",
                    "register": [3000],
                    "unique": "active_power"
                }
            ]
        }

        group_a = SolisSensorGroup(self.hass, definition, controller_a, identification=None)
        group_b = SolisSensorGroup(self.hass, definition, controller_b, identification=None)

        sensor_a = group_a.sensors[0]
        sensor_b = group_b.sensors[0]

        print(f"Sensor A Unique ID: {sensor_a.unique_id}")
        print(f"Sensor B Unique ID: {sensor_b.unique_id}")

        self.assertNotEqual(sensor_a.unique_id, sensor_b.unique_id, "Unique IDs should be different for different slaves")

    def test_derived_unique_id_collision(self):
        # Even with different hosts, Derived Sensors might collide if they don't use Host in ID
        controller_a = MagicMock()
        controller_a.host = "192.168.1.10"
        controller_a.port = 502
        controller_a.device_id = 1
        controller_a.inverter_config = self.inverter_config

        controller_b = MagicMock()
        controller_b.host = "192.168.1.20" # Different IP!
        controller_b.port = 502
        controller_b.device_id = 1
        controller_b.inverter_config = self.inverter_config

        entity_def = {
            "name": "Status",
            "unique": "inverter_status",
            "register": []
        }
        
        # Simulating __init__.py logic
        DOMAIN = "solis_modbus"
        identification = None
        
        if not identification:
             base_a = controller_a.host + (f"_{controller_a.port}" if hasattr(controller_a, 'port') and controller_a.port != 502 else "") + (f"_{controller_a.device_id}" if controller_a.device_id != 1 else "")
             base_b = controller_b.host + (f"_{controller_b.port}" if hasattr(controller_b, 'port') and controller_b.port != 502 else "") + (f"_{controller_b.device_id}" if controller_b.device_id != 1 else "")
             unique_id_a = f"{DOMAIN}_{base_a}_{entity_def['unique']}"
             unique_id_b = f"{DOMAIN}_{base_b}_{entity_def['unique']}"
        else:
             unique_id_a = f"{DOMAIN}_{identification}_{entity_def['unique']}"
             unique_id_b = f"{DOMAIN}_{identification}_{entity_def['unique']}"

        print(f"Derived A: {unique_id_a}")
        print(f"Derived B: {unique_id_b}")

        self.assertNotEqual(unique_id_a, unique_id_b, "Derived Sensor IDs should now be unique per Host/Slave")

    def test_port_collision(self):
        # User scenario: Same IP, Different Port, Same Slave (1)
        controller_a = MagicMock()
        controller_a.host = "192.168.1.10"
        controller_a.port = 5001
        controller_a.device_id = 1
        controller_a.inverter_config = self.inverter_config

        controller_b = MagicMock()
        controller_b.host = "192.168.1.10"
        controller_b.port = 5002
        controller_b.device_id = 1
        controller_b.inverter_config = self.inverter_config

        definition = {
            "poll_speed": PollSpeed.NORMAL,
            "entities": [
                {
                    "name": "Active Power",
                    "register": [3000],
                    "unique": "active_power"
                }
            ]
        }

        group_a = SolisSensorGroup(self.hass, definition, controller_a, identification=None)
        group_b = SolisSensorGroup(self.hass, definition, controller_b, identification=None)

        sensor_a = group_a.sensors[0]
        sensor_b = group_b.sensors[0]

        print(f"Sensor A Unique ID: {sensor_a.unique_id}")
        print(f"Sensor B Unique ID: {sensor_b.unique_id}")

        self.assertNotEqual(sensor_a.unique_id, sensor_b.unique_id, "Unique IDs should distinguish by Port if Host is same")

if __name__ == "__main__":
    unittest.main()
