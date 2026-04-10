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
    ):
        self.pv = pv
        self.battery = battery
        self.hv_battery = hv_battery
        self.generator = generator
        self.v2 = v2
        self.ac_coupling = ac_coupling


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
        self._rebuild_features()

    def _rebuild_features(self) -> None:
        opts = self.options
        feats = list(self._intrinsic_features)
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
        if self.type == InverterType.WAVESHARE or self.connection == "WAVESHARE":
            feats.append(InverterFeature.TCP)
        self.features: list[InverterFeature] = feats

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
        )


def inverter_options_from_config(config: dict, template: InverterConfig) -> InverterOptions:
    """Map Home Assistant config entry data/options keys to InverterOptions."""
    return InverterOptions(
        v2=config.get("has_v2", True),
        pv=config.get("has_pv", template.type in (InverterType.HYBRID, InverterType.GRID, InverterType.WAVESHARE)),
        ac_coupling=config.get("has_ac_coupling", False),
        generator=config.get("has_generator", True),
        battery=config.get("has_battery", True),
        hv_battery=config.get("has_hv_battery", False),
    )


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
        wattage=[8000, 10000, 12000, 15000, 29900, 30000, 40000, 49000, 50000, 60000],
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
    InverterConfig(model="RHI-*", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=3, type=InverterType.HYBRID, features=[]),
    InverterConfig(model="RHI-1P", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=1, type=InverterType.HYBRID, features=[]),
    InverterConfig(model="RHI-3P", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=3, type=InverterType.HYBRID, features=[]),
    InverterConfig(model="RAI-*", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=3, type=InverterType.ENERGY, features=[]),
    InverterConfig(model="RAI-3K-48ES-5G", wattage=[3000], phases=1, type=InverterType.HYBRID, features=[]),
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
