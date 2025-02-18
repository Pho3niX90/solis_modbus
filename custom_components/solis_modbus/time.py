import logging
import datetime
from datetime import time
from typing import List

from homeassistant.components.number import NumberMode
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, MANUFACTURER, \
    TIME_ENTITIES
from custom_components.solis_modbus.helpers import get_controller, cache_get

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    """Set up the time platform."""
    modbus_controller: ModbusController = get_controller(hass, config_entry.data.get("host"))

    inverter_type = config_entry.data.get("type", "hybrid")

    if inverter_type == 'string':
        return False

    timeEntities: List[SolisTimeEntity] = []

    timeent = [
        {"name": "Solis Time-Charging Charge Start (Slot 1)", "register": 43143, "enabled": True},
        {"name": "Solis Time-Charging Charge End (Slot 1)", "register": 43145, "enabled": True},
        {"name": "Solis Time-Charging Discharge Start (Slot 1)", "register": 43147, "enabled": True},
        {"name": "Solis Time-Charging Discharge End (Slot 1)", "register": 43149, "enabled": True},

        {"name": "Solis Time-Charging Charge Start (Slot 2)", "register": 43153, "enabled": True},
        {"name": "Solis Time-Charging Charge End (Slot 2)", "register": 43155, "enabled": True},
        {"name": "Solis Time-Charging Discharge Start (Slot 2)", "register": 43157, "enabled": True},
        {"name": "Solis Time-Charging Discharge End (Slot 2)", "register": 43159, "enabled": True},

        {"name": "Solis Time-Charging Charge Start (Slot 3)", "register": 43163, "enabled": True},
        {"name": "Solis Time-Charging Charge End (Slot 3)", "register": 43165, "enabled": True},
        {"name": "Solis Time-Charging Discharge Start (Slot 3)", "register": 43167, "enabled": True},
        {"name": "Solis Time-Charging Discharge End (Slot 3)", "register": 43169, "enabled": True},

        {"name": "Solis Time-Charging Charge Start (Slot 4)", "register": 43173, "enabled": True},
        {"name": "Solis Time-Charging Charge End (Slot 4)", "register": 43175, "enabled": True},
        {"name": "Solis Time-Charging Discharge Start (Slot 4)", "register": 43177, "enabled": True},
        {"name": "Solis Time-Charging Discharge End (Slot 4)", "register": 43179, "enabled": True},

        {"name": "Solis Time-Charging Charge Start (Slot 5)", "register": 43183, "enabled": True},
        {"name": "Solis Time-Charging Charge End (Slot 5)", "register": 43185, "enabled": True},
        {"name": "Solis Time-Charging Discharge Start (Slot 5)", "register": 43187, "enabled": True},
        {"name": "Solis Time-Charging Discharge End (Slot 5)", "register": 43189, "enabled": True},


        {"name": "Solis Grid Time of Use Charge Start (Slot 1)", "register": 43711, "enabled": True},
        {"name": "Solis Grid Time of Use Charge End (Slot 1)", "register": 43713, "enabled": True},
        {"name": "Solis Time-Charging Discharge Start (Slot 1)", "register": 43753, "enabled": True},
        {"name": "Solis Time-Charging Discharge End (Slot 1)", "register": 43755, "enabled": True},

        {"name": "Solis Grid Time of Use Charge Start (Slot 2)", "register": 43718, "enabled": True},
        {"name": "Solis Grid Time of Use Charge End (Slot 2)", "register": 43720, "enabled": True},
        {"name": "Solis Time-Charging Discharge Start (Slot 2)", "register": 43760, "enabled": True},
        {"name": "Solis Time-Charging Discharge End (Slot 2)", "register": 43762, "enabled": True},

        {"name": "Solis Grid Time of Use Charge Start (Slot 3)", "register": 43725, "enabled": True},
        {"name": "Solis Grid Time of Use Charge End (Slot 3)", "register": 43727, "enabled": True},
        {"name": "Solis Time-Charging Discharge Start (Slot 3)", "register": 43767, "enabled": True},
        {"name": "Solis Time-Charging Discharge End (Slot 3)", "register": 43769, "enabled": True},

        {"name": "Solis Grid Time of Use Charge Start (Slot 4)", "register": 43732, "enabled": True},
        {"name": "Solis Grid Time of Use Charge End (Slot 4)", "register": 43734, "enabled": True},
        {"name": "Solis Grid Time of Use Discharge Start (Slot 4)", "register": 43774, "enabled": True},
        {"name": "Solis Grid Time of Use Discharge End (Slot 4)", "register": 43776, "enabled": True},

        {"name": "Solis Grid Time of Use Charge Start (Slot 5)", "register": 43739, "enabled": True},
        {"name": "Solis Grid Time of Use Charge End (Slot 5)", "register": 43741, "enabled": True},
        {"name": "Solis Grid Time of Use Discharge Start (Slot 5)", "register": 43781, "enabled": True},
        {"name": "Solis Grid Time of Use Discharge End (Slot 5)", "register": 43783, "enabled": True},

        {"name": "Solis Grid Time of Use Charge Start (Slot 6)", "register": 43746, "enabled": True},
        {"name": "Solis Grid Time of Use Charge End (Slot 6)", "register": 43748, "enabled": True},
        {"name": "Solis Grid Time of Use Discharge Start (Slot 6)", "register": 43788, "enabled": True},
        {"name": "Solis Grid Time of Use Discharge End (Slot 6)", "register": 43790, "enabled": True},
    ]

    for entity_definition in timeent:
        timeEntities.append(SolisTimeEntity(hass, modbus_controller, entity_definition))
    async_add_devices(timeEntities, True)


class SolisTimeEntity(TimeEntity):
    """Representation of a Time entity."""

    def __init__(self, hass, modbus_controller, entity_definition):
        """Initialize the Time entity."""
        #
        # Visible Instance Attributes Outside Class
        self._hass = hass
        self._modbus_controller = modbus_controller
        self._register = entity_definition["register"]

        # Hidden Inherited Instance Attributes
        self._attr_unique_id = "{}_{}_{}".format(DOMAIN, self._modbus_controller.host, self._register)
        self._attr_name = entity_definition["name"]
        self._attr_has_entity_name = True
        self._attr_native_value = entity_definition.get("default", None)
        self._attr_available = True
        self._attr_device_class = entity_definition.get("device_class", None)
        self._attr_icon = entity_definition.get("icon", None)
        self._attr_mode = entity_definition.get("mode", NumberMode.AUTO)
        self._attr_entity_registry_enabled_default = entity_definition.get("enabled", False)

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._modbus_controller.host)},
            manufacturer=MANUFACTURER,
            model=self._modbus_controller.model,
            name=f"{MANUFACTURER} {self._modbus_controller.model}",
            sw_version=self._modbus_controller.sw_version,
        )

    @property
    def native_value(self):
        hour = cache_get(self.hass, self._register)
        minute = cache_get(self.hass, self._register + 1)
        if hour is not None and minute is not None:
            return datetime.time(hour=int(hour), minute=int(minute))
        else:
            self._attr_available = False

    async def async_set_value(self, value: time) -> None:
        """Set the time."""
        _LOGGER.debug(f'async_set_value : register = {self._register}, value = {value}')
        await self._modbus_controller.async_write_holding_registers(self._register, [value.hour, value.minute])
        self._attr_native_value = value
        self.async_write_ha_state()
