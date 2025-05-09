import logging
from datetime import datetime, UTC, time
from typing import List
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.const import DOMAIN, MANUFACTURER, REGISTER, VALUE, CONTROLLER, TIME_ENTITIES
from custom_components.solis_modbus.data.enums import InverterType, InverterFeature
from custom_components.solis_modbus.helpers import get_controller, cache_get

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


class SolisTimeEntity(RestoreSensor, TimeEntity):
    """Representation of a Time entity."""

    def __init__(self, hass, modbus_controller, entity_definition):
        """Initialize the Time entity."""
        #
        # Visible Instance Attributes Outside Class
        self._hass = hass
        self._modbus_controller = modbus_controller
        self._register: int = entity_definition["register"]

        # Hidden Inherited Instance Attributes
        self._attr_unique_id = "{}_{}_{}".format(DOMAIN, self._modbus_controller.host, self._register)
        self._attr_name = entity_definition["name"]
        self._attr_has_entity_name = True
        self._attr_available = True
        self._attr_device_class = entity_definition.get("device_class", None)
        self._attr_available = True

        self._received_values = {}

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to HA."""
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

        # 🔥 Register event listener for real-time updates
        self._hass.bus.async_listen(DOMAIN, self.handle_modbus_update)

    @callback
    def handle_modbus_update(self, event):
        """Callback function that updates sensor when new register data is available."""
        updated_register = int(event.data.get(REGISTER))

        updated_controller = str(event.data.get(CONTROLLER))

        if updated_controller != self._modbus_controller.host:
            return # meant for a different sensor/inverter combo

        if updated_register == self._register:
            value = event.data.get(VALUE)
            if self._attr_device_class == SensorDeviceClass.TIMESTAMP:
                if isinstance(value, datetime):
                    updated_value = value
                else:
                    updated_value = datetime.now(UTC)
            else:
                updated_value = int(value)
            _LOGGER.debug(f"Sensor update received, register = {updated_register}, value = {updated_value}")
            self._received_values[updated_register] = updated_value

            if updated_value is not None:
                hour = cache_get(self.hass, self._register)
                minute = cache_get(self.hass, self._register + 1)

                if hour is not None and minute is not None:
                    hour, minute = int(hour), int(minute)

                    if 0 <= minute <= 59 and 0 <= hour <= 23:
                        _LOGGER.debug(f"✅ Time updated to {hour}:{minute}, regs = {self._register}:{self._register + 1}")
                        self._attr_native_value = time(hour=hour, minute=minute)
                        self._attr_available = True
                    else:
                        self._attr_available = False
                        _LOGGER.debug(f"⚠️ Time disabled due to invalid values {hour}:{minute}, regs = {self._register}:{self._register + 1}")
                else:
                    self._attr_available = False
                    _LOGGER.debug(f"⚠️ Time disabled because hour or minute is None, regs = {self._register}:{self._register + 1}")


                self.schedule_update_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._modbus_controller.host)},
            manufacturer=MANUFACTURER,
            model=self._modbus_controller.model,
            name=f"{MANUFACTURER} {self._modbus_controller.model}{self._modbus_controller.device_identification}",
            sw_version=self._modbus_controller.sw_version,
        )

    async def async_set_value(self, value: time) -> None:
        """Set the time."""
        _LOGGER.debug(f'async_set_value : register = {self._register}, value = {value}')
        await self._modbus_controller.async_write_holding_registers(self._register, [value.hour, value.minute])
        self._attr_native_value = value
        self.async_write_ha_state()
