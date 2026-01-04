import pytest
from unittest.mock import patch, MagicMock, ANY
from homeassistant.const import CONF_HOST, CONF_PORT
from custom_components.solis_modbus.const import CONF_INVERTER_SERIAL, DOMAIN
from custom_components.solis_modbus import async_migrate_entry

@pytest.mark.asyncio
class TestMigration:
    def setup_method(self):
        self.hass = MagicMock()
        self.entry = MagicMock()
        self.entry.version = 1
        self.entry.domain = DOMAIN
        self.entry.data = {
            CONF_HOST: "192.168.1.10",
            CONF_PORT: 502,
            "slave": 1,
            CONF_INVERTER_SERIAL: "SN123456"
        }
        self.entry.unique_id = "192.168.1.10_1"
        self.registry = MagicMock()

        # Test Data
        self.old_uid = "solis_modbus_192.168.1.10_solis_modbus_inverter_active_power"
        self.new_uid = "solis_modbus_SN123456_solis_modbus_inverter_active_power"

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
        assert result is True

        # FIX 2: Remove 'data=ANY' (your code only updates the version)
        self.hass.config_entries.async_update_entry.assert_called_with(
            self.entry, version=3
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

        assert result is True

        self.hass.config_entries.async_update_entry.assert_called_with(
            self.entry, version=3
        )

    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_missing_serial(self, mock_get_registry):
        """Test missing serial number."""
        mock_get_registry.return_value = self.registry

        # Remove serial from data
        self.entry.data[CONF_INVERTER_SERIAL] = None

        # Run Migration
        result = await async_migrate_entry(self.hass, self.entry)

        # Should be False because migration is deferred when serial is missing
        assert result is False