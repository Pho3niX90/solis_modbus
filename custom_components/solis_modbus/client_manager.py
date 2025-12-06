import asyncio
import logging
from typing import Dict, Tuple, Union
from pymodbus.client import AsyncModbusTcpClient, AsyncModbusSerialClient

from custom_components.solis_modbus.const import CONN_TYPE_TCP, CONN_TYPE_SERIAL

_LOGGER = logging.getLogger(__name__)

class ModbusClientManager:
    _instance = None

    def __init__(self):
        # Key: connection_id (str), Value: {'client': AsyncModbusTcpClient|AsyncModbusSerialClient, 'ref_count': int, 'lock': asyncio.Lock, 'type': str}
        self._clients: Dict[str, Dict] = {}

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
            self._clients[key] = {'client': client, 'ref_count': 0, 'lock': asyncio.Lock(), 'type': CONN_TYPE_TCP}

        self._clients[key]['ref_count'] += 1
        _LOGGER.debug(f"TCP client ref count for {host}:{port} is now {self._clients[key]['ref_count']}")
        return self._clients[key]['client']

    def get_serial_client(self, serial_port: str, baudrate: int, bytesize: int, parity: str, stopbits: int) -> AsyncModbusSerialClient:
        """Get or create a Serial Modbus client."""
        key = serial_port  # Use serial_port as the key
        if key not in self._clients:
            _LOGGER.debug(f"Creating new Modbus Serial client for {serial_port} (baudrate={baudrate})")
            client = AsyncModbusSerialClient(
                port=serial_port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=5
            )
            self._clients[key] = {'client': client, 'ref_count': 0, 'lock': asyncio.Lock(), 'type': CONN_TYPE_SERIAL}

        self._clients[key]['ref_count'] += 1
        _LOGGER.debug(f"Serial client ref count for {serial_port} is now {self._clients[key]['ref_count']}")
        return self._clients[key]['client']

    def get_client(self, host: str = None, port: int = 502, serial_port: str = None,
                   baudrate: int = 9600, bytesize: int = 8, parity: str = 'N',
                   stopbits: int = 1) -> Union[AsyncModbusTcpClient, AsyncModbusSerialClient]:
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
            return self._clients[connection_id]['lock']
        return None

    def release_client(self, connection_id: str):
        """Release a client and clean up if no more references."""
        if connection_id in self._clients:
            self._clients[connection_id]['ref_count'] -= 1
            _LOGGER.debug(f"Client ref count for {connection_id} is now {self._clients[connection_id]['ref_count']}")

            if self._clients[connection_id]['ref_count'] <= 0:
                _LOGGER.debug(f"Closing and removing Modbus client for {connection_id}")
                client = self._clients[connection_id]['client']
                if client.connected:
                    client.close()
                del self._clients[connection_id]
