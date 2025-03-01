import logging
from typing import List

from homeassistant.config_entries import ConfigEntry

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, TIME_ENTITIES
from custom_components.solis_modbus.data.enums import InverterType, InverterFeature
from custom_components.solis_modbus.helpers import get_controller
from custom_components.solis_modbus.sensors.solis_time_entity import SolisTimeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    """Set up the time platform."""
    modbus_controller: ModbusController = get_controller(hass, config_entry.data.get("host"))

    inverter_config = modbus_controller.inverter_config

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
    ]

    if inverter_config.type == InverterType.HYBRID or InverterFeature.V2 in inverter_config.features:
        timeent.extend([
            {"name": "Solis Grid Time of Use Charge Start (Slot 1)", "register": 43711, "enabled": True},
            {"name": "Solis Grid Time of Use Charge End (Slot 1)", "register": 43713, "enabled": True},
            {"name": "Solis Grid Time of Use Discharge Start (Slot 1)", "register": 43753, "enabled": True},
            {"name": "Solis Grid Time of Use Discharge End (Slot 1)", "register": 43755, "enabled": True},

            {"name": "Solis Grid Time of Use Charge Start (Slot 2)", "register": 43718, "enabled": True},
            {"name": "Solis Grid Time of Use Charge End (Slot 2)", "register": 43720, "enabled": True},
            {"name": "Solis Grid Time of Use Discharge Start (Slot 2)", "register": 43760, "enabled": True},
            {"name": "Solis Grid Time of Use Discharge End (Slot 2)", "register": 43762, "enabled": True},

            {"name": "Solis Grid Time of Use Charge Start (Slot 3)", "register": 43725, "enabled": True},
            {"name": "Solis Grid Time of Use Charge End (Slot 3)", "register": 43727, "enabled": True},
            {"name": "Solis Grid Time of Use Discharge Start (Slot 3)", "register": 43767, "enabled": True},
            {"name": "Solis Grid Time of Use Discharge End (Slot 3)", "register": 43769, "enabled": True},

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
        ])

    for entity_definition in timeent:
        timeEntities.append(SolisTimeEntity(hass, modbus_controller, entity_definition))
    hass.data[DOMAIN][TIME_ENTITIES] = timeEntities
    async_add_devices(timeEntities, True)