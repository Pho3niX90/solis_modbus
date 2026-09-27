"""Repair issue lifecycle for an unreachable datalogger."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from custom_components.solis_modbus.const import DOMAIN, VALUES
from custom_components.solis_modbus.data_retrieval import DataRetrieval


def make_retrieval(entry_id="entry1", suppress_night_issue=False):
    hass = MagicMock()
    hass.data = {DOMAIN: {VALUES: {}}}
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.slave = 1
    controller.poll_speed = {}
    retrieval = DataRetrieval(hass, controller, entry_id, suppress_night_issue=suppress_night_issue)
    return retrieval, hass, controller


def sun_up_at(*up_times):
    """Patch sun.is_up so it's True only for the given offsets (in hours) from now."""
    now = datetime.now(UTC)

    def is_up(_hass, when):
        return any(abs((when - (now + timedelta(hours=h))).total_seconds()) < 600 for h in up_times)

    return patch("custom_components.solis_modbus.data_retrieval.sun.is_up", side_effect=is_up)


# _expected_offline_at_night samples the sun an hour either side of now.
def night():
    return sun_up_at()


def day():
    return sun_up_at(-1, 1)


def just_after_sunrise():
    return sun_up_at(1)  # up in an hour, but wasn't an hour ago


def just_before_sunset():
    return sun_up_at(-1)  # was up an hour ago, won't be in an hour


def test_issue_created_when_unreachable():
    retrieval, hass, controller = make_retrieval()
    with patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        retrieval._update_connection_issue(True)
    mock_ir.async_create_issue.assert_called_once()
    args, kwargs = mock_ir.async_create_issue.call_args
    assert args[:2] == (hass, DOMAIN)
    assert args[2] == "datalogger_unreachable_entry1"
    assert kwargs["translation_key"] == "datalogger_unreachable"
    assert kwargs["is_fixable"] is False


def test_issue_deleted_when_reachable_and_on_stop():
    retrieval, hass, _ = make_retrieval()
    with patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        retrieval._update_connection_issue(False)
    mock_ir.async_delete_issue.assert_called_once_with(hass, DOMAIN, "datalogger_unreachable_entry1")


def test_noop_without_entry_id():
    retrieval, _, _ = make_retrieval(entry_id=None)
    with patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        retrieval._update_connection_issue(True)
        retrieval._update_connection_issue(False)
    mock_ir.async_create_issue.assert_not_called()
    mock_ir.async_delete_issue.assert_not_called()


@pytest.mark.parametrize("sun_window", [night, just_after_sunrise, just_before_sunset], ids=["night", "after_sunrise", "before_sunset"])
def test_issue_suppressed_and_existing_deleted_when_enabled_at_night(sun_window):
    retrieval, hass, _ = make_retrieval(suppress_night_issue=True)
    with sun_window(), patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        retrieval._update_connection_issue(True)
    mock_ir.async_create_issue.assert_not_called()
    mock_ir.async_delete_issue.assert_called_once_with(hass, DOMAIN, "datalogger_unreachable_entry1")


def test_night_suppression_deletes_only_once_per_night():
    retrieval, _, _ = make_retrieval(suppress_night_issue=True)
    with night(), patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        for _ in range(5):
            retrieval._update_connection_issue(True)
    mock_ir.async_create_issue.assert_not_called()
    mock_ir.async_delete_issue.assert_called_once()


def test_issue_raised_during_day_is_cleared_once_night_starts():
    retrieval, hass, _ = make_retrieval(suppress_night_issue=True)
    with patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        with day():
            retrieval._update_connection_issue(True)
        with night():
            retrieval._update_connection_issue(True)
            retrieval._update_connection_issue(True)
    mock_ir.async_create_issue.assert_called_once()
    mock_ir.async_delete_issue.assert_called_once_with(hass, DOMAIN, "datalogger_unreachable_entry1")


def test_issue_still_created_at_night_when_suppression_disabled():
    retrieval, _, _ = make_retrieval(suppress_night_issue=False)
    with night(), patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        retrieval._update_connection_issue(True)
    mock_ir.async_create_issue.assert_called_once()
    mock_ir.async_delete_issue.assert_not_called()


def test_issue_still_created_during_daytime_when_suppression_enabled():
    retrieval, _, _ = make_retrieval(suppress_night_issue=True)
    with day(), patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        retrieval._update_connection_issue(True)
    mock_ir.async_create_issue.assert_called_once()
    mock_ir.async_delete_issue.assert_not_called()
