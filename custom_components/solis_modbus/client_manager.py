import asyncio
import logging
import time

from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient

from custom_components.solis_modbus.const import CONN_TYPE_SERIAL, CONN_TYPE_TCP

_LOGGER = logging.getLogger(__name__)


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
            client = AsyncModbusTcpClient(host=host, port=port, timeout=5, retries=5)
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

    def get_serial_client(self, serial_port: str, baudrate: int, bytesize: int, parity: str, stopbits: int) -> AsyncModbusSerialClient:
        """Get or create a Serial Modbus client."""
        key = serial_port  # Use serial_port as the key
        if key not in self._clients:
            _LOGGER.debug(f"Creating new Modbus Serial client for {serial_port} (baudrate={baudrate})")
            client = AsyncModbusSerialClient(port=serial_port, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, timeout=5)
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
        delay_ms = 100 if is_write else 50
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
                if client.connected:
                    client.close()
                del self._clients[connection_id]
