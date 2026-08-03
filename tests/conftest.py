"""Test session hooks for Windows + pytest-homeassistant socket blocking."""

import pytest
import pytest_socket


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    """Re-enable sockets after pytest-homeassistant disables them in the same hook."""
    outcome = yield
    outcome.get_result()
    pytest_socket.enable_socket()


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    """Ensure sockets are on before the event_loop fixture creates ProactorEventLoop."""
    pytest_socket.enable_socket()
    outcome = yield
    outcome.get_result()
