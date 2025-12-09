import unittest
from unittest.mock import MagicMock, patch, ANY
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

# Adjust import path if necessary
from custom_components.solis_modbus import async_migrate_entry
from custom_components.solis_modbus.const import DOMAIN, CONF_INVERTER_SERIAL

class TestMigration(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up common test fixtures."""
        self.hass = MagicMock(spec=HomeAssistant)
        self.registry = MagicMock()

        # Common Data
        self.host = "192.168.1.10"
        self.serial = "SN123456"
        self.entry = MagicMock(spec=ConfigEntry)
        self.entry.version = 1
        self.entry.data = {
            "host": self.host,
            CONF_INVERTER_SERIAL: self.serial,
            "model": "S6-EH3P",
            "type": "hybrid"
        }
        self.entry.options = {}
        self.entry.entry_id = "test_entry"

        # Define expected IDs for a specific sensor (Active Power)
        # Note: 'solis_modbus_inverter_active_power' is the 'unique' key in hybrid_sensors
        unique_key = "solis_modbus_inverter_active_power"
        self.old_uid = f"{DOMAIN}_{self.host}_{unique_key}"
        self.new_uid = f"{DOMAIN}_{self.serial}_{unique_key}"

    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_migrate_happy_path(self, mock_get_registry):
        """Test standard migration: Old exists, New does not."""
        mock_get_registry.return_value = self.registry

        # MOCK LOGIC:
        # return "entity_id" if looking for OLD_UID
        # return None if looking for NEW_UID (it doesn't exist yet)
        def get_entity_side_effect(platform, domain, unique_id):
            if unique_id == self.old_uid:
                return "sensor.solis_old_entity"
            if unique_id == self.new_uid:
                return None
            return None

        self.registry.async_get_entity_id.side_effect = get_entity_side_effect

        # Run Migration
        result = await async_migrate_entry(self.hass, self.entry)

        # Verify
        self.assertTrue(result)
        self.assertEqual(self.entry.version, 2)

        # Ensure Update was called
        self.registry.async_update_entity.assert_called_with(
            "sensor.solis_old_entity", new_unique_id=self.new_uid
        )
        # Ensure Remove was NOT called
        self.registry.async_remove.assert_not_called()

    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_migrate_collision(self, mock_get_registry):
        """Test collision: Both Old and New IDs exist (Ghost entity)."""
        mock_get_registry.return_value = self.registry

        # MOCK LOGIC: Both return an entity ID
        def get_entity_side_effect(platform, domain, unique_id):
            if unique_id == self.old_uid:
                return "sensor.solis_old_history" # Keep this
            if unique_id == self.new_uid:
                return "sensor.solis_new_ghost"   # Delete this
            return None

        self.registry.async_get_entity_id.side_effect = get_entity_side_effect

        # Run Migration
        result = await async_migrate_entry(self.hass, self.entry)

        # Verify
        self.assertTrue(result)

        # 1. Ensure the Ghost entity was removed
        self.registry.async_remove.assert_called_with("sensor.solis_new_ghost")

        # 2. Ensure the Old entity was updated
        self.registry.async_update_entity.assert_called_with(
            "sensor.solis_old_history", new_unique_id=self.new_uid
        )

    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_missing_serial(self, mock_get_registry):
        """Test missing serial number: Should not bump version but NOT migrating."""
        mock_get_registry.return_value = self.registry

        # Remove serial from data
        self.entry.data[CONF_INVERTER_SERIAL] = None

        # Run Migration
        result = await async_migrate_entry(self.hass, self.entry)

        # Verify
        self.assertTrue(result)
        self.assertEqual(self.entry.version, 1)

        # Ensure NO registry calls were made
        self.registry.async_update_entity.assert_not_called()
        self.registry.async_remove.assert_not_called()

if __name__ == "__main__":
    unittest.main()