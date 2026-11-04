"""Experimental signed battery dispatch for Solis hybrid inverters.

Firmware-dependent RC registers: queued Modbus writes are NOT verified output.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.event import async_track_time_interval

from .helpers import unique_id_generator

_LOGGER = logging.getLogger(__name__)

MODE = 43135
DISCHARGE = 43129
CHARGE = 43136
RC_TIMEOUT = 43282


class SolisDispatchCoordinator:
    """Translate signed battery power into serialized remote-control writes."""

    def __init__(self, hass, controller):
        self.hass = hass
        self.controller = controller
        self.self_use = True
        self.target_w = 0
        self.last_error = None
        self.last_request = None
        self.refresh_interval = 30
        self._lock = asyncio.Lock()
        self._unsub = None
        self.entities = []

    async def start(self):
        self._unsub = async_track_time_interval(
            self.hass, self._heartbeat, timedelta(seconds=self.refresh_interval)
        )

    async def stop(self):
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    def notify(self):
        for entity in self.entities:
            entity.async_write_ha_state()

    async def set_self_use(self, enabled: bool):
        async with self._lock:
            if enabled:
                await self._write_off()
                self.self_use = True
            else:
                if self.target_w:
                    await self._write_target(self.target_w)
                self.self_use = False
            self.notify()

    async def set_power(self, watts: float):
        if not (-self.max_w <= watts <= self.max_w):
            raise ValueError(f"Solis dispatch target must be within +/-{self.max_w} W")
        watts = int(round(watts / 10)) * 10
        async with self._lock:
            if not self.self_use:
                if watts:
                    await self._write_target(watts)
                else:
                    await self._write_off()
            self.target_w = watts
            self.notify()

    @property
    def max_w(self):
        return min(int(getattr(self.controller.inverter_config, "wattage_chosen", 5000)), 655350)

    async def _write_off(self):
        if not self.controller.connected():
            self.last_error = "Modbus disconnected; RC off not delivered"
            raise RuntimeError(self.last_error)
        await self.controller.async_write_holding_register(MODE, 0)
        self.last_error = None
        self.last_request = "RC off queued"

    async def _write_target(self, watts: int):
        if not self.controller.connected():
            self.last_error = "Modbus disconnected; dispatch not delivered"
            raise RuntimeError(self.last_error)
        mode = 2 if watts > 0 else 1
        raw = abs(watts) // 10
        async with self.controller.write_batch():
            await self.controller.async_write_holding_register(MODE, mode)
            await self.controller.async_write_holding_register(DISCHARGE if watts > 0 else CHARGE, raw)
            await self.controller.async_write_holding_register(RC_TIMEOUT, 2)
        self.last_error = None
        self.last_request = f"{watts} W RC command queued; actual output unverified"

    async def _heartbeat(self, _now=None):
        if self.self_use or self.target_w == 0 or self._lock.locked():
            return
        async with self._lock:
            try:
                await self._write_target(self.target_w)
            except Exception as exc:
                self.last_error = str(exc)
                _LOGGER.warning("Solis RC refresh failed: %s", exc)
            self.notify()


class SolisDispatchPower(NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Dispatch battery power"
    _attr_native_unit_of_measurement = "W"
    _attr_mode = NumberMode.BOX
    _attr_native_step = 10
    _attr_should_poll = False

    def __init__(self, coord):
        self.coord = coord
        self._attr_unique_id = unique_id_generator(coord.controller, "battery_dispatch_power", "rc")
        self._attr_native_min_value = -coord.max_w
        self._attr_native_max_value = coord.max_w

    @property
    def device_info(self):
        return self.coord.controller.device_info

    @property
    def native_value(self):
        return self.coord.target_w

    @property
    def extra_state_attributes(self):
        return {
            "command_status": self.coord.last_request,
            "error": self.coord.last_error,
            "note": "Requested watts only. Verify physical output using battery power telemetry.",
        }

    async def async_set_native_value(self, value):
        await self.coord.set_power(value)


class SolisDispatchSelfUse(SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Dispatch self use"
    _attr_should_poll = False

    def __init__(self, coord):
        self.coord = coord
        self._attr_unique_id = unique_id_generator(coord.controller, "battery_dispatch_self_use", "rc")

    @property
    def device_info(self):
        return self.coord.controller.device_info

    @property
    def is_on(self):
        return self.coord.self_use

    @property
    def extra_state_attributes(self):
        return {
            "mode": "self_use" if self.coord.self_use else "remote_dispatch",
            "status": self.coord.last_request,
            "error": self.coord.last_error,
            "firmware_support": "not verified",
        }

    async def async_turn_on(self, **kwargs):
        await self.coord.set_self_use(True)

    async def async_turn_off(self, **kwargs):
        await self.coord.set_self_use(False)
