"""Per-config-entry runtime state (Home Assistant runtime_data pattern).

Everything scoped to one inverter entry lives here instead of nested
hass.data buckets. Deliberately NOT here:
- the register VALUES cache (shared across entries, keys namespaced per
  link|slave — parallel inverters on one datalogger share reads),
- the ModbusClientManager singleton (shares one pymodbus client per link).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .data_retrieval import DataRetrieval
    from .modbus_controller import ModbusController

type SolisConfigEntry = ConfigEntry[SolisRuntimeData]


@dataclass
class SolisRuntimeData:
    """Runtime state for one Solis inverter config entry."""

    controller: ModbusController
    data_retrieval: DataRetrieval | None = None
    # platform key ("sensor", "number", "switch", "select", "time") -> entity list
    entities: dict[str, list] = field(default_factory=dict)
