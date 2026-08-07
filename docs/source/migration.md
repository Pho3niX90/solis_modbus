# Migration Guide

## Version 4.0+ — Serial-based unique IDs

Version 4.0 introduces a significant change to how Entity Unique IDs are generated, transitioning from a **Host/Port-based** system to a **Serial Number-based** system. This ensures that your entities (sensors) remain consistent even if your inverter's IP address changes or if you move your database to a new Home Assistant instance.

### Why the change?
Previously, unique IDs were generated using the Inverter's IP address (e.g., `solis_modbus_192.168.1.10_active_power`). If you changed your router or used DHCP, a new IP would cause Home Assistant to see all your sensors as "New" devices, breaking your history and dashboards.

By using the **Serial Number** (e.g., `solis_modbus_SN123ABC_active_power`), the ID remains tied to the physical device.

### The Migration Process
When you upgrade to v4.0+, the integration performs the following checks on startup:

1.  **Serial Number Check**: It checks if your configuration entry has a valid "Inverter Serial".
2.  **Auto-Migration**:
    *   If a Serial is present, it calculates what your *Old* Entity IDs were (based on your Host or the old "Identification" setting).
    *   It safely renames the *Old* Entity ID to the *New* Serial-based ID in the Home Assistant Entity Registry.
    *   **Result**: Your entity names (e.g., `sensor.solis_active_power`) stay the same, and your history is preserved.
3.  **Deferred Migration**:
    *   If your configuration is *missing* the Serial Number, the migration cannot happen.
    *   The integration will continue to work, but will generate a **Persistent Notification** asking you to "Reconfigure".
    *   Once you add the Serial Number, the migration will trigger automatically.

### Troubleshooting (serial migration)
If you see duplicate entities (e.g., `sensor.solis_active_power` and `sensor.solis_active_power_2`), it means the migration might have been interrupted or a conflict occurred.

*   **Solution**: Delete the "New" (duplicate) entities and restart Home Assistant. The migration logic will try to rename the "Old" (original) entities again.
*   **Logs**: Check your Home Assistant logs for messages starting with `Migration collision` or `Migrating sensor ...`.

### "Identification" Field
The old "Identification" field (used to manually override the unique ID base) is now **deprecated**.
*   It is no longer available in the Setup/Config flow.
*   If you had it set previously, the migration logic *will* honor it to find your old entities and migrate them to the Serial Number format.
*   After migration, this field is effectively unused.

---

## Version 4.2.3 — Duplicate entities after v4.2.0 ([#452](https://github.com/Pho3niX90/solis_modbus/issues/452))

In v4.2.0, some sensors got a second entity (original stuck `Unavailable`; new copy live, often with a **location prefix** in the `entity_id`). That was unintentional.

**Cause:** sensor groups passed the whole entity definition dict into `unique_id_generator`, so unique IDs embedded `str(dict)`. Definition changes in v4.2.0 (for example adding `data_type: U32` on lifetime energy sensors) changed those strings and Home Assistant treated them as new entities.

v4.2.3 fixes generation to use the stable `"unique"` key and migrates the entity registry on upgrade.

### Upgrade behavior

| Path | What happens |
|------|----------------|
| **4.1.6 → 4.2.3** | No duplicates. Same `entity_id`s. Only internal `unique_id`s are rewritten. Dashboards and automations keep working. |
| **4.2.0–4.2.2 → 4.2.3** | Original `entity_id`s restored. Orphan (usually location-prefixed) duplicates removed. The live entity is renamed onto the freed original `entity_id` with a stable `unique_id`. |
| **Fresh 4.2.3** | Stable unique IDs from day one. |

### What may remain after 4.2.3

*   **Location-prefixed sensors with no short twin** — Sensors that were **first created in v4.2.0** (new telemetry such as dispatch, meter2, fault bitfields, etc.), or that were only ever registered while the device name already included a location, have no pre-duplicate twin to restore. Their `entity_id` keeps the location prefix. That is expected; they are not failed restores of older entities.
*   Hybrid and string sensor maps are separate hardware profiles — only one is active per install. Do not treat the combined counts as what one inverter creates.

### History / Energy dashboard caveats

*   Home Assistant's recorder is *supposed* to move post-upgrade history when an `entity_id` is renamed onto the original. If logs show something like `Cannot migrate history … already in use`, that rename merge failed and you may see a history gap. For recorder state-history gaps, use the [manual restore steps](#restoring-sensor-history-manual) below or [HA-Merge-Sensor-History](https://github.com/mayerwin/HA-Merge-Sensor-History) (which merges both state history and long-term statistics). Use [Developer Tools → Statistics](https://www.home-assistant.io/docs/tools/dev-tools/) only to fix missing or invalid long-term statistics (not for general history recovery).
*   If you already re-pointed the **Energy dashboard** at a location-prefixed duplicate, re-select the restored original once after upgrading.
*   Dashboards and automations that still used the original `entity_id`s should work again without changes.

### Logs to check
Look for `Migrating dict unique_id`, `Restoring … onto original entity_id`, `Removing duplicate/orphan entity`, or recorder warnings about history migration / `states_meta`.

---

## Restoring Sensor History (manual)

If a sensor's entity ID changes and you want to keep the old history:

1. Navigate to **Settings** → **Devices & Services** → **Entities**.
2. Search for the sensor name (e.g., "Today Battery Charge Energy").
3. You will likely see multiple entries with similar names. Identify which is the **current** sensor and which is the **stale** one (the stale entry typically shows as "Unavailable" or "Restored").
4. Remove only the **stale** entity-registry entry (not the historic one with data). This frees up the desired `entity_id` without losing history.
5. Restart Home Assistant if needed to allow the current sensor to claim the freed `entity_id`.

**Important**: Do not rename or delete the historic entry's data. Removing the stale entity-registry entry preserves all recorder history.

If you need to merge history from multiple entities, use: https://github.com/mayerwin/HA-Merge-Sensor-History

For fixing missing or invalid **long-term statistics** specifically, use [Developer Tools → Statistics](https://www.home-assistant.io/docs/tools/dev-tools/).
