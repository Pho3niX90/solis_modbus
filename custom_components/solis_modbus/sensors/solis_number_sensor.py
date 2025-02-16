import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import RestoreSensor

from custom_components.solis_modbus import ModbusController, DOMAIN
from custom_components.solis_modbus.const import VALUES
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

_LOGGER = logging.getLogger(__name__)

import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import RestoreSensor
from homeassistant.core import callback
from custom_components.solis_modbus import ModbusController, DOMAIN
from custom_components.solis_modbus.const import VALUES, REGISTER
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor
from custom_components.solis_modbus.helpers import cache_get

_LOGGER = logging.getLogger(__name__)

class SolisNumberEntity(RestoreSensor, NumberEntity):
    """Representation of a Number entity."""

    def __init__(self, hass, modbus_controller, sensor: SolisBaseSensor):
        """Initialize the Number entity."""
        self._hass = hass
        self.base_sensor = sensor
        self._modbus_controller: ModbusController = modbus_controller
        self._register = sensor.registrars  # Multi-register support
        self._multiplier = sensor.multiplier

        # Unique ID based on all registers
        self._attr_unique_id = "{}_{}_{}".format(DOMAIN, self._modbus_controller.host, "_".join(map(str, self._register)))
        self._attr_has_entity_name = True
        self._attr_name = sensor.name
        self._attr_native_value = sensor.default
        self._attr_available = False
        self.is_added_to_hass = False
        self._attr_device_class = sensor.device_class
        self._attr_mode = NumberMode.AUTO
        self._attr_native_unit_of_measurement = sensor.unit_of_measurement
        self._attr_native_min_value = sensor.min_value
        self._attr_native_max_value = sensor.max_value
        self._attr_native_step = sensor.step
        self._attr_should_poll = False
        self._attr_entity_registry_enabled_default = sensor.enabled

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
        self._hass.bus.async_listen("solis_modbus_update", self.handle_modbus_update)

    @callback
    def handle_modbus_update(self, event):
        """Callback function that updates sensor when new register data is available."""
        updated_register = int(event.data.get(REGISTER))

        # If this register belongs to the sensor, store it temporarily
        if updated_register in self._register:
            self._received_values[updated_register] = cache_get(self._hass, updated_register)

            # Wait until all registers have been received
            if not all(reg in self._received_values for reg in self._register):
                return  # Wait for remaining registers

            # All registers received, combine the values
            all_values = [self._received_values[reg] for reg in self._register]

            # 🔄 Combine registers based on type
            if len(self._register) == 1:
                new_value = all_values[0]  # Single register value
            elif len(self._register) == 2:
                # Example: Handling U32/S32 conversions (2 registers)
                new_value = (all_values[0] << 16) | all_values[1]

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
            self._modbus_controller.async_write_holding_register(self._register, register_value)
        )

        self._attr_native_value = value
        self.schedule_update_ha_state()

