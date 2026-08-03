"""Test session hooks for Windows + pytest-homeassistant socket blocking."""

import sys

import pytest
import pytest_socket


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    """On Windows, allow sockets while the event_loop fixture creates ProactorEventLoop."""
    if sys.platform == "win32" and fixturedef.argname == "event_loop":
        pytest_socket.enable_socket()
    outcome = yield
    outcome.get_result()
