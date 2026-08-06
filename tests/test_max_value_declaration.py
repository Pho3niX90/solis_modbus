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


class TestUndeclaredMaxUsesProtocolCeiling(unittest.TestCase):
    """Definitions that omit "max" fall back to what the register can carry.

    The unit no longer implies anything. Deriving from ``wattage_chosen`` because the
    entity happened to be in watts is what made a change aimed at one register silently
    retarget every other one.
    """

    def setUp(self):
        self.controller = MockController(wattage_chosen=8000)

    def test_watt_entity_without_max_is_not_capped_at_the_rating(self):
        sensor = _group(
            self.controller,
            {"name": "Some Power", "register": ["43100"], "unit_of_measurement": UnitOfPower.WATT, "editable": True, "multiplier": 10},
        ).sensors[0]
        self.assertEqual(sensor.max_value, 65535 * 10)

    def test_kilowatt_entity_without_max_uses_its_own_scale(self):
        sensor = _group(
            self.controller,
            {"name": "Some Power kW", "register": ["43101"], "unit_of_measurement": UnitOfPower.KILO_WATT, "editable": True, "multiplier": 0.1},
        ).sensors[0]
        self.assertAlmostEqual(sensor.max_value, 6553.5)

    def test_ampere_entity_without_max_no_longer_assumes_a_44v_bus(self):
        sensor = _group(
            self.controller,
            {
                "name": "Some Current",
                "register": ["43102"],
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "editable": True,
                "multiplier": 0.1,
            },
        ).sensors[0]
        self.assertAlmostEqual(sensor.max_value, 6553.5)
        self.assertNotEqual(sensor.max_value, round((8000 / 44) / 10) * 20)

    def test_signed_register_uses_the_signed_ceiling(self):
        sensor = _group(
            self.controller,
            {"name": "Signed", "register": ["43105"], "editable": True, "data_type": "S16", "multiplier": 10},
        ).sensors[0]
        self.assertEqual(sensor.max_value, 32767 * 10)

    def test_register_pair_without_a_data_type_decodes_as_s32(self):
        """Matches _convert_raw_value's own default for a two-register entity."""
        sensor = _group(
            self.controller,
            {"name": "Pair", "register": ["43106", "43107"], "editable": True, "multiplier": 1},
        ).sensors[0]
        self.assertEqual(sensor.max_value, 2147483647)

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
        self.assertEqual(sensor.max_value, 65535)


class TestInverterRatingIsOptIn(unittest.TestCase):
    """``wattage_chosen`` is only reachable through an explicit "max_source"."""

    def setUp(self):
        self.controller = MockController(wattage_chosen=20000)

    def test_declared_source_uses_the_rating(self):
        sensor = _group(
            self.controller,
            {
                "name": "RC Force Battery Charge Power",
                "register": ["43136"],
                "unit_of_measurement": UnitOfPower.WATT,
                "editable": True,
                "multiplier": 10,
                "min": 0,
                "max_source": "inverter_rating",
            },
        ).sensors[0]
        self.assertEqual(sensor.max_value, 20000)

    def test_a_signed_source_register_is_symmetric(self):
        """43128 must be able to export as far as it can import."""
        sensor = _group(
            self.controller,
            {
                "name": "RC Inverter AC Grid Active Power",
                "register": ["43128"],
                "unit_of_measurement": UnitOfPower.WATT,
                "editable": True,
                "data_type": "S16",
                "multiplier": 10,
                "min": -10000,
                "max_source": "inverter_rating",
            },
        ).sensors[0]
        self.assertEqual(sensor.max_value, 20000)
        self.assertEqual(sensor.min_value, -20000)

    def test_an_unusable_rating_falls_back_to_the_protocol_ceiling(self):
        """Never wrong-low: a missing rating must not collapse the bound."""
        sensor = _group(
            MockController(wattage_chosen=0),
            {
                "name": "RC Force Battery Charge Power",
                "register": ["43136"],
                "unit_of_measurement": UnitOfPower.WATT,
                "editable": True,
                "multiplier": 10,
                "min": 0,
                "max_source": "inverter_rating",
            },
        ).sensors[0]
        self.assertEqual(sensor.max_value, 65535 * 10)

    def test_a_kilowatt_source_register_scales_the_rating(self):
        sensor = _group(
            self.controller,
            {
                "name": "Some kW Limit",
                "register": ["43108"],
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "editable": True,
                "multiplier": 0.1,
                "max_source": "inverter_rating",
            },
        ).sensors[0]
        self.assertEqual(sensor.max_value, 20)


class TestInverterWattageCatalogue(unittest.TestCase):
    def test_s6_eh3p_covers_the_20k_sku(self):
        """S6-EH3P20K-H is a shipping SKU and was unrepresentable (issue #438)."""
        s6_eh3p = next(i for i in SOLIS_INVERTERS if i.model == "S6-EH3P")
        self.assertIn(20000, s6_eh3p.wattage)


if __name__ == "__main__":
    unittest.main()
