"""Issue #457: poll profiles (full / essential / extreme).

Extreme mode exists because a tight control loop needs a *small* register set
polled fast, not the whole map polled faster. Each sensor group is one Modbus
frame and the Solis spec requires >300ms between frames, so a full ~11-group
fast pass can never run at 2s — but two live groups can.

These tests pin down the three things that would silently break a user's
system: which groups each profile polls, that the pre-#457 `essential_only`
boolean still resolves correctly, and that the tighter interval floor is only
reachable from the profile that earns it.
"""

from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from custom_components.solis_modbus.config_flow import (
    BASE_CONFIG_SCHEMA,
    OPTIONS_SCHEMA,
    SOLIS_MODELS,
    _validate_poll_interval,
)
from custom_components.solis_modbus.const import (
    CONF_EXTREME_INCLUDE_BATTERY,
    CONF_POLL_PROFILE,
    POLL_INTERVAL_FAST_MIN,
    POLL_INTERVAL_FAST_MIN_EXTREME,
    POLL_PROFILE_ESSENTIAL,
    POLL_PROFILE_EXTREME,
    POLL_PROFILE_FULL,
    POLL_PROFILES,
)
from custom_components.solis_modbus.helpers import (
    derived_sensor_is_supported,
    extreme_includes_battery,
    get_poll_profile,
    group_in_poll_profile,
    is_essential_only,
    registers_declared_by,
)
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors, hybrid_sensors_derived

# Registers the extreme profile is specified to poll (#457): live PV, live
# meter/CT, and the ONCE identity groups so the device still identifies itself.
EXTREME_GROUPS = {33000, 35000, 33049, 33126}
EXTREME_BATTERY_GROUP = 33132


def _entry(data=None, options=None):
    entry = MagicMock()
    entry.data = data or {}
    entry.options = options or {}
    return entry


def _selected(profile, include_battery=False, groups=hybrid_sensors):
    return {g["register_start"] for g in groups if group_in_poll_profile(g, profile, include_battery)}


class TestGroupSelection:
    def test_extreme_selects_exactly_the_specified_groups(self):
        assert _selected(POLL_PROFILE_EXTREME) == EXTREME_GROUPS

    def test_extreme_battery_adds_only_the_battery_group(self):
        assert _selected(POLL_PROFILE_EXTREME, include_battery=True) == EXTREME_GROUPS | {EXTREME_BATTERY_GROUP}

    def test_extreme_includes_the_meter_group_essential_does_not(self):
        # 33126 carries meter voltage/current/active power — the signal an export
        # control loop actually needs, and the reason extreme is not simply a
        # subset of essential.
        assert 33126 in _selected(POLL_PROFILE_EXTREME)
        assert 33126 not in _selected(POLL_PROFILE_ESSENTIAL)

    def test_extreme_is_smaller_than_essential(self):
        assert len(_selected(POLL_PROFILE_EXTREME)) < len(_selected(POLL_PROFILE_ESSENTIAL))

    def test_full_selects_everything(self):
        assert _selected(POLL_PROFILE_FULL) == {g["register_start"] for g in hybrid_sensors}

    def test_no_profile_polls_holding_register_groups_except_full(self):
        # 43xxx/44xxx are settings groups; polling them in a reduced profile would
        # defeat the point and re-create the writable entities we deliberately skip.
        for profile in (POLL_PROFILE_ESSENTIAL, POLL_PROFILE_EXTREME):
            assert all(reg < 40000 for reg in _selected(profile)), profile

    def test_extreme_frame_budget_fits_the_two_second_floor(self):
        # >300ms mandatory spacing per frame; the live groups are what recur at the
        # fast interval (identity groups are ONCE), so the recurring cost must fit.
        live = {g for g in _selected(POLL_PROFILE_EXTREME, include_battery=True) if g not in (33000, 35000)}
        assert len(live) * 0.3 < POLL_INTERVAL_FAST_MIN_EXTREME


class TestProfileResolution:
    def test_defaults_to_full(self):
        assert get_poll_profile(_entry()) == POLL_PROFILE_FULL

    def test_reads_explicit_profile(self):
        assert get_poll_profile(_entry(data={CONF_POLL_PROFILE: POLL_PROFILE_EXTREME})) == POLL_PROFILE_EXTREME

    def test_options_override_data(self):
        entry = _entry(data={CONF_POLL_PROFILE: POLL_PROFILE_FULL}, options={CONF_POLL_PROFILE: POLL_PROFILE_EXTREME})
        assert get_poll_profile(entry) == POLL_PROFILE_EXTREME

    @pytest.mark.parametrize(
        ("essential_only", "expected"),
        [(True, POLL_PROFILE_ESSENTIAL), (False, POLL_PROFILE_FULL)],
    )
    def test_falls_back_to_legacy_boolean(self, essential_only, expected):
        # An entry that has not migrated yet, or one whose stale option survived,
        # must keep polling the subset the user chose.
        assert get_poll_profile(_entry(data={"essential_only": essential_only})) == expected

    def test_explicit_profile_wins_over_legacy_boolean(self):
        entry = _entry(data={"essential_only": True, CONF_POLL_PROFILE: POLL_PROFILE_FULL})
        assert get_poll_profile(entry) == POLL_PROFILE_FULL

    def test_unknown_profile_value_falls_back(self):
        assert get_poll_profile(_entry(data={CONF_POLL_PROFILE: "nonsense"})) == POLL_PROFILE_FULL

    @pytest.mark.parametrize(
        ("profile", "expected"),
        [(POLL_PROFILE_FULL, False), (POLL_PROFILE_ESSENTIAL, True), (POLL_PROFILE_EXTREME, True)],
    )
    def test_is_essential_only_means_any_reduced_profile(self, profile, expected):
        # The write platforms gate on this: neither reduced profile polls the
        # 43xxx groups, so writable entities would sit permanently unknown.
        assert is_essential_only(_entry(data={CONF_POLL_PROFILE: profile})) is expected

    def test_battery_opt_in_defaults_off(self):
        assert extreme_includes_battery(_entry()) is False
        assert extreme_includes_battery(_entry(options={CONF_EXTREME_INCLUDE_BATTERY: True})) is True


class TestPollIntervalFloor:
    @pytest.mark.parametrize("profile", [POLL_PROFILE_FULL, POLL_PROFILE_ESSENTIAL])
    def test_non_extreme_profiles_keep_the_default_floor(self, profile):
        assert _validate_poll_interval({CONF_POLL_PROFILE: profile, "poll_interval_fast": 2}) == "poll_interval_below_floor"
        assert _validate_poll_interval({CONF_POLL_PROFILE: profile, "poll_interval_fast": POLL_INTERVAL_FAST_MIN}) is None

    def test_extreme_allows_the_tighter_floor(self):
        cfg = {CONF_POLL_PROFILE: POLL_PROFILE_EXTREME, "poll_interval_fast": POLL_INTERVAL_FAST_MIN_EXTREME}
        assert _validate_poll_interval(cfg) is None

    def test_nothing_goes_below_the_extreme_floor(self):
        cfg = {CONF_POLL_PROFILE: POLL_PROFILE_EXTREME, "poll_interval_fast": 1}
        assert _validate_poll_interval(cfg) == "poll_interval_below_floor"

    def test_missing_interval_is_not_an_error(self):
        assert _validate_poll_interval({CONF_POLL_PROFILE: POLL_PROFILE_EXTREME}) is None

    def test_schema_floor_is_the_extreme_minimum(self):
        # The schema can't vary by profile (both fields are on the same form), so it
        # declares the loosest floor and _validate_poll_interval enforces the rest.
        base = vol.Schema(dict(BASE_CONFIG_SCHEMA), extra=vol.ALLOW_EXTRA)
        common = {"connection_type": "tcp", "inverter_serial": "T1", "slave": 1, "model": next(iter(SOLIS_MODELS))}
        assert base({**common, "poll_interval_fast": POLL_INTERVAL_FAST_MIN_EXTREME})["poll_interval_fast"] == POLL_INTERVAL_FAST_MIN_EXTREME
        with pytest.raises(vol.Invalid):
            base({**common, "poll_interval_fast": 1})


class TestDerivedSensorFiltering:
    """Derived sensors are computed from other groups' registers.

    Under a reduced profile they have to be filtered too, or they are created and
    then never receive a value — the exact "created but permanently unknown" state
    the profiles exist to avoid.
    """

    def _supported(self, profile, include_battery=False):
        selected = [g for g in hybrid_sensors if group_in_poll_profile(g, profile, include_battery)]
        polled = registers_declared_by(selected)
        known = registers_declared_by(hybrid_sensors)
        return {e["name"] for e in hybrid_sensors_derived if derived_sensor_is_supported(e, polled, known)}

    def test_full_profile_keeps_every_derived_sensor(self):
        assert self._supported(POLL_PROFILE_FULL) == {e["name"] for e in hybrid_sensors_derived}

    def test_extreme_drops_derived_sensors_whose_sources_are_not_polled(self):
        supported = self._supported(POLL_PROFILE_EXTREME)
        # Power Factor reads 33079-33082 (group 33070), which extreme does not poll.
        assert "Power Factor" not in supported
        assert "Grid Power Net" not in supported  # 33263/33264, group 33251

    def test_extreme_keeps_derived_sensors_built_on_polled_registers(self):
        supported = self._supported(POLL_PROFILE_EXTREME)
        # PV Power 1 reads 33049/33050 — squarely inside the live PV group.
        assert "PV Power 1" in supported

    def test_synthetic_and_literal_registers_do_not_block_a_derived_sensor(self):
        # "Last Modbus Success" reads 90006, which no group declares; literal
        # direction flags (0/1) are the same shape. Neither is a real source, so
        # neither should exclude the entity.
        assert "Last Modbus Success" in self._supported(POLL_PROFILE_EXTREME)

    def test_battery_derived_sensors_follow_the_battery_opt_in(self):
        without = self._supported(POLL_PROFILE_EXTREME, include_battery=False)
        with_batt = self._supported(POLL_PROFILE_EXTREME, include_battery=True)
        assert "Battery Power Net" not in without
        assert "Battery Power Net" in with_batt

    def test_reduced_profiles_never_keep_more_than_full(self):
        full = self._supported(POLL_PROFILE_FULL)
        for profile in (POLL_PROFILE_ESSENTIAL, POLL_PROFILE_EXTREME):
            assert self._supported(profile) <= full


class TestMigrationFromEssentialOnly:
    """v4 -> v5 folds the `essential_only` boolean into the profile select."""

    def _migrate(self, data, options=None):
        from custom_components.solis_modbus import _migrate_essential_only_to_poll_profile

        hass = MagicMock()
        entry = _entry(data=data, options=options)
        captured = {}

        def update(target, **kwargs):
            captured.update(kwargs)
            target.data = kwargs.get("data", target.data)
            target.options = kwargs.get("options", target.options)

        hass.config_entries.async_update_entry.side_effect = update
        _migrate_essential_only_to_poll_profile(hass, entry)
        return entry, captured

    @pytest.mark.parametrize(
        ("essential_only", "expected"),
        [(True, POLL_PROFILE_ESSENTIAL), (False, POLL_PROFILE_FULL)],
    )
    def test_boolean_becomes_profile(self, essential_only, expected):
        entry, _ = self._migrate({"essential_only": essential_only})
        assert entry.data[CONF_POLL_PROFILE] == expected

    def test_legacy_key_is_removed_from_both_data_and_options(self):
        # Setup merges {**data, **options}: a surviving option would shadow the
        # migrated data key and quietly restore the old behaviour.
        entry, _ = self._migrate({"essential_only": True}, options={"essential_only": True})
        assert "essential_only" not in entry.data
        assert "essential_only" not in entry.options

    def test_option_set_alone_still_migrates(self):
        entry, _ = self._migrate({}, options={"essential_only": True})
        assert entry.data[CONF_POLL_PROFILE] == POLL_PROFILE_ESSENTIAL

    def test_entry_with_no_setting_becomes_full(self):
        entry, _ = self._migrate({})
        assert entry.data[CONF_POLL_PROFILE] == POLL_PROFILE_FULL

    def test_already_migrated_entry_is_left_alone(self):
        hass = MagicMock()
        entry = _entry(data={CONF_POLL_PROFILE: POLL_PROFILE_EXTREME})
        from custom_components.solis_modbus import _migrate_essential_only_to_poll_profile

        _migrate_essential_only_to_poll_profile(hass, entry)
        hass.config_entries.async_update_entry.assert_not_called()

    def test_other_config_keys_survive(self):
        entry, _ = self._migrate({"essential_only": True, "host": "10.0.0.5", "slave": 3})
        assert entry.data["host"] == "10.0.0.5"
        assert entry.data["slave"] == 3


def test_string_inverters_have_no_extreme_groups_yet():
    """Justifies the fallback in async_setup_entry.

    Extreme is mapped for hybrid groups only (#457 question 4 defers string to a
    follow-up). Without a fallback, a string user selecting extreme would set up
    an entry with zero sensor groups, which reads as a broken integration rather
    than an unsupported option.
    """
    from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors

    assert _selected(POLL_PROFILE_EXTREME, groups=string_sensors) == set()
    assert _selected(POLL_PROFILE_ESSENTIAL, groups=string_sensors), "fallback target must not be empty"


class TestSchemaOptions:
    def test_both_schemas_offer_every_profile(self):
        base_keys = {str(k.schema): k for k in BASE_CONFIG_SCHEMA}
        options_keys = {str(k.schema): k for k in OPTIONS_SCHEMA.schema}
        for keys in (base_keys, options_keys):
            assert CONF_POLL_PROFILE in keys
            assert CONF_EXTREME_INCLUDE_BATTERY in keys
        assert set(POLL_PROFILES) == {POLL_PROFILE_FULL, POLL_PROFILE_ESSENTIAL, POLL_PROFILE_EXTREME}

    def test_profile_values_are_rejected_when_unknown(self):
        schema = vol.Schema(dict(BASE_CONFIG_SCHEMA), extra=vol.ALLOW_EXTRA)
        common = {"connection_type": "tcp", "inverter_serial": "T1", "slave": 1, "model": next(iter(SOLIS_MODELS))}
        with pytest.raises(vol.Invalid):
            schema({**common, CONF_POLL_PROFILE: "turbo"})


def test_migration_strips_a_stale_boolean_from_an_already_migrated_entry():
    """A v4 entry can hold both keys; the dead one must not survive.

    Setup merges {**data, **options}, so leaving `essential_only` behind is the
    same shadowing hazard the migration exists to remove.
    """
    from custom_components.solis_modbus import _migrate_essential_only_to_poll_profile

    hass = MagicMock()
    entry = _entry(data={CONF_POLL_PROFILE: POLL_PROFILE_EXTREME, "essential_only": True})

    def update(target, **kwargs):
        target.data = kwargs.get("data", target.data)
        target.options = kwargs.get("options", target.options)

    hass.config_entries.async_update_entry.side_effect = update
    _migrate_essential_only_to_poll_profile(hass, entry)

    assert entry.data[CONF_POLL_PROFILE] == POLL_PROFILE_EXTREME  # chosen profile preserved
    assert "essential_only" not in entry.data
