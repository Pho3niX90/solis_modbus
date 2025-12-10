import unittest
from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

# Adjust import path if necessary
from custom_components.solis_modbus import async_migrate_entry
from custom_components.solis_modbus.const import DOMAIN, CONF_INVERTER_SERIAL


class TestMigration(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up common test fixtures."""
        self.hass = MagicMock(spec=HomeAssistant)
        self.hass.config_entries = MagicMock()
        self.registry = MagicMock()

        # Common Data
        self.host = "192.168.1.10"
        self.serial = "SN123456"
        self.entry = MagicMock(spec=ConfigEntry)
        self.entry.version = 1

        # --- FIX: Define the unique_id attribute ---
        # Simulate the old V1 format (Host based)
        self.entry.unique_id = f"{self.host}_1"
        # -----------------------------------------

        self.entry.data = {
            "host": self.host,
            CONF_INVERTER_SERIAL: self.serial,
            "model": "S6-EH3P",
            "type": "hybrid"
        }
        self.entry.options = {}
        self.entry.entry_id = "test_entry"

        # Define expected IDs for a specific sensor (Active Power)
        unique_key = "solis_modbus_inverter_active_power"
        self.old_uid = f"{DOMAIN}_{self.host}_{unique_key}"
        self.new_uid = f"{DOMAIN}_{self.serial}_{unique_key}"

    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_migrate_happy_path(self, mock_get_registry):
        """Test standard migration: Old exists, New does not."""
        mock_get_registry.return_value = self.registry

        # MOCK LOGIC:
        def get_entity_side_effect(platform, domain, unique_id):
            if unique_id == self.old_uid:
                return "sensor.solis_old_entity"
            if unique_id == self.new_uid:
                return None
            return None

        self.registry.async_get_entity_id.side_effect = get_entity_side_effect

        # Run Migration
        result = await async_migrate_entry(self.hass, self.entry)

        # Verify Success
        self.assertTrue(result)

        # Verify Version Bump via API Call (Not attribute check)
        self.hass.config_entries.async_update_entry.assert_called_with(
            self.entry, version=2
        )

        # Ensure Update was called
        self.registry.async_update_entity.assert_called_with(
            "sensor.solis_old_entity", new_unique_id=self.new_uid
        )
        # Ensure Remove was NOT called
        self.registry.async_remove.assert_not_called()

        # Ensure Config Entry Unique ID was updated
        # The logic calls update_entry twice: once for ID, once for Version.
        # Or merged? In your code it was separate calls.
        # Let's verify the ID update specifically.
        # Note: Depending on your exact implementation order, verify ANY call had these args
        self.hass.config_entries.async_update_entry.assert_any_call(
            self.entry, unique_id=self.serial
        )

    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_migrate_collision(self, mock_get_registry):
        """Test collision: Both Old and New IDs exist (Ghost entity)."""
        mock_get_registry.return_value = self.registry

        # MOCK LOGIC: Both return an entity ID
        def get_entity_side_effect(platform, domain, unique_id):
            if unique_id == self.old_uid:
                return "sensor.solis_old_history"  # Keep this
            if unique_id == self.new_uid:
                return "sensor.solis_new_ghost"  # Delete this
            return None

        self.registry.async_get_entity_id.side_effect = get_entity_side_effect

        # Run Migration
        result = await async_migrate_entry(self.hass, self.entry)

        self.assertTrue(result)

        # Verify Version Bump
        self.hass.config_entries.async_update_entry.assert_called_with(
            self.entry, version=2
        )

        # 1. Ensure the Ghost entity was removed
        self.registry.async_remove.assert_called_with("sensor.solis_new_ghost")

        # 2. Ensure the Old entity was updated
        self.registry.async_update_entity.assert_called_with(
            "sensor.solis_old_history", new_unique_id=self.new_uid
        )

    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_missing_serial(self, mock_get_registry):
        """Test missing serial number: Should bump version to 2 (Deferred) but NOT migrate entities."""
        mock_get_registry.return_value = self.registry

        # Remove serial from data
        self.entry.data[CONF_INVERTER_SERIAL] = None

        # Run Migration
        result = await async_migrate_entry(self.hass, self.entry)

        # Verify
        self.assertTrue(result)

        # CRITICAL CHANGE: We expect version 2 now (Deferred Strategy)
        self.hass.config_entries.async_update_entry.assert_called_with(
            self.entry, version=2
        )

        # Ensure NO registry calls were made (Entity migration skipped)
        self.registry.async_update_entity.assert_not_called()
        self.registry.async_remove.assert_not_called()


if __name__ == "__main__":
    unittest.main()
