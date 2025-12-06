import unittest
from unittest.mock import MagicMock, patch
from custom_components.solis_modbus.client_manager import ModbusClientManager

class TestModbusClientManager(unittest.TestCase):

    def setUp(self):
        # Reset singleton
        ModbusClientManager._instance = None
        self.manager = ModbusClientManager.get_instance()

    def tearDown(self):
        ModbusClientManager._instance = None

    @patch('custom_components.solis_modbus.client_manager.AsyncModbusTcpClient')
    def test_get_client_creates_new_if_not_exists(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        client1 = self.manager.get_client("1.2.3.4", 502)
        
        mock_client_cls.assert_called_once_with(host="1.2.3.4", port=502, timeout=5, retries=5)
        self.assertEqual(client1, mock_client)
        self.assertEqual(self.manager._clients[("1.2.3.4", 502)]['ref_count'], 1)

    @patch('custom_components.solis_modbus.client_manager.AsyncModbusTcpClient')
    def test_get_client_returns_existing_and_increments_ref(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        client1 = self.manager.get_client("1.2.3.4", 502)
        client2 = self.manager.get_client("1.2.3.4", 502)
        
        mock_client_cls.assert_called_once() # Called only once!
        self.assertEqual(client1, client2)
        self.assertEqual(self.manager._clients[("1.2.3.4", 502)]['ref_count'], 2)

    @patch('custom_components.solis_modbus.client_manager.AsyncModbusTcpClient')
    def test_get_client_lock(self, mock_client_cls):
        client1 = self.manager.get_client("1.2.3.4", 502)
        lock = self.manager.get_client_lock("1.2.3.4", 502)
        
        self.assertIsNotNone(lock)
        # Should be the same lock instance
        self.assertEqual(lock, self.manager._clients[("1.2.3.4", 502)]['lock'])
        
        # Non-existent
        self.assertIsNone(self.manager.get_client_lock("9.9.9.9", 502))

    @patch('custom_components.solis_modbus.client_manager.AsyncModbusTcpClient')
    def test_release_client(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.connected = True
        mock_client_cls.return_value = mock_client
        
        # Get twice
        self.manager.get_client("1.2.3.4", 502)
        self.manager.get_client("1.2.3.4", 502)
        
        # Release once
        self.manager.release_client("1.2.3.4", 502)
        self.assertEqual(self.manager._clients[("1.2.3.4", 502)]['ref_count'], 1)
        mock_client.close.assert_not_called()
        
        # Release again
        self.manager.release_client("1.2.3.4", 502)
        # Should be removed
        self.assertNotIn(("1.2.3.4", 502), self.manager._clients)
        mock_client.close.assert_called_once()
    
    def test_release_non_existent_client(self):
        # Should not raise
        self.manager.release_client("9.9.9.9", 502)

if __name__ == "__main__":
    unittest.main()
