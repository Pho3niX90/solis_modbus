# solis_base.py
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant

from custom_components.solis_modbus.data.enums import Category, DataType, InverterFeature, PollSpeed
from custom_components.solis_modbus.helpers import (
    _any_in,
    cache_get,
    combine_u32,
    combine_u32_le,
    extract_serial_number,
    split_s32,
    split_s32_le,
    unique_id_generator,
)

_LOGGER = logging.getLogger(__name__)

# Raw value range per register width, used to derive the *protocol ceiling*: the largest
# value a register can physically carry. This is the generic fallback for definitions that
# declare no "max" — it is never wrong-low, and unlike a guess it needs no per-model
# knowledge. Deriving a ceiling from the inverter's AC rating instead is what produced
# issues #438 and #455.
DATA_TYPE_RAW_RANGES = {
    DataType.U16.value: (0, 65535),
    DataType.S16.value: (-32768, 32767),
    DataType.U32.value: (0, 4294967295),
    DataType.U32_LE.value: (0, 4294967295),
    DataType.S32.value: (-2147483648, 2147483647),
    DataType.S32_LE.value: (-2147483648, 2147483647),
}

# Definitions tag the limit the inverter's rated output governs with
# "max_source": "inverter_rating" — the remote-control dispatch and battery-power
# setpoints. The rating is surfaced as an advisory ``device_limit``, never as the
# advertised max: HA rejects service calls above the advertised max, so a wrong-low
# rating (misconfigured model, DC-side charging above the AC nameplate) would turn
# into hard write failures — the same failure mode as #464/#467 on the BMS mirrors.
# Never applied to grid-side registers (#438) and never inferred from the unit, which
# is what made the old derivation retarget registers it never considered.
MAX_SOURCE_INVERTER_RATING = "inverter_rating"

# Battery-current setpoints, mapped to the BMS mirror register that publishes the
# battery's own current limit. The mirrors are surfaced as an advisory ``device_limit``
# (entity attribute + warning on write), NOT as the advertised max. Two field reports
# disqualified them as bounds on what may be *configured*:
#
#   #467 — a real BMS (Dyness HV) derates the limit with SOC, so it moves through the
#          day: the number's state ended up above its own max, TOU slots (scheduled
#          config) were bounded by the instant the page was opened, and automation
#          writes intermittently raised out_of_range.
#   #464 — some firmware echoes the effective setpoint back on the mirror, so lowering
#          the setpoint lowered the advertised max: a one-way ratchet (users stuck at
#          1-2 A until they went through Solis Cloud).
#
# The TOU slot and time-charging currents are mapped for the same reason the four
# originals are (#455): their old literals (135 A / 300 A) sat below both a 15 kW LV
# bank's ~293 A and the 580 A a parallel pair reports (#351).
BATTERY_CURRENT_MIRROR_REGISTERS = {
    # --- charge -> Battery Max Charge Current Mirror ---
    43012: 33206,  # Max Charge Current
    43117: 33206,  # Battery Max Charge Current
    43141: 33206,  # Time-Charging Charge Current
    43709: 33206,  # Grid TOU Charge battery current (Slot 1)
    43716: 33206,  # Grid TOU Charge battery current (Slot 2)
    43723: 33206,  # Grid TOU Charge battery current (Slot 3)
    43730: 33206,  # Grid TOU Charge battery current (Slot 4)
    43737: 33206,  # Grid TOU Charge battery current (Slot 5)
    43744: 33206,  # Grid TOU Charge battery current (Slot 6)
    # --- discharge -> Battery Max Discharge Current Mirror ---
    43013: 33207,  # Max Discharge Current
    43118: 33207,  # Battery Max Discharge Current
    43142: 33207,  # Time-Charging Discharge Current
    43751: 33207,  # Grid TOU Discharge battery current (Slot 1)
    43758: 33207,  # Grid TOU Discharge battery current (Slot 2)
    43765: 33207,  # Grid TOU Discharge battery current (Slot 3)
    43772: 33207,  # Grid TOU Discharge battery current (Slot 4)
    43779: 33207,  # Grid TOU Discharge battery current (Slot 5)
    43786: 33207,  # Grid TOU Discharge battery current (Slot 6)
}

# The mirrors are U16 on a 0.1 A scale, same as the setpoints they bound.
BATTERY_CURRENT_MIRROR_MULTIPLIER = 0.1

# Grid TOU cut-off voltage: charge slots 1-6, then discharge slots 1-6.
_TOU_CUTOFF_VOLTAGE_REGISTERS = (43710, 43717, 43724, 43731, 43738, 43745, 43752, 43759, 43766, 43773, 43780, 43787)

# Battery voltage setpoints. The protocol gives one range for LV banks and a much wider
# one for HV: "Range:40—48 ... HV Series- Default:120; Range 100-999" (ESINV-33000ID, the
# 33208-33211 read-side equivalents). The shipped literals cover the LV case only, which
# leaves an HV owner — a 480 V pack is ordinary — unable to set these at all.
HV_BATTERY_VOLTAGE_REGISTERS = {
    43016,  # Floating Charge Voltage
    43017,  # Equalizing Charge Voltage
    43020,  # Overdischarge Voltage
    43021,  # Forcecharge Voltage
    *_TOU_CUTOFF_VOLTAGE_REGISTERS,
}

# The upper bound of that HV range. The lower bound (100 V) is deliberately not applied:
# an inverter reporting a value below it would land outside its own entity's range.
HV_BATTERY_VOLTAGE_MAX = 999


class SolisBaseSensor:
    """Base class for all Solis sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        controller,
        unique_id: str,
        name: str,
        registrars: list[int],
        write_register: int,
        multiplier: float,
        device_class: SwitchDeviceClass | SensorDeviceClass | str = None,
        unit_of_measurement: UnitOfElectricPotential | UnitOfApparentPower | UnitOfElectricCurrent | UnitOfPower = None,
        editable: bool = False,
        state_class: SensorStateClass = None,
        default=None,
        step=0.1,
        hidden=False,
        enabled=True,
        category: Category = None,
        min_value: int | None = None,
        max_value: int | None = None,
        max_source: str | None = None,
        identification=None,
        poll_speed=PollSpeed.NORMAL,
        data_type: str | None = None,
    ):
        """
        :param name: Sensor name
        :param registrars: First register address
        """
        self.hass = hass
        self.unique_id = unique_id
        self.controller = controller
        self.name = name
        self.default = default
        self.registrars = registrars
        self.write_register = write_register
        _LOGGER.debug(" self.registrars = %s | self.write_register = %s", self.registrars, self.write_register)
        self.editable = editable
        self.multiplier = multiplier

        if isinstance(data_type, DataType):
            self.data_type = data_type.value
        elif data_type is not None and any(data_type == item.value for item in DataType):
            self.data_type = data_type
        elif data_type is not None:
            _LOGGER.warning(f"Invalid data_type '{data_type}' for sensor {name}, falling back to None")
            self.data_type = None
        else:
            self.data_type = None

        self.device_class = device_class
        self.unit_of_measurement = unit_of_measurement
        self.hidden = hidden
        self.state_class = state_class
        # min before max: adjust_max also resolves the floor of a signed register
        # (marked by a negative declared min), so it needs the min already in place.
        self.min_value = min_value
        self.max_source = max_source
        self.adjust_max(max_value)
        self.step = self.get_step(step)
        self.enabled = enabled
        self.poll_speed = poll_speed
        self.category = category
        self.identification = identification

        self.dynamic_adjustments()

    def dynamic_adjustments(self):
        inv_model = self.controller.inverter_config.model
        inv_features = self.controller.inverter_config.features

        # HV battery-specific adjustments
        if InverterFeature.HV_BATTERY in inv_features:
            hv_battery_sensitive_regs = {33205, 33206, 33207, 43013, 43117}
            if _any_in(self.registrars, hv_battery_sensitive_regs):
                self.min_value = 0
                self.step = 0.1 if self.step is None else min(self.step, 0.1)

            # The declared voltage maxima describe a 48 V bank. On HV the protocol allows
            # 100-999 V, and a 480 V pack is ordinary — leave the LV literal in place and
            # an HV owner cannot set these at all.
            if _any_in(self.registrars, HV_BATTERY_VOLTAGE_REGISTERS):
                self.max_value = HV_BATTERY_VOLTAGE_MAX

        # RHI/RAI models: 1 <--> 1W (range: 0–30000)
        if inv_model in {"RHI-1P", "RHI-3P", "RAI-3K-48ES-5G"} and 43074 in self.registrars:
            self.multiplier = 1

        # S6-EH3P10K-H-ZP or ZONNEPLAN feature: apply 0.01 multiplier
        elif inv_model == "S6-EH3P10K-H-ZP" or InverterFeature.ZONNEPLAN in inv_features:
            s6_registers = {33142, 33161, 33162, 33163, 33164, 33165, 33166, 33167, 33168}
            if _any_in(self.registrars, s6_registers):
                self.multiplier = 0.01

    def adjust_max(self, max_default):
        """Resolve the static ceiling: a declared ``"max"``, else the protocol ceiling.

        The advertised bound answers "what may be configured", so it is static and
        never below what the register can carry:

        1. A declared ``"max"`` — a real protocol or datasheet constraint, audited.
        2. The protocol ceiling — what the register can physically carry.

        Live limits — the BMS mirror, the inverter's rated output — are deliberately
        NOT in this chain. HA rejects ``number.set_value`` above the advertised max, so
        a moving or wrong-low limit turns into hard write failures and out-of-range
        states (#464, #467). They are advisory instead: see ``device_limit``.
        """
        if max_default is not None:
            self.max_value = max_default
            return

        derived = self.protocol_max
        self.max_value = derived
        _LOGGER.debug("max for %s resolved to protocol ceiling %s (no declared max)", self.registrars, derived)

        # A negative declared min marks a signed dispatch register (43128/43133/43134)
        # as writable below zero; the floor then resolves by the same rule as the
        # ceiling — what the register can physically carry — in the opposite direction.
        # (A definition declaring its "max" keeps its declared min untouched above.)
        if self.min_value is not None and self.min_value < 0:
            self.min_value = self.protocol_min

    def _inverter_rating_max(self) -> float | None:
        """The inverter's rated output in this entity's unit, or None if unusable."""
        rating = getattr(self.controller.inverter_config, "wattage_chosen", None)
        if not isinstance(rating, (int, float)) or isinstance(rating, bool) or rating <= 0:
            return None
        if self.unit_of_measurement == UnitOfPower.KILO_WATT:
            return rating / 1000
        return rating

    @property
    def protocol_raw_range(self) -> tuple[int, int]:
        """The raw (min, max) this register can carry, from its width."""
        data_type = self.data_type
        if data_type not in DATA_TYPE_RAW_RANGES:
            # Mirror what _convert_raw_value assumes when nothing is declared: a pair of
            # registers decodes as signed 32-bit, a lone one as unsigned 16-bit.
            data_type = DataType.S32.value if len(self.registrars) > 1 else DataType.U16.value
        return DATA_TYPE_RAW_RANGES[data_type]

    @property
    def protocol_max(self) -> float:
        """The largest value this register can physically hold, in its own unit."""
        # multiplier 0 is treated as 1 on the decode path; keep the two consistent.
        return self.protocol_raw_range[1] * (self.multiplier or 1)

    @property
    def protocol_min(self) -> float:
        """The smallest value this register can physically hold, in its own unit."""
        return self.protocol_raw_range[0] * (self.multiplier or 1)

    @property
    def battery_current_mirror_register(self) -> int | None:
        """The BMS mirror register advising this setpoint, or None if it isn't one."""
        for reg in self.registrars:
            mirror = BATTERY_CURRENT_MIRROR_REGISTERS.get(reg)
            if mirror is not None:
                return mirror
        return None

    @property
    def device_limit(self) -> float | None:
        """What the governing device reports it can do right now, or None.

        Advisory only: surfaced as an entity attribute and checked on write for a log
        warning, never advertised as the number's max. The BMS mirror derates with SOC
        through the day (#467) and on some firmware echoes the setpoint back (#464);
        the inverter rating can sit below a legitimate DC-side setpoint — all of which
        disqualify them as bounds on what may be *configured*. The device enforces its
        real limit itself at runtime.
        """
        mirror = self.battery_current_mirror_register
        if mirror is not None:
            return self._bms_reported_max(mirror)
        if self.max_source == MAX_SOURCE_INVERTER_RATING:
            return self._inverter_rating_max()
        return None

    @property
    def device_limit_source(self) -> str | None:
        """The authority ``device_limit`` comes from, or None if this entity has none."""
        if self.battery_current_mirror_register is not None:
            return "bms"
        if self.max_source == MAX_SOURCE_INVERTER_RATING:
            return MAX_SOURCE_INVERTER_RATING
        return None

    def _bms_reported_max(self, mirror_register: int) -> float | None:
        """The mirror's value in amps, or None while it is absent/zero/unreadable."""
        try:
            raw = cache_get(self.hass, self.controller, mirror_register)
        except Exception:  # no cache yet (tests, early setup) — no advisory limit
            return None
        if not isinstance(raw, (int, float)) or isinstance(raw, bool) or raw <= 0:
            return None
        return round(raw * BATTERY_CURRENT_MIRROR_MULTIPLIER, 1)

    def get_step(self, wanted_step):
        if wanted_step is not None:
            return wanted_step
        if self.unit_of_measurement == PERCENTAGE:
            return 1
        if self.unit_of_measurement == UnitOfPower.KILO_WATT:
            return 0.1
        if self.unit_of_measurement == UnitOfPower.WATT:
            return 1
        # Anything else has no sensible derived step; callers must cope with None.
        return None

    @property
    def entity_category(self) -> EntityCategory | None:
        """Diagnostic bucket for identity/version/clock-style registers.

        Deliberately conservative: only entities with no device_class (model,
        serial, firmware versions, clock parts, operating mode, internal bus
        data) are demoted. Real measurements (temperature, currents, voltages)
        keep their normal placement even when tagged an "Information" category.
        """
        if self.device_class is None and self.category in (Category.BASIC_INFORMATION, Category.DEVICE_INTERNAL_DATA):
            return EntityCategory.DIAGNOSTIC
        return None

    @property
    def get_raw_values(self):
        return [cache_get(self.hass, self.controller, reg) for reg in self.registrars]

    @property
    def get_value(self):
        return self._convert_raw_value(self.get_raw_values)

    def convert_value(self, value: list[int]):
        return self._convert_raw_value(value)

    def _convert_raw_value(self, values: list[int]):
        if not values or None in values:
            return None

        if len(self.registrars) >= 15:
            values = values
            n_value = extract_serial_number(values)
        elif len(self.registrars) > 1:
            # Default to signed 32-bit big-endian (historical behaviour — the many
            # 2-register power/current registers are genuinely signed). Registers
            # explicitly tagged U32 (e.g. lifetime energy totals) decode unsigned so
            # they never wrap negative; *_LE variants are low-word-first (the
            # string-inverter EPM block 36028-36057 is documented little-endian).
            if self.data_type == DataType.U32.value:
                combined_value = combine_u32(values)
            elif self.data_type == DataType.U32_LE.value:
                combined_value = combine_u32_le(values)
            elif self.data_type == DataType.S32_LE.value:
                combined_value = split_s32_le(values)
            else:
                combined_value = split_s32(values)

            if self.multiplier == 0 or self.multiplier == 1:
                n_value = round(combined_value)
            else:
                n_value = combined_value * self.multiplier
        else:
            # Treat it as a single register (U16/S16)
            raw = values[0]
            if getattr(self, "data_type", None) == DataType.S16.value and raw > 32767:
                raw -= 65536

            if self.multiplier == 0 or self.multiplier == 1:
                n_value = round(raw)
            else:
                n_value = raw * self.multiplier

        return n_value

    def get_info(self):
        """Return basic sensor information."""
        return {"name": self.name, "registrars": self.registrars}


def cluster_sensors_by_contiguous_registers(sensors: list[SolisBaseSensor]) -> list[list[SolisBaseSensor]]:
    """Partition sensors so each part covers a contiguous Modbus address range (no gaps between parts)."""
    active = [s for s in sensors if s.enabled]
    if not active:
        return []
    active.sort(key=lambda s: min(s.registrars))
    clusters: list[list[SolisBaseSensor]] = []
    current = [active[0]]
    cur_hi = max(active[0].registrars)
    for s in active[1:]:
        lo = min(s.registrars)
        hi = max(s.registrars)
        if lo <= cur_hi + 1:
            current.append(s)
            cur_hi = max(cur_hi, hi)
        else:
            clusters.append(current)
            current = [s]
            cur_hi = hi
    clusters.append(current)
    return clusters


class SolisSensorGroup:
    sensors: list[SolisBaseSensor]

    def __init__(self, hass, definition, controller, identification=None):
        self._sensors = list(
            map(
                lambda entity: SolisBaseSensor(
                    hass=hass,
                    name=entity.get("name", "reserve"),
                    controller=controller,
                    registrars=[int(r) for r in entity["register"]],
                    write_register=entity.get("write_register", None),
                    state_class=entity.get("state_class", None),
                    device_class=entity.get("device_class", None),
                    unit_of_measurement=entity.get("unit_of_measurement", None),
                    hidden=entity.get("hidden", False),
                    editable=entity.get("editable", False),
                    max_value=entity.get("max", None),
                    max_source=entity.get("max_source", None),
                    min_value=entity.get("min", 0),
                    step=entity.get("step", None),
                    identification=identification,
                    category=entity.get("category", None),
                    default=entity.get("default", 0),
                    multiplier=entity.get("multiplier", 1),
                    data_type=entity.get("data_type", None),
                    unique_id=unique_id_generator(controller, entity.get("unique", "reserve")),
                    poll_speed=definition.get("poll_speed", PollSpeed.NORMAL),
                ),
                definition.get("entities", []),
            )
        )
        self.poll_speed: PollSpeed = definition.get("poll_speed", PollSpeed.NORMAL if self.start_register < 40000 else PollSpeed.SLOW)

        _LOGGER.debug(
            f"Sensor group creation. start registrar = {self.start_register}, sensor count = {self.sensors_count}, registrar count = {self.registrar_count}"
        )
        self.validate_sequential_registrars()
        self.identification = identification

    @classmethod
    def from_sensors(
        cls,
        sensors: list[SolisBaseSensor],
        poll_speed: PollSpeed,
        identification=None,
    ) -> SolisSensorGroup:
        """Build a group from existing SolisBaseSensor instances (used after splitting a failed read block)."""
        inst = cls.__new__(cls)
        inst._sensors = list(sensors)
        inst.poll_speed = poll_speed
        inst.identification = identification
        inst.validate_sequential_registrars()
        return inst

    def validate_sequential_registrars(self):
        """Ensure all registrars increase sequentially without skipping numbers."""
        all_registrars = sorted(set(reg for sensor in self._sensors for reg in sensor.registrars))

        for i in range(len(all_registrars) - 1):
            if all_registrars[i + 1] != all_registrars[i] + 1:
                _LOGGER.error(f"🚨 Registrar sequence error! Found gap between {all_registrars[i]} and {all_registrars[i + 1]} in sensor group.")

    @property
    def sensors_count(self):
        return len(self._sensors)

    @property
    def sensors(self):
        return self._sensors

    @property
    def registrar_count(self):
        return sum(len(sensor.registrars) for sensor in self._sensors)

    @property
    def start_register(self):
        return min(reg for sensor in self._sensors for reg in sensor.registrars)
