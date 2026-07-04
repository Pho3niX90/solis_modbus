"""32-bit register decoding.

Two-register values default to signed 32-bit (many power/current registers are
genuinely signed). Registers explicitly tagged ``U32`` decode as unsigned so
lifetime totals never wrap negative once the raw count crosses 0x7FFFFFFF.
"""

import unittest

from custom_components.solis_modbus.data.enums import DataType
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor


class MockController:
    def __init__(self):
        class MockConfig:
            model = "TEST"
            features = []
            wattage_chosen = 5000

        self.inverter_config = MockConfig()
        self.connected = lambda: True


class TestSolisBaseSensor32Bit(unittest.TestCase):
    def setUp(self):
        self.controller = MockController()

    def create_sensor(self, data_type, multiplier=1):
        return SolisBaseSensor(
            hass=None,
            controller=self.controller,
            unique_id="test_sensor",
            name="Test Sensor",
            registrars=[33029, 33030],  # two registers -> 32-bit path
            write_register=None,
            multiplier=multiplier,
            data_type=data_type,
        )

    def test_default_two_register_is_signed(self):
        # No data_type -> historical signed behaviour preserved.
        sensor = self.create_sensor(data_type=None)
        # high word 0x9C40 has bit 15 set -> negative under two's complement
        self.assertEqual(sensor._convert_raw_value([0x9C40, 0x0000]), -1673527296)
        self.assertEqual(sensor._convert_raw_value([0x0001, 0x0000]), 65536)

    def test_u32_never_negative(self):
        sensor = self.create_sensor(data_type=DataType.U32.value)
        # Same high-bit-set words now read as a large positive unsigned value.
        self.assertEqual(sensor._convert_raw_value([0x9C40, 0x0000]), 2621440000)
        self.assertEqual(sensor._convert_raw_value([0xFFFF, 0xFFFF]), 4294967295)
        self.assertEqual(sensor._convert_raw_value([0x0001, 0x0000]), 65536)

    def test_u32_enum_member_normalizes(self):
        sensor = self.create_sensor(data_type=DataType.U32)
        self.assertEqual(sensor.data_type, DataType.U32.value)
        self.assertEqual(sensor._convert_raw_value([0x8000, 0x0000]), 2147483648)

    def test_u32_with_multiplier(self):
        sensor = self.create_sensor(data_type=DataType.U32.value, multiplier=0.001)
        # 0x0001_86A0 = 100000 counts * 0.001 = 100.0 kWh
        self.assertAlmostEqual(sensor._convert_raw_value([0x0001, 0x86A0]), 100.0)


if __name__ == "__main__":
    unittest.main()
