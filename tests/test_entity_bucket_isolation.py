"""Multi-inverter isolation: entity buckets are keyed per config entry and the
_iter_entities consumer helper tolerates both the per-entry dict and legacy list.
"""

from custom_components.solis_modbus.helpers import _iter_entities


def test_iter_entities_dict_of_lists():
    bucket = {"entry_a": ["a1", "a2"], "entry_b": ["b1"]}
    assert sorted(_iter_entities(bucket)) == ["a1", "a2", "b1"]


def test_iter_entities_legacy_flat_list():
    assert list(_iter_entities(["x", "y"])) == ["x", "y"]


def test_iter_entities_none_and_empty():
    assert list(_iter_entities(None)) == []
    assert list(_iter_entities({})) == []
    assert list(_iter_entities([])) == []


def test_per_entry_buckets_do_not_clobber():
    """Two entries writing into the same bucket both survive (the bug was a flat
    overwrite where the second inverter replaced the first)."""
    bucket = {}
    bucket.setdefault("entry_a", ["sensor_a"])
    bucket.setdefault("entry_b", ["sensor_b"])
    assert set(bucket) == {"entry_a", "entry_b"}
    assert sorted(_iter_entities(bucket)) == ["sensor_a", "sensor_b"]
    # Unload of entry_a leaves entry_b intact.
    bucket.pop("entry_a", None)
    assert list(_iter_entities(bucket)) == ["sensor_b"]
