"""Multi-inverter isolation: per-entry runtime data keeps each inverter's
entities separate, and cross-entry iteration sees them all.
"""

from unittest.mock import MagicMock

from custom_components.solis_modbus.helpers import (
    get_controller_from_entry,
    iter_controllers,
    iter_platform_entities,
)
from custom_components.solis_modbus.runtime import SolisRuntimeData


def make_entry(controller=None, entities=None):
    entry = MagicMock()
    entry.runtime_data = SolisRuntimeData(controller=controller or MagicMock())
    entry.runtime_data.entities.update(entities or {})
    return entry


def make_hass(entries):
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = entries
    return hass


def test_entries_do_not_clobber_each_other():
    entry_a = make_entry(entities={"sensor": ["sensor_a"]})
    entry_b = make_entry(entities={"sensor": ["sensor_b"]})
    hass = make_hass([entry_a, entry_b])

    assert sorted(iter_platform_entities(hass, "sensor")) == ["sensor_a", "sensor_b"]
    # Each entry keeps its own list
    assert entry_a.runtime_data.entities["sensor"] == ["sensor_a"]
    assert entry_b.runtime_data.entities["sensor"] == ["sensor_b"]


def test_iteration_spans_platforms_and_skips_missing_runtime():
    entry_a = make_entry(entities={"sensor": ["s1"], "number": ["n1"]})
    entry_no_runtime = MagicMock(spec=[])  # not set up yet — no runtime_data attribute
    hass = make_hass([entry_a, entry_no_runtime])

    assert sorted(iter_platform_entities(hass, "sensor", "number")) == ["n1", "s1"]
    assert list(iter_platform_entities(hass, "time")) == []


def test_controller_lookup_via_runtime_data():
    controller_a, controller_b = MagicMock(), MagicMock()
    entry_a, entry_b = make_entry(controller_a), make_entry(controller_b)
    hass = make_hass([entry_a, entry_b])

    assert get_controller_from_entry(hass, entry_a) is controller_a
    assert list(iter_controllers(hass)) == [controller_a, controller_b]

    # unloaded entry (runtime_data cleared) yields nothing and returns None
    entry_a.runtime_data = None
    assert get_controller_from_entry(hass, entry_a) is None
    assert list(iter_controllers(hass)) == [controller_b]
