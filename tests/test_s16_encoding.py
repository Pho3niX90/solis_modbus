import unittest
from unittest.mock import AsyncMock, MagicMock

from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor
from custom_components.solis_modbus.sensors.solis_number_sensor import SolisNumberEntity


class MockController:
    def __init__(self):
        class MockConfig:
            model = "TEST"
            features = []
            wattage_chosen = 5000

        self.inverter_config = MockConfig()
        self.host = "192.168.1.1"
        self.device_id = 1
        self.async_write_holding_register = AsyncMock()

    @property
    def device_info(self):
        return {}


def make_entity(data_type, multiplier=10):
    controller = MockController()
    sensor = MagicMock(spec=SolisBaseSensor)
    sensor.controller = controller
    sensor.name = "Test S16"
    sensor.registrars = [43133]
    sensor.write_register = 43133
    sensor.device_class = "power"
    sensor.unit_of_measurement = "W"
    sensor.state_class = "measurement"
    sensor.multiplier = multiplier
    sensor.min_value = -10000
    sensor.max_value = 10000
    sensor.step = 10
    sensor.enabled = True
    sensor.hidden = False
    sensor.unique_id = "test_s16"
    sensor.default = 0
    sensor.data_type = data_type

    hass = MagicMock()
    hass.bus.async_listen = MagicMock()

    entity = SolisNumberEntity(hass, sensor)
    entity.schedule_update_ha_state = MagicMock()
    return entity, controller


class TestS16Encoding(unittest.TestCase):
    def _written_value(self, controller):
        args, _ = controller.async_write_holding_register.call_args
        return args[1]

    def test_positive_value_unchanged(self):
        """Positive S16: register_value must not be altered."""
        entity, controller = make_entity("S16", multiplier=10)
        entity.set_native_value(1000)  # → register_value = 100, positive → no change
        written = self._written_value(controller)
        self.assertEqual(written, 100)

    def test_negative_value_two_complement(self):
        """Negative S16: -1000 W with multiplier 10 → register -100 → 0xFF9C (65436)."""
        entity, controller = make_entity("S16", multiplier=10)
        entity.set_native_value(-1000)
        written = self._written_value(controller)
        self.assertEqual(written, 65436)  # -100 & 0xFFFF

    def test_minus_one_unit(self):
        """-10 W (one step) → register -1 → 65535."""
        entity, controller = make_entity("S16", multiplier=10)
        entity.set_native_value(-10)
        written = self._written_value(controller)
        self.assertEqual(written, 65535)  # -1 & 0xFFFF

    def test_zero(self):
        """Zero stays zero."""
        entity, controller = make_entity("S16", multiplier=10)
        entity._attr_native_value = 100  # ensure value differs so write is triggered
        entity.set_native_value(0)
        written = self._written_value(controller)
        self.assertEqual(written, 0)

    def test_clamping_below_min(self):
        """Values below -32768 are clamped before two's complement."""
        entity, controller = make_entity("S16", multiplier=1)
        entity.set_native_value(-999999)
        written = self._written_value(controller)
        self.assertEqual(written, 32768)  # -32768 & 0xFFFF

    def test_clamping_above_max(self):
        """Values above 32767 are clamped."""
        entity, controller = make_entity("S16", multiplier=1)
        entity.set_native_value(999999)
        written = self._written_value(controller)
        self.assertEqual(written, 32767)

    def test_no_conversion_without_s16(self):
        """data_type=None: register_value written as-is (positive only registers)."""
        entity, controller = make_entity(None, multiplier=10)
        entity.set_native_value(500)
        written = self._written_value(controller)
        self.assertEqual(written, 50)

    def test_no_write_when_same_value(self):
        """set_native_value does nothing when value is unchanged."""
        entity, controller = make_entity("S16", multiplier=10)
        entity._attr_native_value = -1000
        entity.set_native_value(-1000)
        controller.async_write_holding_register.assert_not_called()


if __name__ == "__main__":
    unittest.main()
