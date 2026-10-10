"""Modbus RTU client for serial ports only Home Assistant's serial library can open.

pymodbus opens serial ports with pyserial, which knows device paths and a few
URL schemes. Home Assistant's own serial library, serialx, also opens ports that
integrations register at runtime, such as ESPHome serial proxies
(esphome-hass://...; Home Assistant Connect AUX-2 is one). For those ports this
client talks Modbus through modbus-connection's tmodbus backend, which opens
them with serialx, while offering the slice of the pymodbus client API the rest
of the integration uses: connect(), connected, close(), and register reads and
writes that return a result with isError(), registers and exception_code.
"""

from __future__ import annotations

import asyncio
import logging

from modbus_connection import ModbusError, ModbusExceptionError, ModbusSerialParams
from modbus_connection.tmodbus import ModbusConnection

_LOGGER = logging.getLogger(__name__)

# Schemes registered with serialx by Home Assistant integrations at runtime.
# esphome-hass: ESPHome serial proxies, registered by the esphome integration
# (HA 2026.5+), which is why the manifest lists esphome in after_dependencies.
SERIAL_PROXY_SCHEMES = ("esphome-hass",)

# Teardowns still running, by port. close() is synchronous, like pymodbus's, so
# the disconnect runs as a task; whatever opens the port next (this client, or a
# new one after the manager released this one) waits for it first.
_PENDING_TEARDOWNS: dict[str, asyncio.Task] = {}


def is_serial_proxy(port: str) -> bool:
    """Return whether this port is one only serialx can open."""
    scheme, separator, _ = port.partition("://")
    return bool(separator) and scheme.lower() in SERIAL_PROXY_SCHEMES


class SerialProxyResult:
    """A register read or write result shaped like pymodbus's responses."""

    def __init__(self, registers: list[int] | None = None, error: ModbusExceptionError | None = None) -> None:
        self.registers = registers or []
        self.exception_code = error.exception_code if error else None
        self._error = error

    def isError(self) -> bool:  # noqa: N802 - mirrors pymodbus
        """Return whether the device answered with a Modbus exception."""
        return self._error is not None

    def __str__(self) -> str:
        if self._error is not None:
            return f"Modbus exception {self.exception_code}: {self._error}"
        return f"registers={self.registers}"


class SerialProxyClient:
    """A pymodbus-like serial client over modbus-connection.

    Modbus exception responses come back as results with isError() True and an
    exception_code, as with pymodbus. Link failures and timeouts raise, which
    the controller already treats as a dropped connection.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        timeout: float = 5,
        retries: int | None = None,
    ) -> None:
        # retries is accepted for pymodbus compatibility; modbus-connection
        # doesn't retry, and the controller's own recovery handles failures.
        self.port = port
        # The controller sets this on serial clients; requests use it unless
        # they pass device_id.
        self.slave = 1
        self._connection = ModbusConnection(
            ModbusSerialParams(device=port, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits),
            timeout=timeout,
        )
        self._teardown: asyncio.Task | None = None

    @property
    def connected(self) -> bool:
        """Whether the link is open; False from close() on, while it is torn down."""
        return self._teardown is None and self._connection.connected

    async def connect(self) -> bool:
        """Open the link; like pymodbus, report failure instead of raising."""
        await self._await_teardown()
        try:
            await self._connection.connect()
        except ModbusError as err:
            _LOGGER.debug("Could not open serial proxy %s: %s", self.port, err)
        return self.connected

    def close(self) -> None:
        """Drop the link; the next connect() or request opens a fresh one.

        Synchronous like pymodbus's close(), so the teardown runs as a task that
        connect() and every request wait for.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self._disconnect())
        self._teardown = task
        _PENDING_TEARDOWNS[self.port] = task
        task.add_done_callback(self._teardown_done)

    async def _disconnect(self) -> None:
        try:
            await self._connection.disconnect()
        except ModbusError as err:
            _LOGGER.debug("Error closing serial proxy %s: %s", self.port, err)

    def _teardown_done(self, task: asyncio.Task) -> None:
        if self._teardown is task:
            self._teardown = None
        if _PENDING_TEARDOWNS.get(self.port) is task:
            del _PENDING_TEARDOWNS[self.port]

    async def _await_teardown(self) -> None:
        """Wait for a teardown of this port still in progress, by any client."""
        for task in {self._teardown, _PENDING_TEARDOWNS.get(self.port)} - {None}:
            # Shielded: a cancelled request must not cancel the teardown.
            await asyncio.shield(task)

    async def _unit(self, device_id: int | None):
        await self._await_teardown()
        return self._connection.for_unit(self.slave if device_id is None else device_id)

    async def read_input_registers(self, address: int, *, count: int = 1, device_id: int | None = None) -> SerialProxyResult:
        """Read input registers (FC04)."""
        unit = await self._unit(device_id)
        try:
            return SerialProxyResult(list(await unit.read_input_registers(address, count)))
        except ModbusExceptionError as err:
            return SerialProxyResult(error=err)

    async def read_holding_registers(self, address: int, *, count: int = 1, device_id: int | None = None) -> SerialProxyResult:
        """Read holding registers (FC03)."""
        unit = await self._unit(device_id)
        try:
            return SerialProxyResult(list(await unit.read_holding_registers(address, count)))
        except ModbusExceptionError as err:
            return SerialProxyResult(error=err)

    async def write_register(self, address: int, value: int, *, device_id: int | None = None) -> SerialProxyResult:
        """Write one holding register (FC06); the result echoes the value, as pymodbus's does."""
        unit = await self._unit(device_id)
        try:
            await unit.write_register(address, value)
        except ModbusExceptionError as err:
            return SerialProxyResult(error=err)
        return SerialProxyResult([value])

    async def write_registers(self, address: int, values: list[int], *, device_id: int | None = None) -> SerialProxyResult:
        """Write consecutive holding registers (FC16)."""
        unit = await self._unit(device_id)
        try:
            await unit.write_registers(address, values)
        except ModbusExceptionError as err:
            return SerialProxyResult(error=err)
        return SerialProxyResult(list(values))
