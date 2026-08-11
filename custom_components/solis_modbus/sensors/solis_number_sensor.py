import logging

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.solis_modbus.const import CONTROLLER, REGISTER, SLAVE, VALUE
from custom_components.solis_modbus.helpers import is_correct_controller, register_update_signal
from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

_LOGGER = logging.getLogger(__name__)


class SolisNumberEntity(RestoreNumber, NumberEntity):
    """Representation of a Number entity."""

    def __init__(self, hass, sensor: SolisBaseSensor):
        self._hass = hass
        self.base_sensor = sensor

        self._attr_name = sensor.name
        self._attr_has_entity_name = True
        self._attr_unique_id = sensor.unique_id

        self._register: list[int] = sensor.registrars
        _LOGGER.debug(f"read_register = {sensor.registrars} | write_register {sensor.write_register}")
        self._write_register: int = sensor.write_register if sensor.write_register is not None else self._register[0] if len(self._register) == 1 else None

        self._device_class = sensor.device_class
        self._unit_of_measurement = sensor.unit_of_measurement
        self._attr_device_class = sensor.device_class
        self._attr_state_class = sensor.state_class
        self._attr_native_unit_of_measurement = sensor.unit_of_measurement
        self._attr_available = not sensor.hidden and sensor.enabled

        self._received_values = {}

        self._multiplier = sensor.multiplier

        # Unique ID based on all registers
        self._attr_native_value = sensor.default
        self._attr_mode = NumberMode.AUTO
        self._attr_native_min_value = sensor.min_value
        # Static by design: a declared max or the protocol ceiling, never a live device
        # limit. HA rejects set_value above this, so a moving bound meant intermittent
        # out_of_range failures and states above their own max (#464, #467). The live
        # limit is advisory — see extra_state_attributes.
        self._attr_native_max_value = sensor.max_value

        self._attr_native_step = sensor.step
        self._attr_step = sensor.step
        self._attr_should_poll = False
        self._attr_entity_registry_enabled_default = sensor.enabled

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Restore the *value* only. Restoring bounds from a snapshot is the same trap
        # as deriving them live (#464/#467): a stale or momentary min/max/step comes
        # back as a hard limit HA then enforces on writes.
        state = await self.async_get_last_number_data()
        if state:
            self._attr_native_value = state.native_value

        for reg in set(self._register):
            self.async_on_remove(
                async_dispatcher_connect(
                    self._hass,
                    register_update_signal(self.base_sensor.controller, reg),
                    self.handle_modbus_update,
                )
            )

        # Battery-current setpoints carry an advisory limit from a BMS mirror register
        # that this entity doesn't otherwise read; follow it so the device_limit
        # attribute refreshes when the battery reports a new limit.
        mirror = getattr(self.base_sensor, "battery_current_mirror_register", None)
        if isinstance(mirror, int):
            self.async_on_remove(
                async_dispatcher_connect(
                    self._hass,
                    register_update_signal(self.base_sensor.controller, mirror),
                    self.handle_device_limit_update,
                )
            )

        if not self.base_sensor.enabled:
            self._attr_available = False

    @property
    def extra_state_attributes(self):
        """Surface the live device limit next to the setpoint, without enforcing it.

        Keeps "what may be configured" (the native min/max) and "what the device can
        do right now" as the two different things they are (#464, #467): dashboards
        and automations can read the limit here, while writes above it stay valid —
        the device enforces its own limit at runtime.
        """
        source = self.base_sensor.device_limit_source
        if source is None:
            return None
        return {
            "device_limit": self.base_sensor.device_limit,
            "device_limit_source": source,
        }

    @callback
    def handle_device_limit_update(self, data):
        """The BMS reported a new current limit — refresh the advisory attribute."""
        if not is_correct_controller(self.base_sensor.controller, str(data.get(CONTROLLER)), int(data.get(SLAVE))):
            return
        self.schedule_update_ha_state()

    @callback
    def handle_modbus_update(self, data):
        """Callback when register data is available (per-register dispatcher)."""
        updated_register = int(data.get(REGISTER))
        updated_controller = str(data.get(CONTROLLER))
        updated_controller_slave = int(data.get(SLAVE))

        if not is_correct_controller(self.base_sensor.controller, updated_controller, updated_controller_slave):
            return  # meant for a different sensor/inverter combo

        if not self.base_sensor.enabled:
            return

        if updated_register in self._register:
            updated_value = int(data.get(VALUE))

            self._received_values[updated_register] = updated_value

            # Wait until all registers have been received
            if not all(reg in self._received_values for reg in self._register):
                _LOGGER.debug(f"not all values received yet = {self._received_values}")
                return

            new_value = self.base_sensor.convert_value([updated_value])

            # Clear received values after update
            self._received_values.clear()

            # Update state if valid value exists
            if new_value is not None:
                self._attr_native_value = new_value
                self.schedule_update_ha_state()

    def set_native_value(self, value):
        """Update the current value."""
        if self._attr_native_value == value:
            return

        # 🔹 Handle multi-register writing
        if self._write_register is None:
            return

        # Advisory only — warn, never clamp or reject. Clamping would corrupt scheduled
        # TOU config written while the BMS is derated (#467) and recreate the ratchet on
        # firmware whose mirror echoes the setpoint (#464); the device enforces its real
        # limit itself. abs(): signed dispatch registers are symmetric about zero.
        limit = getattr(self.base_sensor, "device_limit", None)
        if isinstance(limit, (int, float)) and not isinstance(limit, bool) and abs(value) > limit:
            _LOGGER.warning(
                "%s: requested %s exceeds the device's currently reported limit of %s (%s); writing anyway — the device enforces its own limit",
                self._attr_name,
                value,
                limit,
                self.base_sensor.device_limit_source,
            )

        register_value = round(value / self._multiplier)
        if self.base_sensor.data_type == "S16":
            register_value = max(-32768, min(32767, register_value))
            register_value &= 0xFFFF

        # Write to Modbus controller
        self._hass.create_task(self.base_sensor.controller.async_write_holding_register(self._write_register, int(register_value)))

        self._attr_native_value = value
        self.schedule_update_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return self.base_sensor.controller.device_info
