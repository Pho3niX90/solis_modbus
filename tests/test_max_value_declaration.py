"""A declared "max" in a sensor definition must survive.

Regression cover for issue #438: the export power limit is a *grid-connection*
constraint, not an inverter-output one, so deriving its ceiling from the inverter's
rated wattage capped users below what their grid connection allows. An S6-EH3P20K-H
owner picking the config-flow default model (S6-EH1P, max wattage 8000) got a
0-8000 W export limit despite the definition declaring max 20000.
"""

import unittest

from homeassistant.const import UnitOfElectricCurrent, UnitOfPower

from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS
from custom_components.solis_modbus.sensors.solis_base_sensor import (
    DEFAULT_MAX_VALUE,
    SolisBaseSensor,
    SolisSensorGroup,
)


class MockController:
    def __init__(self, wattage_chosen=8000):
        class MockConfig:
            model = "TEST"
            features = []

        MockConfig.wattage_chosen = wattage_chosen
        self.inverter_config = MockConfig()
        self.device_serial_number = "SN438"
        self.identification = None
        self.host = "127.0.0.1"


def _group(controller, entity):
    return SolisSensorGroup(
        hass=None,
        definition={"register_start": int(entity["register"][0]), "entities": [entity]},
        controller=controller,
    )


class TestDeclaredMaxSurvives(unittest.TestCase):
    def setUp(self):
        # 8000 is the S6-EH1P ceiling that produced the 0-8000 W in the report.
        self.controller = MockController(wattage_chosen=8000)

    def test_declared_max_survives_on_watt_entity(self):
        """Backflow Power (43074) declares max 20000 — it must not be clamped to 8000."""
        sensor = _group(
            self.controller,
            {
                "name": "Backflow Power",
                "register": ["43074"],
                "unit_of_measurement": UnitOfPower.WATT,
                "editable": True,
                "multiplier": 100,
                "min": 0,
                "max": 20000,
            },
        ).sensors[0]
        self.assertEqual(sensor.max_value, 20000)

    def test_declared_max_survives_on_flexible_export(self):
        """Flexible Export Backflow Power (43291) declares max 15000."""
        sensor = _group(
            self.controller,
            {
                "name": "Flexible Export Backflow Power",
                "register": ["43291"],
                "unit_of_measurement": UnitOfPower.WATT,
                "editable": True,
                "multiplier": 100,
                "max": 15000,
            },
        ).sensors[0]
        self.assertEqual(sensor.max_value, 15000)

    def test_declared_max_survives_below_rating_too(self):
        """The rule is 'declared wins', not 'take the larger of the two'."""
        sensor = _group(
            self.controller,
            {
                "name": "Export Calibration",
                "register": ["43195"],
                "unit_of_measurement": UnitOfPower.WATT,
                "editable": True,
                "max": 1000,
            },
        ).sensors[0]
        self.assertEqual(sensor.max_value, 1000)


class TestUndeclaredMaxStillDerived(unittest.TestCase):
    """Definitions that omit "max" keep deriving one from the inverter rating."""

    def setUp(self):
        self.controller = MockController(wattage_chosen=8000)

    def test_watt_entity_without_max_uses_wattage(self):
        sensor = _group(
            self.controller,
            {"name": "Some Power", "register": ["43100"], "unit_of_measurement": UnitOfPower.WATT, "editable": True},
        ).sensors[0]
        self.assertEqual(sensor.max_value, 8000)

    def test_kilowatt_entity_without_max_scales(self):
        sensor = _group(
            self.controller,
            {"name": "Some Power kW", "register": ["43101"], "unit_of_measurement": UnitOfPower.KILO_WATT, "editable": True},
        ).sensors[0]
        self.assertEqual(sensor.max_value, 8)

    def test_ampere_entity_without_max_derives_current(self):
        sensor = _group(
            self.controller,
            {
                "name": "Some Current",
                "register": ["43102"],
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "editable": True,
            },
        ).sensors[0]
        self.assertEqual(sensor.max_value, round((8000 / 44) / 10) * 20)

    def test_unitless_entity_without_max_falls_back_to_default(self):
        sensor = _group(
            self.controller,
            {"name": "Some Setting", "register": ["43103"], "editable": True},
        ).sensors[0]
        self.assertEqual(sensor.max_value, DEFAULT_MAX_VALUE)

    def test_direct_construction_without_max_is_unaffected(self):
        sensor = SolisBaseSensor(
            hass=None,
            controller=self.controller,
            unique_id="u",
            name="n",
            registrars=[43104],
            write_register=None,
            multiplier=1,
            unit_of_measurement=UnitOfPower.WATT,
        )
        self.assertEqual(sensor.max_value, 8000)


class TestInverterWattageCatalogue(unittest.TestCase):
    def test_s6_eh3p_covers_the_20k_sku(self):
        """S6-EH3P20K-H is a shipping SKU and was unrepresentable (issue #438)."""
        s6_eh3p = next(i for i in SOLIS_INVERTERS if i.model == "S6-EH3P")
        self.assertIn(20000, s6_eh3p.wattage)


if __name__ == "__main__":
    unittest.main()
