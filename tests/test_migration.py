from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.solis_modbus import async_migrate_dict_unique_ids, async_migrate_entry
from custom_components.solis_modbus.const import CONF_INVERTER_SERIAL, DOMAIN
from custom_components.solis_modbus.helpers import unique_id_generator
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisSensorGroup


def _apply_version_updates(entry):
    """Make mocked async_update_entry actually bump entry.version."""

    def _update(config_entry, **kwargs):
        if "version" in kwargs:
            config_entry.version = kwargs["version"]

    return _update


@pytest.mark.asyncio
class TestMigration:
    def setup_method(self):
        self.hass = MagicMock()
        self.entry = MagicMock()
        self.entry.version = 1
        self.entry.domain = DOMAIN
        self.entry.entry_id = "entry-1"
        self.entry.data = {CONF_HOST: "192.168.1.10", CONF_PORT: 502, "slave": 1, CONF_INVERTER_SERIAL: "SN123456", "model": "S6-EH1P"}
        self.entry.options = {}
        self.entry.unique_id = "192.168.1.10_1"
        self.registry = MagicMock()
        self.dev_registry = MagicMock()
        self.dev_registry.devices.get_devices_for_config_entry_id.return_value = []

        self.old_uid = "solis_modbus_192.168.1.10_solis_modbus_inverter_active_power"
        self.new_uid = "solis_modbus_SN123456_solis_modbus_inverter_active_power"

    @patch("homeassistant.helpers.device_registry.async_get")
    @patch("homeassistant.helpers.entity_registry.async_get")
    @patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry", return_value=[])
    async def test_migrate_happy_path(self, _mock_entries, mock_get_registry, mock_get_dev_registry):
        """Serial migrate then dict migrate: version lands on 4."""
        mock_get_registry.return_value = self.registry
        mock_get_dev_registry.return_value = self.dev_registry
        self.hass.config_entries.async_update_entry.side_effect = _apply_version_updates(self.entry)

        def get_entity_side_effect(platform, domain, unique_id):
            if unique_id == self.old_uid:
                return "sensor.solis_old_entity"
            if unique_id == self.new_uid:
                return None
            return None

        self.registry.async_get_entity_id.side_effect = get_entity_side_effect

        result = await async_migrate_entry(self.hass, self.entry)

        assert result is True
        assert self.entry.version == 4
        self.hass.config_entries.async_update_entry.assert_any_call(self.entry, version=3)
        self.hass.config_entries.async_update_entry.assert_any_call(self.entry, version=4)

    @patch("homeassistant.helpers.device_registry.async_get")
    @patch("homeassistant.helpers.entity_registry.async_get")
    @patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry", return_value=[])
    async def test_migrate_collision(self, _mock_entries, mock_get_registry, mock_get_dev_registry):
        mock_get_registry.return_value = self.registry
        mock_get_dev_registry.return_value = self.dev_registry
        self.hass.config_entries.async_update_entry.side_effect = _apply_version_updates(self.entry)

        def get_entity_side_effect(platform, domain, unique_id):
            if unique_id == self.old_uid:
                return "sensor.solis_old_history"
            if unique_id == self.new_uid:
                return "sensor.solis_new_ghost"
            return None

        self.registry.async_get_entity_id.side_effect = get_entity_side_effect

        result = await async_migrate_entry(self.hass, self.entry)

        assert result is True
        assert self.entry.version == 4

    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_missing_serial(self, mock_get_registry):
        mock_get_registry.return_value = self.registry
        self.entry.data[CONF_INVERTER_SERIAL] = None

        result = await async_migrate_entry(self.hass, self.entry)

        assert result is False


def _make_registry_entry(entity_id, unique_id, domain="sensor", created_at=None):
    ent = MagicMock()
    ent.entity_id = entity_id
    ent.unique_id = unique_id
    ent.domain = domain
    ent.created_at = created_at
    return ent


UNIQUE_KEY = "solis_modbus_inverter_backup_total_energy"


def _broken_uid(serial: str, with_data_type: bool) -> str:
    entity = {
        "name": "Backup Load Total Energy",
        "unique": UNIQUE_KEY,
        "register": ["33590", "33591"],
    }
    if with_data_type:
        entity["data_type"] = "U32"
    return f"{DOMAIN}_{serial}_{entity}"


@pytest.mark.asyncio
class TestDictUniqueIdMigration:
    def setup_method(self):
        self.hass = MagicMock()
        self.entry = MagicMock()
        self.entry.version = 3
        self.entry.entry_id = "entry-dict-1"
        self.entry.data = {
            CONF_HOST: "192.168.1.10",
            CONF_PORT: 502,
            "slave": 1,
            CONF_INVERTER_SERIAL: "SN123456",
            "model": "S6-EH1P",
        }
        self.entry.options = {}
        self.registry = MagicMock()
        self.live = {}

        def async_get(entity_id):
            return self.live.get(entity_id)

        def async_remove(entity_id):
            self.live.pop(entity_id, None)

        def async_update_entity(entity_id, **kwargs):
            ent = self.live.pop(entity_id)
            if "new_unique_id" in kwargs:
                ent.unique_id = kwargs["new_unique_id"]
            new_eid = kwargs.get("new_entity_id", entity_id)
            ent.entity_id = new_eid
            self.live[new_eid] = ent
            return ent

        self.registry.async_get.side_effect = async_get
        self.registry.async_remove.side_effect = async_remove
        self.registry.async_update_entity.side_effect = async_update_entity

    @patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry")
    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_upgrade_416_to_423_rewrites_unique_id_keeps_entity_id(self, mock_get_reg, mock_entries):
        """4.1.6 → 4.2.3: one entity; rewrite unique_id only; no rename, no duplicates.

        Pre-4.2.0 installs have a single dict-stringified unique_id per sensor.
        Migration must keep that entity_id so dashboards/automations keep working.
        """
        mock_get_reg.return_value = self.registry
        original_entity_id = "sensor.solis_s6_eh1p_backup_load_total_energy"
        broken = _broken_uid("SN123456", with_data_type=False)
        ent = _make_registry_entry(original_entity_id, broken)
        self.live[ent.entity_id] = ent
        mock_entries.return_value = [ent]

        await async_migrate_dict_unique_ids(self.hass, self.entry)

        assert list(self.live.keys()) == [original_entity_id], "must not create a second entity"
        survivor = self.live[original_entity_id]
        assert survivor.entity_id == original_entity_id
        assert survivor.unique_id == f"{DOMAIN}_SN123456_{UNIQUE_KEY}"
        self.registry.async_remove.assert_not_called()
        self.registry.async_update_entity.assert_called_once_with(
            original_entity_id,
            new_unique_id=f"{DOMAIN}_SN123456_{UNIQUE_KEY}",
        )
        assert "new_entity_id" not in self.registry.async_update_entity.call_args.kwargs

    @patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry")
    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_upgrade_422_to_423_restores_original_removes_location_prefixed_ghost(self, mock_get_reg, mock_entries):
        """4.2.2 → 4.2.3: restore original entity_id; remove location-prefixed duplicate.

        After v4.2.0, the pre-dupe (oldest) entity_id is unavailable and a
        location-prefixed duplicate holds live values. Migration frees the
        original entity_id, renames the live row onto it (recorder follows),
        and leaves exactly one entity with the stable unique_id.
        """
        mock_get_reg.return_value = self.registry
        original_entity_id = "sensor.solis_s6_eh1p_backup_load_total_energy"
        location_prefixed_id = "sensor.kallare_solis_s6_eh1p_backup_load_total_energy"
        old_uid = _broken_uid("SN123456", with_data_type=False)
        new_uid = _broken_uid("SN123456", with_data_type=True)
        oldest = _make_registry_entry(
            original_entity_id,
            old_uid,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        newest = _make_registry_entry(
            location_prefixed_id,
            new_uid,
            created_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
        self.live[oldest.entity_id] = oldest
        self.live[newest.entity_id] = newest
        mock_entries.return_value = [oldest, newest]

        await async_migrate_dict_unique_ids(self.hass, self.entry)

        assert location_prefixed_id not in self.live, "location-prefixed ghost must be gone"
        assert list(self.live.keys()) == [original_entity_id], "original entity_id must be restored as sole survivor"
        survivor = self.live[original_entity_id]
        assert survivor.entity_id == original_entity_id
        assert survivor.unique_id == f"{DOMAIN}_SN123456_{UNIQUE_KEY}"
        self.registry.async_remove.assert_called_once_with(original_entity_id)
        self.registry.async_update_entity.assert_called_once_with(
            location_prefixed_id,
            new_unique_id=f"{DOMAIN}_SN123456_{UNIQUE_KEY}",
            new_entity_id=original_entity_id,
        )

    @patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry")
    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_number_platform_duplicate(self, mock_get_reg, mock_entries):
        mock_get_reg.return_value = self.registry
        # Use a key that exists on hybrid maps; number platform shares unique strings.
        key = "solis_modbus_inverter_overcharge_soc"
        old_uid = f"{DOMAIN}_SN123456_{{'name': 'Max Charge SOC', 'unique': '{key}', 'register': ['43010']}}"
        new_uid = f"{DOMAIN}_SN123456_{{'name': 'Max Charge SOC', 'unique': '{key}', 'register': ['43010'], 'data_type': 'U32'}}"
        oldest = _make_registry_entry(
            "number.solis_max_charge_soc",
            old_uid,
            domain="number",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        newest = _make_registry_entry(
            "number.kallare_solis_max_charge_soc",
            new_uid,
            domain="number",
            created_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
        self.live[oldest.entity_id] = oldest
        self.live[newest.entity_id] = newest
        mock_entries.return_value = [oldest, newest]

        await async_migrate_dict_unique_ids(self.hass, self.entry)

        assert "number.solis_max_charge_soc" in self.live
        assert "number.kallare_solis_max_charge_soc" not in self.live
        assert self.live["number.solis_max_charge_soc"].unique_id == f"{DOMAIN}_SN123456_{key}"

    @patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry")
    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_already_correct_noop(self, mock_get_reg, mock_entries):
        mock_get_reg.return_value = self.registry
        correct = f"{DOMAIN}_SN123456_{UNIQUE_KEY}"
        ent = _make_registry_entry("sensor.solis_s6_eh1p_backup_load_total_energy", correct)
        self.live[ent.entity_id] = ent
        mock_entries.return_value = [ent]

        await async_migrate_dict_unique_ids(self.hass, self.entry)

        self.registry.async_update_entity.assert_not_called()
        self.registry.async_remove.assert_not_called()

    @patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry")
    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_only_newest_left_rewrites_in_place(self, mock_get_reg, mock_entries):
        mock_get_reg.return_value = self.registry
        new_uid = _broken_uid("SN123456", with_data_type=True)
        ent = _make_registry_entry("sensor.kallare_solis_s6_eh1p_backup_load_total_energy", new_uid)
        self.live[ent.entity_id] = ent
        mock_entries.return_value = [ent]

        await async_migrate_dict_unique_ids(self.hass, self.entry)

        assert "sensor.kallare_solis_s6_eh1p_backup_load_total_energy" in self.live
        assert self.live["sensor.kallare_solis_s6_eh1p_backup_load_total_energy"].unique_id == (f"{DOMAIN}_SN123456_{UNIQUE_KEY}")
        # No rename when only one remains
        kwargs = self.registry.async_update_entity.call_args.kwargs
        assert "new_entity_id" not in kwargs

    @patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry", return_value=[])
    @patch("homeassistant.helpers.entity_registry.async_get")
    async def test_version_3_to_4_runs_dict_migration(self, mock_get_reg, _mock_entries):
        mock_get_reg.return_value = self.registry
        self.hass.config_entries.async_update_entry.side_effect = _apply_version_updates(self.entry)

        result = await async_migrate_entry(self.hass, self.entry)

        assert result is True
        assert self.entry.version == 4


class TestUniqueIdCallSite:
    def test_dict_guard_extracts_unique_key(self):
        controller = MagicMock()
        controller.device_serial_number = "SN1"
        controller.identification = None
        controller.host = "1.2.3.4"
        entity = {"name": "X", "unique": "solis_modbus_inverter_backup_total_energy"}
        assert unique_id_generator(controller, entity) == f"{DOMAIN}_SN1_solis_modbus_inverter_backup_total_energy"

    def test_sensor_group_uses_unique_key_not_dict_str(self):
        hass = MagicMock()
        controller = MagicMock()
        controller.device_serial_number = "SN1"
        controller.identification = None
        controller.host = "1.2.3.4"
        controller.inverter_config = MagicMock()
        controller.inverter_config.model = "S6-EH1P"
        controller.inverter_config.features = set()
        controller.inverter_config.wattage_chosen = 6000

        definition = {
            "register_start": 33590,
            "poll_speed": MagicMock(),
            "entities": [
                {
                    "name": "Backup Load Total Energy",
                    "unique": UNIQUE_KEY,
                    "register": ["33590", "33591"],
                    "data_type": "U32",
                }
            ],
        }
        # Avoid PollSpeed enum comparison issues in start_register path
        from custom_components.solis_modbus.data.enums import PollSpeed

        definition["poll_speed"] = PollSpeed.SLOW

        group = SolisSensorGroup(hass=hass, definition=definition, controller=controller)
        assert len(group.sensors) == 1
        uid = group.sensors[0].unique_id
        assert uid == f"{DOMAIN}_SN1_{UNIQUE_KEY}"
        assert "{" not in uid
        assert "data_type" not in uid
