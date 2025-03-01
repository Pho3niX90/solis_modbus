import datetime
import logging
from homeassistant.components.sensor import RestoreSensor
from homeassistant.components.time import TimeEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.solis_modbus.const import REGISTER, CONTROLLER, VALUE, DOMAIN, MANUFACTURER
from custom_components.solis_modbus.helpers import cache_get

_LOGGER = logging.getLogger(__name__)

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
        updated_value = int(event.data.get(VALUE))
        updated_controller = str(event.data.get(CONTROLLER))

        if updated_controller != self._modbus_controller.host:
            return # meant for a different sensor/inverter combo

        if updated_register == self._register:
            _LOGGER.debug(f"Sensor update received, register = {updated_register}, value = {updated_value}")
            self._received_values[updated_register] = updated_value

            if updated_value is not None:
                hour = cache_get(self.hass, self._register)
                minute = cache_get(self.hass, self._register + 1)

                if hour is not None and minute is not None:
                    hour, minute = int(hour), int(minute)

                    if 0 <= minute <= 59 and 0 <= hour <= 23:
                        _LOGGER.debug(f"✅ Time updated to {hour}:{minute}, regs = {self._register}:{self._register + 1}")
                        self._attr_native_value = datetime.time(hour=hour, minute=minute)
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
            name=f"{MANUFACTURER} {self._modbus_controller.model}",
            sw_version=self._modbus_controller.sw_version,
        )

    async def async_set_value(self, value: datetime.time) -> None:
        """Set the time."""
        _LOGGER.debug(f'async_set_value : register = {self._register}, value = {value}')
        await self._modbus_controller.async_write_holding_registers(self._register, [value.hour, value.minute])
        self._attr_native_value = value
        self.async_write_ha_state()
