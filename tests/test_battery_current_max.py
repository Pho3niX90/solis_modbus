"""Battery-current setpoints: static bounds, advisory BMS limit.

Two generations of regressions meet here:

* ``"max": 200`` (and 135/300 on the TOU/time-charging currents) rejected legitimate
  writes — a 15 kW LV hybrid at 51.2 V needs ~293 A, a parallel pair reports 580 A
  (#351, #455). No literal survives contact with the fleet.
* Replacing the literal with the live BMS mirror (33206/33207) made the bound *move*:
  a real BMS derates with SOC, so the state ended up above its own max and automation
  writes intermittently raised out_of_range (#467); on some firmware the mirror echoes
  the setpoint back, so lowering the value ratcheted the max down one-way (#464).

The resolution: the advertised max is the *static* protocol ceiling (what the register
can carry — never wrong-low), and the mirror is surfaced as an advisory
``device_limit`` attribute plus a log warning on write, never enforced.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import UnitOfElectricCurrent, UnitOfPower

from custom_components.solis_modbus.const import DOMAIN, VALUES
from custom_components.solis_modbus.helpers import cache_save, notify_register_update
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor
from custom_components.solis_modbus.sensors.solis_number_sensor import SolisNumberEntity

CHARGE_REGISTERS = (43012, 43117)
DISCHARGE_REGISTERS = (43013, 43118)
BATTERY_CURRENT_REGISTERS = CHARGE_REGISTERS + DISCHARGE_REGISTERS

# The time-charging and TOU slot currents, brought under the same mirror. Their old
# literals (135 A / 300 A) sat below a 15 kW LV bank's ~293 A and the 580 A a parallel
# pair reports.
EXTENDED_CHARGE_REGISTERS = (43141, 43709, 43716, 43723, 43730, 43737, 43744)
EXTENDED_DISCHARGE_REGISTERS = (43142, 43751, 43758, 43765, 43772, 43779, 43786)

CHARGE_MIRROR = 33206
DISCHARGE_MIRROR = 33207

# U16 on a 0.1 A scale — the static ceiling for every battery-current setpoint.
PROTOCOL_CURRENT_MAX = 6553.5


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

        assert "max" not in entity, f"{entity['name']} declares a max; no literal survives contact with the fleet"

    @pytest.mark.parametrize("register", BATTERY_CURRENT_REGISTERS)
    def test_still_editable_with_a_min(self, register):
        """Removing the max must not have disturbed the rest of the definition."""
        entity = next(e for g in hybrid_sensors for e in g["entities"] if e.get("register") == [str(register)])

        assert entity["editable"] is True
        assert entity["min"] == 0
        assert entity["step"] == 0.1


class TestTheAdvertisedMaxIsStatic:
    """#464/#467: the bound must not track the mirror, whatever the mirror does."""

    def setup_method(self):
        self.hass = _Hass()
        self.controller = _controller(wattage_chosen=15000)

    @pytest.mark.parametrize("register", BATTERY_CURRENT_REGISTERS)
    def test_the_max_is_the_protocol_ceiling(self, register):
        assert _sensor(self.hass, self.controller, register).max_value == pytest.approx(PROTOCOL_CURRENT_MAX)

    @pytest.mark.parametrize("register", CHARGE_REGISTERS)
    def test_a_derated_mirror_cannot_lower_the_max(self, register):
        """#467: a Dyness HV at 12% SOC reports ~18 A — the bound must not follow."""
        cache_save(self.hass, self.controller, CHARGE_MIRROR, 184)  # 18.4 A
        sensor = _sensor(self.hass, self.controller, register)

        assert sensor.max_value == pytest.approx(PROTOCOL_CURRENT_MAX)

    def test_a_setpoint_echo_cannot_ratchet_the_max(self):
        """#464: firmware that mirrors the setpoint back must not shrink the range.

        The reproduction: set 2 A, the mirror reports 2 A shortly after, and with the
        old resolution the entity would never accept anything above 2 A again.
        """
        sensor = _sensor(self.hass, self.controller, 43117)
        cache_save(self.hass, self.controller, CHARGE_MIRROR, 20)  # the echoed 2.0 A

        assert sensor.max_value == pytest.approx(PROTOCOL_CURRENT_MAX)
        assert sensor.min_value <= 50 <= sensor.max_value  # raising it back stays valid

    def test_a_580a_parallel_pair_stays_writable(self):
        """#351: the case the mirror bound was built for still fits under the ceiling."""
        sensor = _sensor(self.hass, self.controller, 43012)

        assert sensor.min_value <= 580 <= sensor.max_value

    @pytest.mark.parametrize("register", EXTENDED_CHARGE_REGISTERS + EXTENDED_DISCHARGE_REGISTERS)
    def test_time_and_tou_currents_share_the_static_ceiling(self, register):
        """Scheduled config (#467 point 2): the range must not depend on when you look."""
        cache_save(self.hass, self.controller, CHARGE_MIRROR, 184)
        cache_save(self.hass, self.controller, DISCHARGE_MIRROR, 184)

        assert _sensor(self.hass, self.controller, register).max_value == pytest.approx(PROTOCOL_CURRENT_MAX)


class TestAdvisoryDeviceLimit:
    """The mirror survives as information: device_limit, live, per direction."""

    def setup_method(self):
        self.hass = _Hass()
        self.controller = _controller(wattage_chosen=15000)

    @pytest.mark.parametrize("register", CHARGE_REGISTERS + EXTENDED_CHARGE_REGISTERS)
    def test_charge_registers_report_the_charge_mirror(self, register):
        cache_save(self.hass, self.controller, CHARGE_MIRROR, 4000)  # 400.0 A
        sensor = _sensor(self.hass, self.controller, register)

        assert sensor.device_limit == 400.0
        assert sensor.device_limit_source == "bms"

    @pytest.mark.parametrize("register", DISCHARGE_REGISTERS + EXTENDED_DISCHARGE_REGISTERS)
    def test_discharge_registers_report_the_discharge_mirror(self, register):
        cache_save(self.hass, self.controller, DISCHARGE_MIRROR, 3500)  # 350.0 A
        sensor = _sensor(self.hass, self.controller, register)

        assert sensor.device_limit == 350.0
        assert sensor.device_limit_source == "bms"

    def test_charge_and_discharge_mirrors_are_not_crossed(self):
        cache_save(self.hass, self.controller, CHARGE_MIRROR, 4000)
        cache_save(self.hass, self.controller, DISCHARGE_MIRROR, 1000)

        assert _sensor(self.hass, self.controller, 43012).device_limit == 400.0
        assert _sensor(self.hass, self.controller, 43013).device_limit == 100.0

    def test_the_limit_is_read_live_not_frozen_at_construction(self):
        """Mirrors arrive asynchronously, long after the sensor was built."""
        sensor = _sensor(self.hass, self.controller, 43012)
        assert sensor.device_limit is None

        cache_save(self.hass, self.controller, CHARGE_MIRROR, 2930)

        assert sensor.device_limit == 293.0

    @pytest.mark.parametrize("absent", [None, 0])
    def test_an_absent_or_zero_mirror_reports_no_limit(self, absent):
        """0 is 'not reported yet', not 'this battery accepts no current'."""
        if absent is not None:
            cache_save(self.hass, self.controller, CHARGE_MIRROR, absent)

        assert _sensor(self.hass, self.controller, 43012).device_limit is None

    def test_a_hass_without_a_cache_reports_no_limit(self):
        """Construction paths that pass hass=None must not explode."""
        sensor = _sensor(None, self.controller, 43012)

        assert sensor.device_limit is None
        assert sensor.max_value == pytest.approx(PROTOCOL_CURRENT_MAX)

    def test_a_plain_register_has_no_limit_source(self):
        sensor = SolisBaseSensor(
            hass=self.hass,
            controller=self.controller,
            unique_id="u",
            name="Backflow Power",
            registrars=[43074],
            write_register=43074,
            multiplier=100,
            unit_of_measurement=UnitOfPower.WATT,
            editable=True,
            max_value=20000,
        )

        assert sensor.device_limit is None
        assert sensor.device_limit_source is None


class TestIssue438DoesNotRegress:
    """Declared maxima on grid registers still win over everything derived."""

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


@pytest.mark.asyncio
class TestNumberEntity:
    async def test_the_entity_advertises_the_static_ceiling(self, hass):
        """#467: an 18.4 A mirror must not become the entity's max."""
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        cache_save(hass, controller, CHARGE_MIRROR, 184)
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))

        assert entity.native_max_value == pytest.approx(PROTOCOL_CURRENT_MAX)

    async def test_the_entity_surfaces_the_limit_as_an_attribute(self, hass):
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        cache_save(hass, controller, CHARGE_MIRROR, 2930)
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))

        assert entity.extra_state_attributes == {"device_limit": 293.0, "device_limit_source": "bms"}

    async def test_the_attribute_tracks_a_later_mirror_update(self, hass):
        """The advisory limit moves without the entity being rebuilt."""
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))
        assert entity.extra_state_attributes["device_limit"] is None

        cache_save(hass, controller, CHARGE_MIRROR, 2930)

        assert entity.extra_state_attributes["device_limit"] == 293.0

    async def test_a_mirror_arriving_republishes_the_attributes(self, hass):
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
        """Two inverters on one logger must not rewrite each other's attributes."""
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
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))
        entity.hass = hass
        entity.entity_id = "number.battery_max_charge_current"
        restored = MagicMock()
        restored.native_value = 100.0
        restored.native_max_value = 200
        entity.async_get_last_number_data = AsyncMock(return_value=restored)

        await entity.async_added_to_hass()

        assert entity.native_value == 100.0
        assert entity.native_max_value == pytest.approx(PROTOCOL_CURRENT_MAX)

    async def test_293a_is_writable_on_a_15kw_lv_hybrid(self, hass):
        """The #455 reproduction: set_value 293 used to raise before reaching us."""
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

    async def test_a_write_above_a_derated_limit_goes_through_with_a_warning(self, hass, caplog):
        """#467 (Valiante): 60 A into a momentarily derated pack must not raise."""
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        cache_save(hass, controller, CHARGE_MIRROR, 184)  # BMS says 18.4 A right now
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43141))
        entity.schedule_update_ha_state = MagicMock()

        assert entity.native_min_value <= 60 <= entity.native_max_value

        with caplog.at_level(logging.WARNING):
            entity.set_native_value(60)
        await hass.async_block_till_done()

        controller.async_write_holding_register.assert_called_with(43141, 600)
        assert any("18.4" in r.getMessage() for r in caplog.records)

    async def test_a_write_within_the_limit_does_not_warn(self, hass, caplog):
        hass.data.setdefault(DOMAIN, {}).setdefault(VALUES, {})
        controller = _controller(wattage_chosen=15000)
        cache_save(hass, controller, CHARGE_MIRROR, 3000)
        entity = SolisNumberEntity(hass, _sensor(hass, controller, 43117))
        entity.schedule_update_ha_state = MagicMock()

        with caplog.at_level(logging.WARNING):
            entity.set_native_value(50)
        await hass.async_block_till_done()

        controller.async_write_holding_register.assert_called_with(43117, 500)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
