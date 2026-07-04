"""Static integrity checks over the hand-written sensor definition lists.

These catch the class of bug where two entities in the same list share a
``unique`` id (HA silently drops one) or where a group's registers are not the
contiguous ascending block the block-reader assumes.
"""

from collections import Counter

import pytest

from custom_components.solis_modbus.sensor_data.hybrid_sensors import (
    hybrid_sensors,
    hybrid_sensors_derived,
)
from custom_components.solis_modbus.sensor_data.string_sensors import (
    string_sensors,
    string_sensors_derived,
)


def _group_uniques(groups):
    """Yield every ``unique`` from a list of register-group dicts."""
    for group in groups:
        for entity in group.get("entities", []):
            if entity.get("type") == "reserve":
                continue
            unique = entity.get("unique")
            if unique:
                yield unique


def _flat_uniques(entities):
    """Yield every ``unique`` from a flat list of entity dicts (derived sensors)."""
    for entity in entities:
        if entity.get("type") == "reserve":
            continue
        unique = entity.get("unique")
        if unique:
            yield unique


@pytest.mark.parametrize(
    "name,uniques",
    [
        ("hybrid", list(_group_uniques(hybrid_sensors)) + list(_flat_uniques(hybrid_sensors_derived))),
        ("string", list(_group_uniques(string_sensors)) + list(_flat_uniques(string_sensors_derived))),
    ],
)
def test_no_duplicate_unique_ids(name, uniques):
    """A single inverter loads exactly one of these lists; a duplicate ``unique``
    inside a list makes HA drop one entity (see the 2999/36013 Model No clash)."""
    dupes = [u for u, count in Counter(uniques).items() if count > 1]
    assert not dupes, f"Duplicate unique ids in {name} sensor definitions: {dupes}"


@pytest.mark.parametrize("groups", [hybrid_sensors, string_sensors], ids=["hybrid", "string"])
def test_group_registers_are_contiguous_ascending(groups):
    """Each group is read as one Modbus block, so its registers must be an
    ascending, gap-free run starting at register_start."""
    offenders = []
    for group in groups:
        start = group.get("register_start")
        if start is None:
            continue
        regs = []
        for entity in group.get("entities", []):
            regs.extend(int(r) for r in entity.get("register", []))
        if not regs:
            continue
        expected = list(range(min(regs), max(regs) + 1))
        if sorted(regs) != expected or min(regs) != start:
            offenders.append((start, sorted(regs)))
    assert not offenders, f"Non-contiguous / mis-started register groups: {offenders}"
