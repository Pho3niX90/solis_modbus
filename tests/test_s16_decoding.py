import unittest
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor
from custom_components.solis_modbus.data.enums import PollSpeed, DataType

class MockController:
    def __init__(self):
        class MockConfig:
            model = "TEST"
            features = []
            wattage_chosen = 5000
        self.inverter_config = MockConfig()
        self.connected = lambda: True

class TestSolisBaseSensorS16(unittest.TestCase):
    def setUp(self):
        self.hass = None
        self.controller = MockController()
        
    def create_sensor(self, data_type, multiplier=1):
        return SolisBaseSensor(
            hass=self.hass,
            controller=self.controller,
            unique_id="test_sensor",
            name="Test Sensor",
            registrars=[33093],
            write_register=None,
            multiplier=multiplier,
            data_type=data_type
        )
        
    def test_s16_decoding_positive(self):
        sensor = self.create_sensor(data_type=DataType.S16.value, multiplier=1)
        self.assertEqual(sensor._convert_raw_value([0]), 0)
        self.assertEqual(sensor._convert_raw_value([1]), 1)
        self.assertEqual(sensor._convert_raw_value([32767]), 32767)

    def test_s16_decoding_with_enum_member(self):
        sensor = self.create_sensor(data_type=DataType.S16, multiplier=1)
        # Should normalize to string .value
        self.assertEqual(sensor.data_type, DataType.S16.value)
        self.assertEqual(sensor._convert_raw_value([65535]), -1)

    def test_s16_decoding_negative(self):
        sensor = self.create_sensor(data_type=DataType.S16.value, multiplier=1)
        # 65535 is -1 in 16-bit two's complement
        self.assertEqual(sensor._convert_raw_value([65535]), -1)
        # 32768 is -32768 in 16-bit two's complement
        self.assertEqual(sensor._convert_raw_value([32768]), -32768)
        self.assertEqual(sensor._convert_raw_value([65534]), -2)

    def test_s16_decoding_with_multiplier(self):
        sensor = self.create_sensor(data_type=DataType.S16.value, multiplier=0.1)
        self.assertEqual(sensor._convert_raw_value([0]), 0.0)
        self.assertEqual(sensor._convert_raw_value([1]), 0.1)
        self.assertEqual(sensor._convert_raw_value([65535]), -0.1)
        self.assertEqual(sensor._convert_raw_value([65526]), -1.0)
        
    def test_u16_decoding(self):
        sensor = self.create_sensor(data_type=DataType.U16.value, multiplier=1)
        self.assertEqual(sensor._convert_raw_value([0]), 0)
        self.assertEqual(sensor._convert_raw_value([32768]), 32768)
        self.assertEqual(sensor._convert_raw_value([65535]), 65535)

    def test_empty_values(self):
        sensor = self.create_sensor(data_type=DataType.S16.value, multiplier=1)
        self.assertIsNone(sensor._convert_raw_value([]))
        self.assertIsNone(sensor._convert_raw_value([None]))

if __name__ == '__main__':
    unittest.main()
