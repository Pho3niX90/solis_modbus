"""Storage Mode select (register 43110) — issue #413 redesign.

Value table cross-checked against SolisCloud field captures (issues #413/#82,
solax-modbus mode matrix, ha-solarman lookup): 33=Self-Use(+grid charge),
35=Self-Use+TOU, 49=Reserve, 51=Reserve+TOU, 96/98=Feed-in(+TOU), 2080=Peak.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.solis_modbus.data.solis_config import SOLIS_INVERTERS
from custom_components.solis_modbus.sensor_data.select_sensors import get_select_sensors
from custom_components.solis_modbus.sensors.solis_select_entity import SolisSelectEntity


def make_entity():
    inverter_config = next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH1P")
    definition = next(g for g in get_select_sensors(inverter_config) if g["register"] == 43110)
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.device_id = 1
    controller.connected.return_value = True
    controller.async_write_holding_register = AsyncMock()
    controller.device_serial_number = "SN123"
    controller.identification = None
    return SolisSelectEntity(MagicMock(), controller, definition)


# (register value, expected option) — cloud-verified combos, incl. grid-charge bit 5
STATE_TABLE = [
    (1, "Self-Use"),
    (33, "Self-Use"),  # #413 reporter's idle value (bit 5 = grid charge preserved)
    (3, "Self-Use + TOU"),
    (35, "Self-Use + TOU"),
    (17, "Reserve / Backup"),
    (49, "Reserve / Backup"),
    (51, "Reserve / Backup + TOU"),
    (64, "Feed-in Priority"),
    (96, "Feed-in Priority"),
    (98, "Feed-in Priority + TOU"),
    (4, "Off-Grid Operation"),
    (2048, "Peak Shaving"),
    (2080, "Peak Shaving"),  # EA1P cloud value = bits 5+11 (#413)
    (2082, "Peak Shaving"),  # degenerate leftover from the old select (stray TOU bit)
]


@pytest.mark.parametrize("value,expected", STATE_TABLE)
def test_current_option_resolution(value, expected):
    entity = make_entity()
    with patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=value):
        assert entity.current_option == expected, f"43110={value} ({value:#06x})"


@pytest.mark.parametrize(
    "start,option,expected_write",
    [
        # The #413 blocker: leaving "+ TOU" was impossible (35 -> Self-Use was a no-op)
        (35, "Self-Use", 33),
        # The #413 headline: Self-Use(+grid charge) -> Peak Shaving must be exactly 2080
        (33, "Peak Shaving", 2080),
        (35, "Peak Shaving", 2080),  # TOU bit must not survive (old code wrote 2082)
        (33, "Self-Use + TOU", 35),
        (33, "Reserve / Backup", 49),
        (33, "Reserve / Backup + TOU", 51),
        (33, "Feed-in Priority", 96),
        (2080, "Self-Use", 33),  # and back out of peak shaving
        # Independent modifier bits (3 wakeup, 8 forcecharge) must be preserved
        (33 | (1 << 3) | (1 << 8), "Peak Shaving", 2080 | (1 << 3) | (1 << 8)),
    ],
)
async def test_select_option_writes(start, option, expected_write):
    entity = make_entity()
    controller = entity._modbus_controller
    with (
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=start),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_save"),
    ):
        await entity.async_select_option(option)
    controller.async_write_holding_register.assert_awaited_once_with(43110, expected_write)


async def test_reselecting_current_mode_is_a_noop():
    entity = make_entity()
    controller = entity._modbus_controller
    with (
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=33),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_save"),
    ):
        await entity.async_select_option("Self-Use")
    controller.async_write_holding_register.assert_not_awaited()


def test_entity_renamed_but_unique_id_stable():
    inverter_config = next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH1P")
    definition = next(g for g in get_select_sensors(inverter_config) if g["register"] == 43110)
    assert definition["name"] == "Storage Mode"
    assert definition["unique"] == "select_entity_43110"
