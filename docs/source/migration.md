# Migration Guide (v4.0+)

Version 4.0 introduces a significant change to how Entity Unique IDs are generated, transitioning from a **Host/Port** based system to a **Serial Number** based system. This ensures that your entities (sensors) remain consistent even if your inverter's IP address changes or if you move your database to a new Home Assistant instance.

## Why the change?
Previously, unique IDs were generated using the Inverter's IP address (e.g., `solis_modbus_192.168.1.10_active_power`). If you changed your router or used DHCP, a new IP would cause Home Assistant to see all your sensors as "New" devices, breaking your history and dashboards.

By using the **Serial Number** (e.g., `solis_modbus_SN123ABC_active_power`), the ID remains tied to the physical device.

## The Migration Process
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

## Troubleshooting
If you see duplicate entities (e.g., `sensor.solis_active_power` and `sensor.solis_active_power_2`), it means the migration might have been interrupted or a conflict occurred.

*   **Solution**: Delete the "New" (duplicate) entities and restart Home Assistant. The migration logic will try to rename the "Old" (original) entities again.
*   **Logs**: Check your Home Assistant logs for messages starting with `Migration collision` or `Migrating sensor ...`.

### Restoring Sensor History
If a sensor's entity ID changes and you want to keep the old history:

1. Navigate to **Developer Tools** -> **Statistics**.
2. Search for the sensor name (e.g., "Today Battery Charge Energy").
3. You will likely see multiple entries with similar names. Identify which is the **current** sensor and which is the **historic** one.
4. Click on the **current** sensor, click the gear icon, and now rename the "Entity ID" to the old one

## "Identification" Field
The old "Identification" field (used to manually override the unique ID base) is now **deprecated**.
*   It is no longer available in the Setup/Config flow.
*   If you had it set previously, the migration logic *will* honor it to find your old entities and migrate them to the Serial Number format.
*   After migration, this field is effectively unused.
