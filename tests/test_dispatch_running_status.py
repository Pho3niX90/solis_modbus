"""Remote Dispatch running status (input 34504).

Requested in #440: the running-status register is worth exposing on its own, even
without any write support, because it tells you whether an external controller is
currently dispatching the inverter.
"""

from custom_components.solis_modbus.data.enums import Category, PollSpeed
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors


def _groups_containing(register: str):
    return [g for g in hybrid_sensors for e in g.get("entities", []) if register in e.get("register", [])]


def _entity(register: str):
    for group in hybrid_sensors:
        for entity in group.get("entities", []):
            if register in entity.get("register", []):
                return group, entity
    raise AssertionError(f"no entity defined for register {register}")


def test_running_status_register_is_defined():
    _, entity = _entity("34504")
    assert entity["name"] == "Remote Dispatch Running Status"
    assert entity["category"] == Category.REMOTE_DISPATCH_SETTING
    assert entity["unique"] == "solis_modbus_inverter_remote_dispatch_running_status"


def test_running_status_has_its_own_group():
    """It must not share the capability group — those flags are polled ONCE."""
    group, _ = _entity("34504")
    assert group["register_start"] == 34504
    registers = [r for e in group["entities"] for r in e["register"]]
    assert registers == ["34504"]

    capability_group, _ = _entity("34502")
    assert capability_group["poll_speed"] == PollSpeed.ONCE
    assert group is not capability_group


def test_running_status_is_polled_repeatedly():
    """A ONCE poll would freeze it at whatever it read during startup."""
    group, _ = _entity("34504")
    assert group["poll_speed"] in (PollSpeed.FAST, PollSpeed.NORMAL, PollSpeed.SLOW)


def test_capability_flags_stay_polled_once():
    """Guard the flip side: 34502/34503 are fixed per firmware, don't re-poll them."""
    group, _ = _entity("34502")
    registers = sorted(r for e in group["entities"] for r in e["register"])
    assert registers == ["34502", "34503"]
    assert group["poll_speed"] == PollSpeed.ONCE


def test_register_is_defined_exactly_once():
    assert len(_groups_containing("34504")) == 1
