import asyncio
import logging
from typing import Dict, Tuple
from pymodbus.client import AsyncModbusTcpClient

_LOGGER = logging.getLogger(__name__)

class ModbusClientManager:
    _instance = None
    
    def __init__(self):
        # Key: (host, port), Value: {'client': AsyncModbusTcpClient, 'ref_count': int, 'lock': asyncio.Lock}
        self._clients: Dict[Tuple[str, int], Dict] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_client(self, host: str, port: int) -> AsyncModbusTcpClient:
        key = (host, port)
        if key not in self._clients:
            _LOGGER.debug(f"Creating new Modbus client for {host}:{port}")
            client = AsyncModbusTcpClient(host=host, port=port, timeout=5, retries=5)
            self._clients[key] = {'client': client, 'ref_count': 0, 'lock': asyncio.Lock()}
        
        self._clients[key]['ref_count'] += 1
        _LOGGER.debug(f"Client ref count for {host}:{port} is now {self._clients[key]['ref_count']}")
        return self._clients[key]['client']

    def get_client_lock(self, host: str, port: int) -> asyncio.Lock:
        key = (host, port)
        if key in self._clients:
            return self._clients[key]['lock']
        return None

    def release_client(self, host: str, port: int):
        key = (host, port)
        if key in self._clients:
            self._clients[key]['ref_count'] -= 1
            _LOGGER.debug(f"Client ref count for {host}:{port} is now {self._clients[key]['ref_count']}")
            
            if self._clients[key]['ref_count'] <= 0:
                _LOGGER.debug(f"Closing and removing Modbus client for {host}:{port}")
                client = self._clients[key]['client']
                if client.connected:
                    client.close()
                del self._clients[key]
