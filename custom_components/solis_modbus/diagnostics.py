"""Diagnostics support for Solis Modbus — download from the config entry's ⋮ menu."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_INVERTER_SERIAL, DOMAIN, VALUES
from .runtime import SolisConfigEntry

TO_REDACT = {"host", CONF_INVERTER_SERIAL, "serial_port", "identification"}

# Serial-number registers decode to the inverter serial — keep them out of the dump.
_SERIAL_REGISTER_RANGE = range(33004, 33020)


def _partial(value) -> str | None:
    """Keep the last 4 characters so support can still correlate reports."""
    return f"***{str(value)[-4:]}" if value else None


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: SolisConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None:
        return {"error": "entry has no runtime data (not set up)"}

    controller = runtime.controller
    cache = hass.data.get(DOMAIN, {}).get(VALUES, {})
    cache_prefix = f"{controller.connection_id}|{controller.device_id}|"
    register_cache = {}
    for key, value in cache.items():
        if not key.startswith(cache_prefix):
            continue
        register = key.removeprefix(cache_prefix)
        if register.isdigit() and int(register) in _SERIAL_REGISTER_RANGE:
            continue
        register_cache[register] = value

    last_success = controller.last_modbus_success

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
            "version": f"{entry.version}.{entry.minor_version}",
            "unique_id": _partial(entry.unique_id),
        },
        "controller": {
            "connection_type": controller.connection_type,
            "host": _partial(controller.host),
            "device_id": controller.device_id,
            "connected": controller.connected(),
            "enabled": controller.enabled,
            "connect_failures": controller.connect_failures,
            "last_modbus_success": last_success.isoformat() if last_success else None,
            "poll_speed": {speed.name: interval for speed, interval in controller.poll_speed.items()},
            "sw_version": controller.sw_version,
        },
        "inverter_config": {
            "model": controller.inverter_config.model,
            "type": controller.inverter_config.type.name,
            "phases": controller.inverter_config.phases,
            "connection": controller.inverter_config.connection,
            "wattage_chosen": controller.inverter_config.wattage_chosen,
            "features": [feature.name for feature in controller.inverter_config.features],
        },
        "sensor_groups": [
            {
                "start_register": group.start_register,
                "count": group.registrar_count,
                "poll_speed": group.poll_speed.name,
                "disabled_sensors": [sensor.name for sensor in group.sensors if not sensor.enabled],
            }
            for group in controller.sensor_groups
        ],
        "entity_counts": {platform: len(entities) for platform, entities in runtime.entities.items()},
        "register_cache": register_cache,
    }
