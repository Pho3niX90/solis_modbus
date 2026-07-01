"""Conservative diagnostic categorisation: identity/version/clock registers are
demoted to DIAGNOSTIC, but real measurements tagged an Information category stay
on the main device page.
"""

import unittest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory

from custom_components.solis_modbus.data.enums import Category
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor


class MockController:
    def __init__(self):
        class MockConfig:
            model = "TEST"
            features = []
            wattage_chosen = 5000

        self.inverter_config = MockConfig()


class TestEntityCategory(unittest.TestCase):
    def setUp(self):
        self.controller = MockController()

    def make(self, category, device_class=None):
        return SolisBaseSensor(
            hass=None,
            controller=self.controller,
            unique_id="u",
            name="n",
            registrars=[33000],
            write_register=None,
            multiplier=1,
            device_class=device_class,
            category=category,
        )

    def test_identity_register_is_diagnostic(self):
        # Model No / Serial / versions / clock have no device_class.
        self.assertEqual(self.make(Category.BASIC_INFORMATION).entity_category, EntityCategory.DIAGNOSTIC)
        self.assertEqual(self.make(Category.DEVICE_INTERNAL_DATA).entity_category, EntityCategory.DIAGNOSTIC)

    def test_measurement_in_info_category_stays_primary(self):
        # e.g. Temperature is tagged BASIC_INFORMATION but is a real measurement.
        self.assertIsNone(self.make(Category.BASIC_INFORMATION, SensorDeviceClass.TEMPERATURE).entity_category)

    def test_other_categories_are_uncategorised(self):
        self.assertIsNone(self.make(Category.BATTERY_INFORMATION).entity_category)
        self.assertIsNone(self.make(None).entity_category)


if __name__ == "__main__":
    unittest.main()
