from __future__ import annotations

from custom_components.solis_modbus.data.enums import InverterFeature, InverterType


class InverterOptions:
    def __init__(
        self,
        pv: bool = True,
        battery: bool = True,
        hv_battery: bool = False,
        generator: bool = False,
        v2: bool = True,
        ac_coupling: bool = False,
        parallel: bool = False,
        dual_meter: bool = False,
        epm: bool = True,
        smart_port: bool = True,
        parallel_readings: bool = False,
        zonneplan_scaling: bool = True,
        mppt_count: int | None = None,
    ):
        self.pv = pv
        self.battery = battery
        self.hv_battery = hv_battery
        self.generator = generator
        self.v2 = v2
        self.ac_coupling = ac_coupling
        self.parallel = parallel
        self.dual_meter = dual_meter
        self.epm = epm
        # Only meaningful for models whose template lists SMART_PORT; lets users without
        # anything on the Smart Port stop polling its registers.
        self.smart_port = smart_port
        # Parallel-inverter readings without the parallel option (see CONF_PARALLEL_READINGS).
        self.parallel_readings = parallel_readings
        # Only meaningful for models whose template lists ZONNEPLAN (see CONF_ZONNEPLAN_SCALING).
        self.zonneplan_scaling = zonneplan_scaling
        # MPPTs wired on this unit (see CONF_MPPT_COUNT); None keeps the model's default.
        self.mppt_count = mppt_count


# Every model reads MPPT 1-4 from its classic DC voltage/current registers (3021-3028
# on string inverters, 33049-33056 on hybrids). Entries set up before the MPPT count
# existed have no count stored and keep exactly these four.
LEGACY_MPPT_COUNT = 4
# The multi-MPPT block (3500/3530 in the protocol) defines MPPT 1-15.
MAX_MPPT_COUNT = 15
# PV string currents the protocol lists (3301-3320, wire 3300-3319).
MAX_STRING_COUNT = 20


class InverterConfig:
    def __init__(
        self,
        model: str,
        wattage: list[int],
        phases: int,
        type: InverterType,
        options: InverterOptions | None = None,
        connection="S2_WL_ST",
        features=None,
        max_mppts: int = LEGACY_MPPT_COUNT,
        default_mppts: int | None = None,
        strings_per_mppt: int = 0,
    ):
        if features is None:
            features = []
        if options is None:
            options = InverterOptions()
        self._intrinsic_features: list[InverterFeature] = list(features)
        self.model = model
        self.wattage = wattage
        self.phases = phases
        self.type = type
        self.options = options
        self.connection = connection
        self.wattage_chosen = max(wattage)
        # Most MPPTs this model can report; more than 4 needs the multi-MPPT registers.
        self.max_mppts = max_mppts
        # Count used when the entry stores none and detection found nothing.
        self.default_mppts = default_mppts if default_mppts is not None else min(max_mppts, LEGACY_MPPT_COUNT)
        # PV strings per MPPT on models that report per-string currents (0 = none).
        self.strings_per_mppt = strings_per_mppt
        self._rebuild_features()

    def _rebuild_features(self) -> None:
        opts = self.options
        feats = list(self._intrinsic_features)
        if not opts.smart_port:
            feats = [f for f in feats if f != InverterFeature.SMART_PORT]
        if not opts.zonneplan_scaling:
            feats = [f for f in feats if f != InverterFeature.ZONNEPLAN]
        feats.append(InverterFeature.BMS)
        if opts.pv:
            feats.append(InverterFeature.PV)
        if opts.generator:
            feats.append(InverterFeature.GENERATOR)
        if opts.battery:
            feats.append(InverterFeature.BATTERY)
        if opts.hv_battery:
            feats.append(InverterFeature.HV_BATTERY)
        if opts.v2:
            feats.append(InverterFeature.V2)
        if opts.ac_coupling:
            feats.append(InverterFeature.AC_COUPLING)
        if opts.parallel:
            feats.append(InverterFeature.PARALLEL)
        if opts.parallel_readings:
            feats.append(InverterFeature.PARALLEL_READINGS)
        if opts.dual_meter:
            feats.append(InverterFeature.DUAL_METER)
        if opts.epm:
            feats.append(InverterFeature.EPM)
        if self.type == InverterType.WAVESHARE or self.connection == "WAVESHARE":
            feats.append(InverterFeature.TCP)
        self.features: list[InverterFeature] = feats

    @property
    def mppt_count(self) -> int:
        """MPPTs to create entities for: the user's or detected count, else the model default, within 1..max_mppts."""
        count = self.options.mppt_count if self.options.mppt_count is not None else self.default_mppts
        return max(1, min(int(count), self.max_mppts))

    @property
    def string_count(self) -> int:
        """PV string currents to create entities for (0 on models without per-string readings)."""
        return min(self.mppt_count * self.strings_per_mppt, MAX_STRING_COUNT)

    @property
    def probe_register(self) -> int:
        """An input register every inverter of this type answers, for checking a unit responds."""
        return 3041 if self.type in [InverterType.GRID, InverterType.STRING] else 35000

    @property
    def identity_register(self) -> int:
        """The model-number input register, which never reads 0 on a real inverter."""
        return 2999 if self.type in [InverterType.GRID, InverterType.STRING] else 33000

    def clone_with_options(self, options: InverterOptions, connection: str) -> InverterConfig:
        """Copy this model definition with user-chosen options (does not mutate SOLIS_INVERTERS templates)."""
        return InverterConfig(
            model=self.model,
            wattage=self.wattage,
            phases=self.phases,
            type=self.type,
            options=options,
            connection=connection,
            features=list(self._intrinsic_features),
            max_mppts=self.max_mppts,
            default_mppts=self.default_mppts,
            strings_per_mppt=self.strings_per_mppt,
        )


def inverter_options_from_config(config: dict, template: InverterConfig) -> InverterOptions:
    """Map Home Assistant config entry data/options keys to InverterOptions."""
    return InverterOptions(
        v2=config.get("has_v2", True),
        pv=config.get("has_pv", template.type in (InverterType.HYBRID, InverterType.GRID, InverterType.WAVESHARE)),
        ac_coupling=config.get("has_ac_coupling", False),
        parallel=config.get("has_parallel", False),
        generator=config.get("has_generator", True),
        battery=config.get("has_battery", True),
        hv_battery=config.get("has_hv_battery", False),
        dual_meter=config.get("has_dual_meter", False),
        epm=config.get("has_epm", True),
        smart_port=config.get("has_smart_port", True),
        parallel_readings=config.get("parallel_readings", False),
        zonneplan_scaling=config.get("zonneplan_scaling", True),
        mppt_count=config.get("mppt_count"),
    )


# DC input type (wire 3003) holds the number of PV inputs minus one; the string
# combination register (wire 3286) says how many string currents share one MPPT
# voltage: 0 = two, 3 = three. Field-verified on a Solis-100K-5G: 19 and 0, 10 MPPTs.
STRINGS_PER_MPPT_BY_COMBINATION = {0: 2, 3: 3}


def mppt_count_from_registers(dc_input_type: int, combination: int, template: InverterConfig) -> int | None:
    """MPPT count read from the inverter, or None when the registers don't fit this model.

    The string combination has to match the model's strings per MPPT, since the
    string current entities are laid out from that.
    """
    if STRINGS_PER_MPPT_BY_COMBINATION.get(combination) != template.strings_per_mppt or template.strings_per_mppt == 0:
        return None
    inputs = dc_input_type + 1
    if inputs % template.strings_per_mppt:
        return None
    count = inputs // template.strings_per_mppt
    return count if 1 <= count <= template.max_mppts else None


# Firmware (registers 33001/33002) from which an S6-EH3P10K-H-ZP sends the standard
# battery energy values (#563). Every unit known to send them 10x/100x too high is on
# DSP 2 / HMI 2 (#191 and three units on #563); one on DSP 0x15 / HMI 0x22 sends the
# standard values. Firmware in between is unconfirmed and keeps the scaling.
ZONNEPLAN_FIXED_DSP_VERSION = 0x15
ZONNEPLAN_FIXED_HMI_VERSION = 0x22


def zonneplan_scaling_for_firmware(dsp_version: int, hmi_version: int) -> bool:
    """Whether a ZP unit on this firmware (registers 33001/33002) needs the Zonneplan scaling."""
    return not (dsp_version >= ZONNEPLAN_FIXED_DSP_VERSION and hmi_version >= ZONNEPLAN_FIXED_HMI_VERSION)


# TODO: Need to find a naming convention, and a better way to handle sub models to more finely control the power
SOLIS_INVERTERS = [
    InverterConfig(
        model="S6-EH1P",
        wattage=[3000, 3600, 5000, 6000, 8000],
        phases=1,
        type=InverterType.HYBRID,
        features=[InverterFeature.SMART_PORT],
    ),
    InverterConfig(
        model="S6-EH2P",
        wattage=[9600, 11400, 12000, 14000, 16000],
        phases=3,
        type=InverterType.HYBRID,
        features=[InverterFeature.SMART_PORT],
    ),
    InverterConfig(
        model="S6-EH3P",
        wattage=[8000, 10000, 12000, 15000, 20000, 29900, 30000, 40000, 49000, 50000, 60000],
        phases=3,
        type=InverterType.HYBRID,
        features=[InverterFeature.SMART_PORT],
    ),
    InverterConfig(model="S6-EO1P", wattage=[4000, 5000], phases=1, type=InverterType.HYBRID, features=[InverterFeature.SMART_PORT]),
    InverterConfig(
        model="S6-GR1P",
        wattage=[3000, 3600, 4000, 4600, 5000, 6000],
        phases=1,
        type=InverterType.GRID,
        features=[InverterFeature.SMART_PORT],
    ),
    InverterConfig(model="S6-EA1P", wattage=[3600, 4500, 5000, 6000], phases=1, type=InverterType.ENERGY, features=[InverterFeature.SMART_PORT]),
    InverterConfig(
        model="S6-EH3P10K-H-ZP",
        wattage=[10000],
        phases=3,
        type=InverterType.HYBRID,
        features=[InverterFeature.SMART_PORT, InverterFeature.TCP, InverterFeature.ZONNEPLAN],
    ),
    InverterConfig(model="S5-EH1P", wattage=[4000, 5000], phases=1, type=InverterType.HYBRID, features=[]),
    InverterConfig(model="S5-EO1P", wattage=[4000, 5000], phases=1, type=InverterType.HYBRID, features=[]),
    InverterConfig(model="S5-GR1P", wattage=[7000, 10000, 10000], phases=1, type=InverterType.GRID, features=[]),
    InverterConfig(model="S5-GR3P", wattage=[5000, 10000], phases=3, type=InverterType.GRID, features=[]),
    InverterConfig(
        model="S5-GC",
        wattage=[25000, 30000, 33000, 36000, 40000, 50000, 60000],
        phases=3,
        type=InverterType.GRID,
        features=[],
    ),
    InverterConfig(
        # Solis-(80-110)K-5G and -5G-PRO: 2 strings per MPPT, but the MPPT count varies
        # (datasheets: 80K-5G 9, 100K-5G 10, 80K-5G-PRO 6, 100/110K-5G-PRO 8). Setup
        # reads it from the inverter; 10 is the field-verified Solis-100K-5G.
        model="3P(80-110)K-5G",
        wattage=[80000, 90000, 100000, 110000],
        phases=3,
        type=InverterType.GRID,
        features=[InverterFeature.MULTI_MPPT],
        max_mppts=MAX_MPPT_COUNT,
        default_mppts=10,
        strings_per_mppt=2,
    ),
    InverterConfig(model="RHI-*", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=3, type=InverterType.HYBRID, features=[]),
    InverterConfig(model="RHI-1P", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=1, type=InverterType.HYBRID, features=[]),
    InverterConfig(model="RHI-3P", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=3, type=InverterType.HYBRID, features=[]),
    InverterConfig(model="RAI-*", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=3, type=InverterType.ENERGY, features=[]),
    InverterConfig(model="RAI-3K-48ES-5G", wattage=[3000], phases=1, type=InverterType.ENERGY, features=[]),
    InverterConfig(
        model="3P(3-20)K-4G",
        wattage=[3000, 4000, 5000, 6000, 8000, 9000, 10000, 12000, 15000, 17000, 20000],
        phases=3,
        type=InverterType.GRID,
        features=[InverterFeature.PV],
    ),
    InverterConfig(model="1P(2.5-6)K-4G", wattage=[2500, 3000, 4000, 5000, 6000], phases=1, type=InverterType.GRID, features=[]),
    InverterConfig(model="WAVESHARE", wattage=[10000], phases=3, type=InverterType.HYBRID),
]

CONNECTION_METHOD = {
    "S2_WL_ST": "S2_WL_ST",
    "WAVESHARE": "WAVESHARE",
}
