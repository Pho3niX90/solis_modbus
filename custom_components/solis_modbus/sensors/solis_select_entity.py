import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.restore_state import RestoreEntity

from custom_components.solis_modbus import ModbusController
from custom_components.solis_modbus.helpers import cache_get, cache_save, get_bit_bool, set_bit, unique_id_generator

_LOGGER = logging.getLogger(__name__)


class SolisSelectEntity(RestoreEntity, SelectEntity):
    def __init__(self, hass, modbus_controller, entity_definition) -> None:
        self._hass = hass
        self._modbus_controller: ModbusController = modbus_controller
        self._register = entity_definition["register"]
        self._attr_name = entity_definition["name"]
        self._attr_has_entity_name = True
        self._attr_unique_id = unique_id_generator(modbus_controller, entity_definition["register"], "select")

        self._attr_options = [e["name"] for e in entity_definition["entities"]]
        self._attr_options_raw = entity_definition["entities"]
        self._companion_writes = entity_definition.get("companion_writes") or []
        self._current_option = None

    @property
    def current_option(self) -> str | None:
        reg_cache = cache_get(self._hass, self._modbus_controller, self._register)
        if reg_cache is None:
            return

        # Sort by number of requires descending to prioritize more specific matches
        sorted_options = sorted(self._attr_options_raw, key=lambda e: len(e.get("requires", [])) if "requires" in e else 0, reverse=True)

        # Two passes: strict first (an option only matches when its conflicting bits,
        # other than its own/required ones, are clear — makes resolution independent
        # of file order, e.g. 43110=35 must not read as plain "Self-Use"), then a
        # lenient pass so degenerate leftover combos (e.g. Peak Shaving with a stray
        # TOU bit written by older versions) still resolve to the nearest option.
        for strict in (True, False):
            for e in sorted_options:
                on_value = e.get("on_value")
                bit_position = e.get("bit_position")
                requires = e.get("requires") or []

                if on_value is not None:
                    if reg_cache == on_value:
                        return e["name"]
                elif bit_position is not None:
                    if not get_bit_bool(reg_cache, bit_position):
                        continue
                    if not all(get_bit_bool(reg_cache, rbit) for rbit in requires):
                        continue
                    if strict:
                        own_bits = {bit_position, *requires}
                        conflicts = [cbit for cbit in (e.get("conflicts_with") or []) if cbit not in own_bits]
                        if any(get_bit_bool(reg_cache, cbit) for cbit in conflicts):
                            continue
                    return e["name"]

        return None

    @property
    def extra_state_attributes(self):
        """Expose the raw register so unmatched bit combos are debuggable."""
        reg_cache = cache_get(self._hass, self._modbus_controller, self._register)
        if reg_cache is None:
            return None
        return {
            "raw_value": reg_cache,
            "set_bits": [bit for bit in range(16) if (int(reg_cache) >> bit) & 1],
        }

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        for e in self._attr_options_raw:
            on_value = e.get("on_value", None)
            bit_position = e.get("bit_position", None)
            conflicts_with = e.get("conflicts_with", None)
            requires = e.get("requires", None)

            if e["name"] == option:
                if on_value is not None:
                    await self._modbus_controller.async_write_holding_register(self._register, on_value)
                    await self._write_companions()
                    self._attr_current_option = option
                    self.async_write_ha_state()
                    break
                else:
                    await self.set_register_bit(on_value, bit_position, conflicts_with, requires)

    @property
    def device_info(self):
        """Return device info."""
        return self._modbus_controller.device_info

    async def _write_companions(self) -> None:
        """Re-write companion registers from cache after the primary write.

        Some Solis firmware revisions require certain registers to be written in a
        specific order for the values to latch (e.g. RC Timeout only takes effect if
        Forced Charge/Discharge has been enabled first). Re-writing companion
        registers here forms the second half of that combo.
        """
        for companion_register in self._companion_writes:
            cached = cache_get(self._hass, self._modbus_controller, companion_register)
            if cached is None:
                _LOGGER.debug(
                    "Skipping companion write for register %s: no cached value yet",
                    companion_register,
                )
                continue
            await self._modbus_controller.async_write_holding_register(companion_register, cached)

    async def set_register_bit(self, on_value, bit_position, conflicts_with, requires):
        """Set or clear a specific bit in the Modbus register."""
        controller = self._modbus_controller
        current_register_value: int = cache_get(self._hass, self._modbus_controller, self._register)

        if current_register_value is None and bit_position is not None:
            # A read-modify-write from an empty cache (e.g. right after a reload,
            # before this register's group has been polled) would start from 0 and
            # clear every other bit in the register (issue #402). Read the live
            # value from the inverter first.
            registers = await controller.async_read_holding_register(self._register, 1)
            if not registers:
                _LOGGER.warning(
                    f"({controller.host}) Cannot set bit {bit_position} of register {self._register}: "
                    f"no cached value and live read failed; skipping write to avoid clearing other bits"
                )
                return
            current_register_value = registers[0]
            cache_save(self._hass, controller, self._register, current_register_value)

        new_register_value = current_register_value

        if bit_position is not None:
            # Clear conflicts
            if conflicts_with:
                for wbit in conflicts_with:
                    new_register_value = set_bit(new_register_value, wbit, False)

            # Set dependencies
            if requires:
                for rbit in requires:
                    new_register_value = set_bit(new_register_value, rbit, True)

            new_register_value = set_bit(new_register_value, bit_position, True)

        else:
            new_register_value = on_value

        _LOGGER.debug(f"Attempting bit {bit_position} to {True} in register {self._register}. New value for register {new_register_value}")
        # Compare against the value the device currently holds (not a partially
        # mutated working copy) so clearing a conflict bit alone still triggers a write.
        if current_register_value != new_register_value and controller.connected():
            await controller.async_write_holding_register(self._register, new_register_value)
            cache_save(self._hass, self._modbus_controller, self._register, new_register_value)
        self._attr_available = True
