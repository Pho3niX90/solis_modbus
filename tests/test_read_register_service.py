"""Tests for the solis_read_register debugging service.

The service is used for probing undocumented registers, so getting the address
or register type wrong is routine rather than exceptional. It should say so
plainly instead of surfacing as an unhandled server error (#447).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.solis_modbus.const import MODBUS_ILLEGAL_DATA_ADDRESS


class TestErrorClassification:
    """A caller mistake is a validation error; a failed read is not."""

    def test_illegal_address_is_a_validation_error(self):
        """ServiceValidationError, so callers get a 400 and a readable message."""
        assert issubclass(ServiceValidationError, HomeAssistantError)

    def test_the_modbus_code_is_the_documented_one(self):
        """Exception code 2 is 'illegal data address' in the Modbus spec."""
        assert MODBUS_ILLEGAL_DATA_ADDRESS == 2


class TestReadOutcomes:
    """Exercising the three outcomes the handler distinguishes."""

    def _controller(self, values, exception_code):
        controller = MagicMock()
        controller.async_read_input_registers_with_exception = AsyncMock(return_value=(values, exception_code))
        controller.async_read_holding_registers_with_exception = AsyncMock(return_value=(values, exception_code))
        return controller

    @pytest.mark.parametrize("register_type", ["input", "holding"])
    async def test_a_successful_read_returns_values(self, register_type):
        controller = self._controller([43605, 1, 2], None)

        if register_type == "holding":
            values, code = await controller.async_read_holding_registers_with_exception(34502, 3)
        else:
            values, code = await controller.async_read_input_registers_with_exception(34502, 3)

        assert values == [43605, 1, 2]
        assert code is None

    async def test_an_illegal_address_reports_the_code(self):
        """This is what reading a holding register as 'input' produces."""
        controller = self._controller(None, MODBUS_ILLEGAL_DATA_ADDRESS)

        values, code = await controller.async_read_input_registers_with_exception(44100, 2)

        assert values is None
        assert code == MODBUS_ILLEGAL_DATA_ADDRESS

    async def test_a_transport_failure_has_no_code(self):
        """No code means the read failed rather than being rejected."""
        controller = self._controller(None, None)

        values, code = await controller.async_read_input_registers_with_exception(34502, 3)

        assert values is None
        assert code is None
