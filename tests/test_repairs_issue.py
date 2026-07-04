"""Repair issue lifecycle for an unreachable datalogger."""

from unittest.mock import MagicMock, patch

from custom_components.solis_modbus.const import DOMAIN, VALUES
from custom_components.solis_modbus.data_retrieval import DataRetrieval


def make_retrieval(entry_id="entry1"):
    hass = MagicMock()
    hass.data = {DOMAIN: {VALUES: {}}}
    controller = MagicMock()
    controller.host = "1.2.3.4"
    controller.slave = 1
    controller.poll_speed = {}
    retrieval = DataRetrieval(hass, controller, entry_id)
    return retrieval, hass, controller


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
