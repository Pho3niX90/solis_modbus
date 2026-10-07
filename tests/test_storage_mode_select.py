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
    (17, "Self-Use + Reserve/Backup"),
    (49, "Self-Use + Reserve/Backup"),
    (51, "Self-Use + TOU + Reserve/Backup"),
    (64, "Feed-in Priority"),
    (96, "Feed-in Priority"),
    (98, "Feed-in Priority + TOU"),
    (80, "Feed-in Priority + Reserve/Backup"),
    (112, "Feed-in Priority + Reserve/Backup"),
    (82, "Feed-in Priority + TOU + Reserve/Backup"),
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
        (33, "Self-Use + Reserve/Backup", 49),
        (33, "Self-Use + TOU + Reserve/Backup", 51),
        (33, "Feed-in Priority", 96),
        (2080, "Self-Use", 33),  # and back out of peak shaving
        # Discussion #496: Reserve/Backup paired with Feed-in Priority instead of Self-Use.
        # Grid-charge bit 5 (already on at 96) is independent of STORAGE_MODE_BITS and survives.
        (96, "Feed-in Priority + Reserve/Backup", 112),
        (96, "Feed-in Priority + TOU + Reserve/Backup", 114),
        (80, "Feed-in Priority", 64),  # dropping Reserve/Backup from Feed-in Priority (no bit 5 here)
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


TOU_OPTIONS = {"Self-Use + TOU", "Self-Use + TOU + Reserve/Backup", "Feed-in Priority + TOU", "Feed-in Priority + TOU + Reserve/Backup"}
TOU_V2 = "custom_components.solis_modbus.sensors.solis_select_entity.tou_v2_active"


def test_tou_options_offered_on_v1_firmware():
    entity = make_entity()
    with patch(TOU_V2, return_value=False):
        assert TOU_OPTIONS <= set(entity.options)
        assert len(entity.options) == 10


def test_tou_options_hidden_on_v2_firmware():
    """#475: V2 firmware clears 43110 bit 1 ~15 s after every write."""
    entity = make_entity()
    with patch(TOU_V2, return_value=True):
        assert not TOU_OPTIONS & set(entity.options)
        assert len(entity.options) == 6


@pytest.mark.parametrize(
    "value,expected",
    [
        (19, "Self-Use + Reserve/Backup"),  # write echo seen on the #475 S6 before the firmware cleared it
        (35, "Self-Use"),
        (82, "Feed-in Priority + Reserve/Backup"),
        (17, "Self-Use + Reserve/Backup"),
    ],
)
def test_v2_ignores_dead_tou_bit(value, expected):
    entity = make_entity()
    with (
        patch(TOU_V2, return_value=True),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=value),
    ):
        assert entity.current_option == expected
        assert entity.current_option in entity.options


async def test_v2_refuses_tou_write():
    entity = make_entity()
    controller = entity._modbus_controller
    with (
        patch(TOU_V2, return_value=True),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=17),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_save"),
    ):
        await entity.async_select_option("Self-Use + TOU + Reserve/Backup")
    controller.async_write_holding_register.assert_not_awaited()


async def test_v2_still_clears_stray_tou_bit():
    entity = make_entity()
    controller = entity._modbus_controller
    with (
        patch(TOU_V2, return_value=True),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=19),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_save"),
    ):
        await entity.async_select_option("Self-Use + Reserve/Backup")
    controller.async_write_holding_register.assert_awaited_once_with(43110, 17)


def test_value_selects_unaffected_by_v2():
    """Masking bit 1 must only apply to Storage Mode, not on_value selects like RC Force."""
    inverter_config = next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH1P")
    definition = next(g for g in get_select_sensors(inverter_config) if g["register"] == 43135)
    entity = SolisSelectEntity(MagicMock(), make_entity()._modbus_controller, definition)
    with (
        patch(TOU_V2, return_value=True),
        patch("custom_components.solis_modbus.sensors.solis_select_entity.cache_get", return_value=2),
    ):
        assert entity.current_option == "Solis RC Force Battery Discharge"
        assert len(entity.options) == 3


def test_entity_renamed_but_unique_id_stable():
    inverter_config = next(inv for inv in SOLIS_INVERTERS if inv.model == "S6-EH1P")
    definition = next(g for g in get_select_sensors(inverter_config) if g["register"] == 43110)
    assert definition["name"] == "Storage Mode"
    assert definition["unique"] == "select_entity_43110"
