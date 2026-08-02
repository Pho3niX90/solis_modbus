"""Every sensor definition must construct for every inverter feature set.

This is a guard against a class of bug rather than a specific one. v4.2.0
shipped a crash that only appeared on HV-battery hardware: new amp-denominated
sensors landed on registers that a model-specific branch narrowed the step for,
and the step could be None. Nobody could have caught it by running the
integration, because it needs an HV battery to reach the branch at all
(#445, #446, #447).

Sensor definitions are static data, so the whole matrix can be built in-process
without any hardware. If a definition and a feature branch ever disagree again,
this fails in CI instead of on a user's inverter.
"""

import itertools
from unittest.mock import MagicMock

import pytest

from custom_components.solis_modbus.data.enums import InverterType
from custom_components.solis_modbus.data.solis_config import (
    SOLIS_INVERTERS,
    InverterConfig,
    InverterOptions,
)
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors
from custom_components.solis_modbus.sensor_data.string_sensors import string_sensors
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup

# The options a user can actually toggle, which is what decides the feature set.
TOGGLES = ("hv_battery", "ac_coupling", "parallel", "dual_meter", "epm", "generator")


def _controller(**options):
    controller = MagicMock()
    config = InverterConfig(
        model="S6-EH3P",
        wattage=[10000],
        phases=3,
        type=InverterType.HYBRID,
        options=InverterOptions(**options),
    )
    config.wattage_chosen = 10000
    controller.inverter_config = config
    return controller


def _all_groups():
    """Only the polled register groups.

    Derived sensors are computed from other entities and never go through
    SolisSensorGroup, so they have no registers to build a group from.
    """
    return list(hybrid_sensors) + list(string_sensors)


def _build(controller, group):
    """Build one group the way async_setup_entry does."""
    return SolisSensorGroup(hass=MagicMock(), definition=group, controller=controller, identification=None)


@pytest.mark.parametrize("hv_battery", [True, False], ids=["hv", "lv"])
def test_every_group_builds_for_hv_and_lv(hv_battery):
    """The exact shape of the v4.2.0 regression: HV-only code paths."""
    controller = _controller(hv_battery=hv_battery)
    failures = []

    for group in _all_groups():
        try:
            _build(controller, group)
        except Exception as error:  # noqa: BLE001 - collecting, not handling
            name = group.get("name", group.get("register_start", "?"))
            failures.append(f"{name}: {type(error).__name__}: {error}")

    assert not failures, "sensor groups failed to build:\n  " + "\n  ".join(failures)


@pytest.mark.parametrize(
    "combo",
    list(itertools.product([True, False], repeat=len(TOGGLES))),
    ids=lambda c: "".join(t[0].upper() if v else "-" for t, v in zip(TOGGLES, c)),
)
def test_every_group_builds_for_every_option_combination(combo):
    """All 64 combinations of the user-facing options."""
    controller = _controller(**dict(zip(TOGGLES, combo)))

    for group in _all_groups():
        try:
            _build(controller, group)
        except Exception as error:  # noqa: BLE001
            name = group.get("name", group.get("register_start", "?"))
            pytest.fail(f"{name} failed with {dict(zip(TOGGLES, combo))}: {error!r}")


@pytest.mark.parametrize("template", SOLIS_INVERTERS, ids=lambda t: t.model)
def test_every_shipped_inverter_model_builds(template):
    """Each model in SOLIS_INVERTERS, with HV battery on -- the risky path."""
    config = InverterConfig(
        model=template.model,
        wattage=list(template.wattage),
        phases=template.phases,
        type=template.type,
        options=InverterOptions(hv_battery=True),
    )
    config.wattage_chosen = template.wattage[0]
    controller = MagicMock()
    controller.inverter_config = config

    for group in _all_groups():
        try:
            _build(controller, group)
        except Exception as error:  # noqa: BLE001
            name = group.get("name", group.get("register_start", "?"))
            pytest.fail(f"{template.model} / {name}: {error!r}")


def test_no_sensor_ends_up_with_an_unusable_step():
    """A step must be a number or absent -- never something arithmetic breaks on.

    The v4.2.0 crash was `min(None, 0.1)`. Anything that leaves a step in a
    state later maths can't handle should fail here first.
    """
    bad = []

    for hv in (True, False):
        controller = _controller(hv_battery=hv)
        for group in _all_groups():
            for sensor in _build(controller, group)._sensors:
                if sensor.step is not None and not isinstance(sensor.step, (int, float)):
                    bad.append(f"{sensor.name} (hv={hv}): step={sensor.step!r}")

    assert not bad, "sensors with an unusable step:\n  " + "\n  ".join(bad)
