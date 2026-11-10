import asyncio
import logging
import time

from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
from pymodbus.framer import FramerRTU
from pymodbus.pdu import DecodePDU

from custom_components.solis_modbus.const import CONN_TYPE_SERIAL, CONN_TYPE_TCP
from custom_components.solis_modbus.rtu_framer import EarlyEnd, ResyncFramerRTU
from custom_components.solis_modbus.serial_proxy import SerialProxyClient, is_serial_proxy

_LOGGER = logging.getLogger(__name__)

# Solis RS485_MODBUS protocol (Hybrid Inverter V3.1 / PV Grid-Connected Inverter V19),
# section 3.2 "Inter-frame interval requirement": "More than 300ms communications frame
# interval is required." Applies to every request on the link, read or write. 310ms gives
# a small margin above the documented floor (see issue #480).
MIN_INTER_FRAME_MS = 310

# Serial timeout and retries of the pymodbus serial client. The timeout is only the backstop: the
# framer ends a failed attempt earlier (no first byte 0.5 s after the request, or the line silent for
# MIN_INTER_FRAME_MS without a valid answer), so a corrupted answer costs about its own line time plus
# 0.31 s and a silent attempt about 0.5 s plus the request's line time. 1.5 s still covers the longest
# healthy exchange: 0.5 s to the first byte plus the longest answer (125 registers = 255 bytes, 0.29 s
# of line time at 9600 baud). Three retries because corrupted frames are routine on this line.
SERIAL_TIMEOUT_S = 1.5
SERIAL_RETRIES = 3


def create_serial_client(serial_port: str, baudrate: int, bytesize: int, parity: str, stopbits: int) -> AsyncModbusSerialClient:
    """Create a pymodbus serial client that resyncs past junk and ends failed attempts early."""
    client = AsyncModbusSerialClient(
        port=serial_port, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, timeout=SERIAL_TIMEOUT_S, retries=SERIAL_RETRIES
    )

    def capture_attempt():
        """End function for the attempt being sent: `execute` creates its `response_future` just before sending."""
        future = client.ctx.response_future

        def end_attempt() -> None:
            if not future.done():
                future.set_exception(TimeoutError("attempt ended early by the RTU framer"))  # `execute` takes this like its own timeout: retry

        return end_attempt

    # `ctx.framer` is a plain attribute of pymodbus's transaction manager (3.11.4 - 3.13.1).
    framer = getattr(getattr(client, "ctx", None), "framer", None)
    if isinstance(framer, FramerRTU):
        client.ctx.framer = ResyncFramerRTU(DecodePDU(False), early_end=EarlyEnd(baudrate, MIN_INTER_FRAME_MS / 1000, capture_attempt))
    else:
        _LOGGER.warning("pymodbus serial client has no RTU framer to replace (%s); keeping its stock framer", type(framer).__name__)
    return client


class ModbusClientManager:
    _instance = None

    def __init__(self):
        # Key: connection_id (str), Value: client entry including shared inter-frame timing for all slaves on that link.
        self._clients: dict[str, dict] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_tcp_client(self, host: str, port: int) -> AsyncModbusTcpClient:
        """Get or create a TCP Modbus client."""
        key = f"{host}:{port}"
        if key not in self._clients:
            _LOGGER.debug(f"Creating new Modbus TCP client for {host}:{port}")
            # retries=1: the integration has its own reconnect watchdog and per-group
            # recovery. pymodbus-level retry storms (5 × 5 s per dead group) flood the
            # S2-WL datalogger, desync transaction IDs, and starve its cloud uplink
            # (issues #395/#406).
            client = AsyncModbusTcpClient(host=host, port=port, timeout=5, retries=1)
            self._clients[key] = {
                "client": client,
                "ref_count": 0,
                "lock": asyncio.Lock(),
                "type": CONN_TYPE_TCP,
                "last_modbus_request": 0.0,
            }

        self._clients[key]["ref_count"] += 1
        _LOGGER.debug(f"TCP client ref count for {host}:{port} is now {self._clients[key]['ref_count']}")
        return self._clients[key]["client"]

    def get_serial_client(self, serial_port: str, baudrate: int, bytesize: int, parity: str, stopbits: int) -> AsyncModbusSerialClient | SerialProxyClient:
        """Get or create a Serial Modbus client."""
        key = serial_port  # Use serial_port as the key
        if key not in self._clients:
            _LOGGER.debug(f"Creating new Modbus Serial client for {serial_port} (baudrate={baudrate})")
            if is_serial_proxy(serial_port):
                # ESPHome serial proxies (e.g. Connect AUX-2): pyserial can't open them.
                client = SerialProxyClient(serial_port, baudrate, bytesize, parity, stopbits, timeout=5)
            else:
                client = create_serial_client(serial_port, baudrate, bytesize, parity, stopbits)
            self._clients[key] = {
                "client": client,
                "ref_count": 0,
                "lock": asyncio.Lock(),
                "type": CONN_TYPE_SERIAL,
                "last_modbus_request": 0.0,
            }

        self._clients[key]["ref_count"] += 1
        _LOGGER.debug(f"Serial client ref count for {serial_port} is now {self._clients[key]['ref_count']}")
        return self._clients[key]["client"]

    def get_client(
        self,
        host: str = None,
        port: int = 502,
        serial_port: str = None,
        baudrate: int = 9600,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
    ) -> AsyncModbusTcpClient | AsyncModbusSerialClient:
        """
        Get a Modbus client (backwards compatible method).
        If host is provided, returns TCP client. If serial_port is provided, returns Serial client.
        """
        if host:
            return self.get_tcp_client(host, port)
        elif serial_port:
            return self.get_serial_client(serial_port, baudrate, bytesize, parity, stopbits)
        else:
            raise ValueError("Either host (for TCP) or serial_port (for Serial) must be provided")

    def get_client_lock(self, connection_id: str) -> asyncio.Lock:
        """Get the lock for a specific client connection."""
        if connection_id in self._clients:
            return self._clients[connection_id]["lock"]
        return None

    def get_last_modbus_request(self, connection_id: str) -> float:
        """Monotonic time of last inter-frame wait start for this link (shared across Modbus slaves)."""
        if connection_id in self._clients:
            return float(self._clients[connection_id].get("last_modbus_request", 0.0))
        return 0.0

    async def inter_frame_wait(self, connection_id: str, is_write: bool = False) -> None:
        """Minimum spacing between Modbus operations on one TCP/serial link, across all controllers sharing it."""
        if connection_id not in self._clients:
            return
        delay_ms = MIN_INTER_FRAME_MS
        entry = self._clients[connection_id]
        current_time = time.perf_counter()
        last = float(entry.get("last_modbus_request", 0.0))
        elapsed = (current_time - last) * 1000
        if elapsed < delay_ms:
            await asyncio.sleep((delay_ms - elapsed) / 1000)
        entry["last_modbus_request"] = time.perf_counter()

    def release_client(self, connection_id: str):
        """Release a client and clean up if no more references."""
        if connection_id in self._clients:
            self._clients[connection_id]["ref_count"] -= 1
            _LOGGER.debug(f"Client ref count for {connection_id} is now {self._clients[connection_id]['ref_count']}")

            if self._clients[connection_id]["ref_count"] <= 0:
                _LOGGER.debug(f"Closing and removing Modbus client for {connection_id}")
                client = self._clients[connection_id]["client"]
                try:
                    # unconditional: close() also cancels a pending pymodbus reconnect, which connected=False hides
                    client.close()
                except Exception as e:
                    _LOGGER.debug(f"Error closing client for {connection_id}: {e}")
                del self._clients[connection_id]

    def close_if_released(self, connection_id: str, client) -> None:
        """Close a client the manager no longer holds; a client other controllers still share is left open."""
        entry = self._clients.get(connection_id)
        if entry is None or entry["client"] is not client:
            client.close()
