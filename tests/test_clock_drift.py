from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from custom_components.solis_modbus.const import DOMAIN, DRIFT_COUNTER
from custom_components.solis_modbus.helpers import clock_drift_test

NOW = datetime(2026, 6, 13, 12, 30, 15, tzinfo=UTC)


def make_hass(counter=None):
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    if counter is not None:
        hass.data[DOMAIN][DRIFT_COUNTER] = counter
    return hass


def make_controller(connected=True):
    controller = MagicMock()
    controller.connected.return_value = connected
    return controller


def call(hass, controller, year, month, day, hours, minutes, seconds, now=NOW):
    with patch("custom_components.solis_modbus.helpers.dt_utils") as dt:
        dt.now.return_value = now
        return clock_drift_test(hass, controller, year, month, day, hours, minutes, seconds)


def test_in_sync_resets_counter():
    hass = make_hass(counter=3)
    controller = make_controller()

    adjusted = call(hass, controller, 26, 6, 13, 12, 30, 20)

    assert adjusted is False
    assert hass.data[DOMAIN][DRIFT_COUNTER] == 0
    hass.create_task.assert_not_called()


def test_wrong_date_same_time_is_detected_and_full_rtc_written():
    """A correct time-of-day on the wrong date must count as drift (old code missed this)."""
    hass = make_hass(counter=6)
    controller = make_controller()

    adjusted = call(hass, controller, 26, 6, 12, 12, 30, 15)

    assert adjusted is True
    hass.create_task.assert_called_once()
    write_call = controller.async_write_holding_registers.call_args
    assert write_call.args == (43000, [26, 6, 13, 12, 30, 15])


def test_midnight_rollover_is_not_false_drift():
    """20s of real drift across midnight must not read as ±86400s (old code did)."""
    hass = make_hass()
    controller = make_controller()
    now = datetime(2026, 6, 13, 0, 0, 10, tzinfo=UTC)

    adjusted = call(hass, controller, 26, 6, 12, 23, 59, 50, now=now)

    assert adjusted is False
    assert hass.data[DOMAIN][DRIFT_COUNTER] == 0
    hass.create_task.assert_not_called()


def test_invalid_rtc_contents_force_correction():
    hass = make_hass(counter=6)
    controller = make_controller()

    adjusted = call(hass, controller, 0, 0, 0, 0, 0, 0)

    assert adjusted is True
    write_call = controller.async_write_holding_registers.call_args
    assert write_call.args == (43000, [26, 6, 13, 12, 30, 15])


def test_drift_requires_consecutive_cycles_before_writing():
    hass = make_hass()
    controller = make_controller()

    for expected_counter in range(1, 7):
        adjusted = call(hass, controller, 26, 6, 13, 12, 0, 0)
        assert adjusted is False
        assert hass.data[DOMAIN][DRIFT_COUNTER] == expected_counter

    adjusted = call(hass, controller, 26, 6, 13, 12, 0, 0)
    assert adjusted is True


def test_no_write_when_disconnected():
    hass = make_hass(counter=6)
    controller = make_controller(connected=False)

    adjusted = call(hass, controller, 26, 6, 12, 12, 30, 15)

    assert adjusted is False
    hass.create_task.assert_not_called()
