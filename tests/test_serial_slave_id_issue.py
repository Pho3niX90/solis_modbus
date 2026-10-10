"""Repair issue for serial entries whose inverter only answers at slave ID 1.

Serial requests used to go to unit 1 whatever slave ID was configured, so an
entry with the wrong slave ID worked until that was fixed.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.solis_modbus.const import CONN_TYPE_SERIAL, CONN_TYPE_TCP, DOMAIN, VALUES
from custom_components.solis_modbus.data_retrieval import _SLAVE_PROBE_AFTER, DataRetrieval

ISSUE_ID = "serial_slave_id_entry1"


def make_controller(device_id=7, connection_type=CONN_TYPE_SERIAL, connection_id="/dev/ttyUSB0"):
    controller = MagicMock()
    controller.host = connection_id
    controller.slave = device_id
    controller.device_id = device_id
    controller.connection_type = connection_type
    controller.connection_id = connection_id
    controller.has_answered = False
    controller.poll_speed = {}
    controller.async_unit_answers = AsyncMock(return_value=True)
    return controller


def make_retrieval(controller, entry_id="entry1", polling_for=_SLAVE_PROBE_AFTER.total_seconds() + 1):
    hass = MagicMock()
    hass.data = {DOMAIN: {VALUES: {}}}
    retrieval = DataRetrieval(hass, controller, entry_id)
    retrieval._polling_since = time.monotonic() - polling_for
    return retrieval, hass


@pytest.fixture
def mock_ir():
    with patch("custom_components.solis_modbus.data_retrieval.ir") as mock_ir:
        yield mock_ir


@pytest.fixture
def other_controllers():
    with patch("custom_components.solis_modbus.data_retrieval.iter_controllers", return_value=[]) as mock_iter:
        yield mock_iter


@pytest.mark.asyncio
async def test_issue_raised_when_only_unit_1_answers(mock_ir, other_controllers):
    controller = make_controller()
    retrieval, hass = make_retrieval(controller)

    await retrieval._check_serial_slave_id()

    controller.async_unit_answers.assert_awaited_once_with(1)
    mock_ir.async_create_issue.assert_called_once()
    args, kwargs = mock_ir.async_create_issue.call_args
    assert args == (hass, DOMAIN, ISSUE_ID)
    assert kwargs["translation_key"] == "serial_slave_id"
    assert kwargs["translation_placeholders"] == {"port": "/dev/ttyUSB0", "slave": "7"}

    # No further probes while the issue stands.
    await retrieval._check_serial_slave_id()
    controller.async_unit_answers.assert_awaited_once()
    mock_ir.async_delete_issue.assert_not_called()


@pytest.mark.asyncio
async def test_raised_issue_cleared_once_configured_slave_answers(mock_ir, other_controllers):
    # e.g. the configured inverter was asleep for the first minutes after startup
    controller = make_controller()
    retrieval, hass = make_retrieval(controller)
    await retrieval._check_serial_slave_id()
    mock_ir.async_create_issue.assert_called_once()

    controller.has_answered = True
    await retrieval._check_serial_slave_id()

    mock_ir.async_delete_issue.assert_called_once_with(hass, DOMAIN, ISSUE_ID)
    controller.async_unit_answers.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_issue_when_unit_1_silent_and_retried_later(mock_ir, other_controllers):
    controller = make_controller()
    controller.async_unit_answers.return_value = False
    retrieval, _ = make_retrieval(controller)

    await retrieval._check_serial_slave_id()
    await retrieval._check_serial_slave_id()

    assert controller.async_unit_answers.await_count == 2
    mock_ir.async_create_issue.assert_not_called()


@pytest.mark.asyncio
async def test_no_probe_before_inverter_had_a_chance(mock_ir, other_controllers):
    controller = make_controller()
    retrieval, _ = make_retrieval(controller, polling_for=0)

    await retrieval._check_serial_slave_id()

    controller.async_unit_answers.assert_not_awaited()
    mock_ir.async_create_issue.assert_not_called()


@pytest.mark.parametrize(
    "controller",
    [
        make_controller(device_id=1),
        make_controller(connection_type=CONN_TYPE_TCP, connection_id="1.2.3.4:502"),
    ],
    ids=["slave_1", "tcp"],
)
@pytest.mark.asyncio
async def test_not_applicable_clears_issue(mock_ir, other_controllers, controller):
    # e.g. the entry was reconfigured to slave ID 1 after the issue was raised
    retrieval, hass = make_retrieval(controller)

    await retrieval._check_serial_slave_id()

    controller.async_unit_answers.assert_not_awaited()
    mock_ir.async_delete_issue.assert_called_once_with(hass, DOMAIN, ISSUE_ID)


@pytest.mark.asyncio
async def test_configured_slave_answering_clears_issue(mock_ir, other_controllers):
    controller = make_controller()
    controller.has_answered = True
    retrieval, hass = make_retrieval(controller)

    await retrieval._check_serial_slave_id()

    controller.async_unit_answers.assert_not_awaited()
    mock_ir.async_delete_issue.assert_called_once_with(hass, DOMAIN, ISSUE_ID)


@pytest.mark.asyncio
async def test_no_probe_when_unit_1_is_another_configured_inverter(mock_ir, other_controllers):
    controller = make_controller()
    other_controllers.return_value = [controller, make_controller(device_id=1)]
    retrieval, _ = make_retrieval(controller)

    await retrieval._check_serial_slave_id()

    controller.async_unit_answers.assert_not_awaited()
    mock_ir.async_create_issue.assert_not_called()


@pytest.mark.asyncio
async def test_unit_1_on_another_bus_does_not_count(mock_ir, other_controllers):
    controller = make_controller()
    other_controllers.return_value = [controller, make_controller(device_id=1, connection_id="/dev/ttyUSB1")]
    retrieval, _ = make_retrieval(controller)

    await retrieval._check_serial_slave_id()

    controller.async_unit_answers.assert_awaited_once_with(1)
    mock_ir.async_create_issue.assert_called_once()
