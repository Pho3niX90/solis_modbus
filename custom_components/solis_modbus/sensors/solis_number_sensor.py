import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import RestoreSensor
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.solis_modbus.const import REGISTER, DOMAIN, VALUE, CONTROLLER, MANUFACTURER
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

_LOGGER = logging.getLogger(__name__)

class SolisNumberEntity(RestoreSensor, NumberEntity):
    """Representation of a Number entity."""

    def __init__(self, hass, sensor: SolisBaseSensor):
        """Initialize the Number entity."""
        self._hass = hass
        self.base_sensor = sensor
        self._register = sensor.registrars  # Multi-register support
        self._multiplier = sensor.multiplier

        self._device_class = sensor.device_class
        self._unit_of_measurement  = sensor.unit_of_measurement
        self._attr_device_class = sensor.device_class
        self._attr_state_class = sensor.state_class
        self._attr_native_unit_of_measurement = sensor.unit_of_measurement

        # Unique ID based on all registers
        #"{}_{}_{}".format(DOMAIN, self.base_sensor.controller.host, "_".join(map(str, self._register)))
        self._attr_unique_id = sensor.unique_id
        self._attr_has_entity_name = True
        self._attr_name = sensor.name
        self._attr_native_value = sensor.default
        self.is_added_to_hass = False
        self._attr_mode = NumberMode.AUTO
        self._attr_native_min_value = sensor.min_value
        self._attr_native_max_value = sensor.max_value
        self._attr_native_step = sensor.step
        self._attr_should_poll = False
        self._attr_entity_registry_enabled_default = sensor.enabled
        self._attr_available = not sensor.hidden

        # 🔹 Track received register values before updating
        self._received_values = {}

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to HA."""
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

        self.is_added_to_hass = True

        # 🔥 Register event listener for real-time updates
        self._hass.bus.async_listen(DOMAIN, self.handle_modbus_update)

    @callback
    def handle_modbus_update(self, event):
        """Callback function that updates sensor when new register data is available."""
        updated_register = int(event.data.get(REGISTER))
        updated_value = int(event.data.get(VALUE))
        updated_controller = str(event.data.get(CONTROLLER))

        if updated_controller != self.base_sensor.controller.host:
            return # meant for a different sensor/inverter combo

        if updated_register in self._register:
            self._received_values[updated_register] = updated_value

            # Wait until all registers have been received
            if not all(reg in self._received_values for reg in self._register):
                _LOGGER.debug(f"not all values received yet = {self._received_values}")
                return

            new_value = self.base_sensor.get_value

            # Clear received values after update
            self._received_values.clear()

            # Update state if valid value exists
            if new_value is not None:
                self._attr_native_value = round(new_value / self._multiplier)
                self.schedule_update_ha_state()

    def set_native_value(self, value):
        """Update the current value."""
        if self._attr_native_value == value:
            return

        # 🔹 Handle multi-register writing
        if len(self._register) == 1:
            register_value = round(value * self._multiplier)
        elif len(self._register) == 2:
            # Convert the value into two 16-bit registers
            int_value = round(value * self._multiplier)
            register_value = [(int_value >> 16) & 0xFFFF, int_value & 0xFFFF]
        else:
            _LOGGER.warning("More than 2 registers not yet supported for writing.")
            return

        # Write to Modbus controller
        self.hass.create_task(
            self.base_sensor.controller.async_write_holding_register(self._register, register_value)
        )

        self._attr_native_value = value
        self.schedule_update_ha_state()


    @property
    def native_value(self):
        """Retrieve sensor value from cache."""
        return self.base_sensor.get_value

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.base_sensor.controller.host)},
            manufacturer=MANUFACTURER,
            model=self.base_sensor.controller.model,
            name=f"{MANUFACTURER} {self.base_sensor.controller.model}",
            sw_version=self.base_sensor.controller.sw_version,
        )

