"""Battery-current setpoints must not be hard-capped at 200 A.

The four battery-current numbers (43012/43013 and 43117/43118) declared ``"max": 200``.
That literal was dead for the entire life of the AMPERE derivation in ``adjust_max`` —
the derivation overwrote it unconditionally — until the #438 fix made a declared max
win. 200 A then became the effective ceiling for the first time, and Home Assistant
started rejecting ``number.set_value`` above it with ``ServiceValidationError``, which
also aborts any caller batching writes.

200 A is not a protocol limit (U16 at 0.1 A carries 6553.5 A) and not a hardware one: a
15 kW LV hybrid at 51.2 V needs ~293 A to reach its own nameplate. The battery already
publishes its real limit on the mirrors 33206/33207, so that is what bounds these now.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import UnitOfElectricCurrent, UnitOfPower

from custom_components.solis_modbus.const import DOMAIN, VALUES
from custom_components.solis_modbus.helpers import cache_save, notify_register_update
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors
from custom_components.solis_modbus.sensors.solis_base_sensor import (
    BATTERY_CURRENT_FLOOR,
    SolisBaseSensor,
)
from custom_components.solis_modbus.sensors.solis_number_sensor import SolisNumberEntity

CHARGE_REGISTERS = (43012, 43117)
DISCHARGE_REGISTERS = (43013, 43118)
BATTERY_CURRENT_REGISTERS = CHARGE_REGISTERS + DISCHARGE_REGISTERS

CHARGE_MIRROR = 33206
DISCHARGE_MIRROR = 33207


class _Hass:
    """Just enough hass for the register cache."""

    def __init__(self):
        self.data = {DOMAIN: {VALUES: {}}}


def _controller(wattage_chosen=15000):
    controller = MagicMock()
    controller.inverter_config.model = "S6-EH3P"
    controller.inverter_config.features = []
    controller.inverter_config.wattage_chosen = wattage_chosen
    controller.connection_id = "test-link"
    controller.device_id = 1
    controller.host = "127.0.0.1"
    return controller


def _sensor(hass, controller, register, max_value=None):
    return SolisBaseSensor(
        hass=hass,
        controller=controller,
        unique_id=f"u{register}",
        name=f"Register {register}",
        registrars=[register],
        write_register=register,
        multiplier=0.1,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        editable=True,
        step=0.1,
        min_value=0,
        max_value=max_value,
    )


class TestDefinitions:
    """The literal is gone from the shipped definitions."""

    @pytest.mark.parametrize("register", BATTERY_CURRENT_REGISTERS)
    def test_no_declared_max_on_battery_current(self, register):
        entity = next(e for g in hybrid_sensors for e in g["entities"] if e.get("register") == [str(register)])

        assert "max" not in entity, f"{entity['name']} declares a max; it must be resolved from the BMS mirror"

    @pytest.mark.parametrize("register", BATTERY_CURRENT_REGISTERS)
    def test_still_editable_with_a_min(self, register):
        """Removing the max must not have disturbed the rest of the definition."""
        entity = next(e for g in hybrid_sensors for e in g["entities"] if e.get("register") == [str(register)])

        assert entity["editable"] is True
        assert entity["min"] == 0
        assert entity["step"] == 0.1


class TestMirrorDerivedMax:
    def setup_method(self):
        self.hass = _Hass()
        self.controller = _controller(wattage_chosen=15000)

    @pytest.mark.parametrize("register", CHARGE_REGISTERS)
    def test_charge_registers_follow_the_charge_mirror(self, register):
        cache_save(self.hass, self.controller, CHARGE_MIRROR, 4000)  # 400.0 A
        sensor = _sensor(self.hass, self.controller, register)

        assert sensor.max_value == 400.0

    @pytest.mark.parametrize("register", DISCHARGE_REGISTERS)
    def test_discharge_registers_follow_the_discharge_mirror(self, register):
        cache_save(self.hass, self.controller, DISCHARGE_MIRROR, 3500)  # 350.0 A
        sensor = _sensor(self.hass, self.controller, register)

        assert sensor.max_value == 350.0

    def test_charge_and_discharge_mirrors_are_not_crossed(self):
        cache_save(self.hass, self.controller, CHARGE_MIRROR, 4000)
        cache_save(self.hass, self.controller, DISCHARGE_MIRROR, 1000)

        assert _sensor(self.hass, self.controller, 43012).max_value == 400.0
        assert _sensor(self.hass, self.controller, 43013).max_value == 100.0

    def test_a_mirror_below_the_floor_is_not_widened(self):
        """A BMS that reports 150 A means 150 A — the floor must not override it."""
        cache_save(self.hass, self.controller, CHARGE_MIRROR, 1500)
        sensor = _sensor(self.hass, self.controller, 43117)

        assert sensor.max_value == 150.0

    def test_the_mirror_is_read_live_not_frozen_at_construction(self):
        """Mirrors arrive asynchronously, long after the sensor was built."""
        sensor = _sensor(self.hass, self.controller, 43012)
        derived = sensor.max_value

        cache_save(self.hass, self.controller, CHARGE_MIRROR, 2930)

        assert derived != 293.0
        assert sensor.max_value == 293.0

    @pytest.mark.parametrize("absent", [None, 0])
    def test_an_absent_or_zero_mirror_falls_back(self, absent):
        """0 is 'not reported yet', not 'this battery accepts no current'."""
        if absent is not None:
            cache_save(self.hass, self.controller, CHARGE_MIRROR, absent)
        sensor = _sensor(self.hass, self.controller, 43012)

        assert sensor.max_value == round((15000 / 44) / 10) * 20

    def test_a_hass_without_a_cache_falls_back(self):
        """Construction paths that pass hass=None must not explode."""
        sensor = _sensor(None, self.controller, 43012)

        assert sensor.max_value == round((15000 / 44) / 10) * 20


class TestDerivedFallback:
    """Without a mirror, the inverter-rating derivation applies — floored at 200 A."""

    def setup_method(self):
        self.hass = _Hass()

    def test_a_15kw_rating_clears_the_reported_293a(self):
        sensor = _sensor(self.hass, _controller(wattage_chosen=15000), 43117)

        assert sensor.max_value >= 293

    def test_a_small_rating_is_floored(self):
        """round((3000/44)/10)*20 = 140 — below what 4.1.x allowed; don't regress."""
        sensor = _sensor(self.hass, _controller(wattage_chosen=3000), 43012)

        assert sensor.max_value == BATTERY_CURRENT_FLOOR

    def test_the_floor_does_not_leak_to_other_current_entities(self):
        """Only the four battery-current setpoints get the floor."""
        sensor = _sensor(self.hass, _controller(wattage_chosen=3000), 43102)

        assert sensor.max_value == round((3000 / 44) / 10) * 20


class TestIssue438DoesNotRegress:
    """Declared maxima on grid registers still win over the inverter rating."""

    def setup_method(self):
        self.hass = _Hass()
        self.controller = _controller(wattage_chosen=8000)

    @pytest.mark.parametrize(("register", "declared"), [(43074, 20000), (43291, 15000)])
    def test_export_limits_keep_their_declared_max(self, register, declared):
        sensor = SolisBaseSensor(
            hass=self.hass,
            controller=self.controller,
            unique_id="u",
            name="Backflow Power",
            registrars=[register],
            write_register=register,
            multiplier=100,
            unit_of_measurement=UnitOfPower.WATT,
            editable=True,
            max_value=declared,
        )

        assert sensor.max_value == declared

    def test_a_declared_max_on_a_battery_register_still_loses_to_the_bms(self):
        """The mirror is the authority for these four, declared or not."""
        cache_save(self.hass, self.controller, CHARGE_MIRROR, 4000)
        sensor = _sensor(self.hass, self.controller, 43012, max_value=200)

        assert sensor.max_value == 400.0


@pytest.mark.asyncio
class TestNumberEntityAdvertisesTheLiveMax:
    async def test_the_entity_reports_the_mirror(self, hass):
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        cache_save(hass, controller, CHARGE_MIRROR, 2930)
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))

        assert entity.native_max_value == 293.0

    async def test_the_entity_max_tracks_a_later_mirror_update(self, hass):
        """The reported bound moves without the entity being rebuilt."""
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))

        cache_save(hass, controller, CHARGE_MIRROR, 2930)

        assert entity.native_max_value == 293.0

    async def test_a_mirror_arriving_republishes_the_bounds(self, hass):
        """The mirror isn't one of the entity's own registers — it must still wake it."""
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))
        entity.hass = hass
        entity.entity_id = "number.battery_max_charge_current"
        await entity.async_added_to_hass()
        entity.schedule_update_ha_state = MagicMock()

        notify_register_update(hass, controller, CHARGE_MIRROR, 2930)
        await hass.async_block_till_done()

        entity.schedule_update_ha_state.assert_called()

    async def test_another_inverters_mirror_is_ignored(self, hass):
        """Two inverters on one logger must not rewrite each other's bounds."""
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))
        entity.hass = hass
        entity.entity_id = "number.battery_max_charge_current"
        await entity.async_added_to_hass()
        entity.schedule_update_ha_state = MagicMock()

        other = _controller(wattage_chosen=15000)
        other.host = "10.0.0.9"
        other.device_id = 1
        # Same signal (same connection id + slave), payload from a different host.
        notify_register_update(hass, other, CHARGE_MIRROR, 500)
        await hass.async_block_till_done()

        entity.schedule_update_ha_state.assert_not_called()

    async def test_a_restored_state_cannot_reinstate_an_old_ceiling(self, hass):
        """RestoreNumber restores the value; a stale 200 A bound must not come back."""
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        cache_save(hass, controller, CHARGE_MIRROR, 2930)
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))
        entity.hass = hass
        entity.entity_id = "number.battery_max_charge_current"
        restored = MagicMock()
        restored.native_value = 100.0
        restored.native_max_value = 200
        entity.async_get_last_number_data = AsyncMock(return_value=restored)

        await entity.async_added_to_hass()

        assert entity.native_value == 100.0
        assert entity.native_max_value == 293.0

    async def test_293a_is_writable_on_a_15kw_lv_hybrid(self, hass):
        """The reproduction: set_value 293 used to raise before reaching us."""
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        cache_save(hass, controller, CHARGE_MIRROR, 3000)
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))
        entity.schedule_update_ha_state = MagicMock()

        assert entity.native_min_value <= 293 <= entity.native_max_value

        entity.set_native_value(293)
        await hass.async_block_till_done()

        # 0.1 A scale: 293 A on the wire is 2930.
        controller.async_write_holding_register.assert_called_with(43117, 2930)
