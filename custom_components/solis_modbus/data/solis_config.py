from typing import List

from custom_components.solis_modbus.data.enums import InverterType, InverterFeature


class InverterOptions:
    def __init__(self, pv: bool = True, battery: bool = True, generator: bool = True, v2: bool = True):
        self.pv = pv
        self.battery = battery
        self.generator = generator
        self.v2 = v2


class InverterConfig:
    def __init__(self, model: str, wattage: List[int], phases: int, type: InverterType,
                 options: InverterOptions = InverterOptions(), connection="S2_WL_ST",
                 features=None):
        if features is None:
            features = []
        self.model = model
        self.wattage = wattage
        self.phases = phases
        self.type = type
        self.options = options
        self.connection = connection
        self.features: [InverterFeature] = features
        self.wattage_chosen = max(wattage)

        self.features.append(InverterFeature.BMS)

        if options.pv:
            self.features.append(InverterFeature.PV)
        if options.generator:
            self.features.append(InverterFeature.GENERATOR)
        if options.battery:
            self.features.append(InverterFeature.BATTERY)
        if options.v2:
            self.features.append(InverterFeature.V2)


SOLIS_INVERTERS = [
    InverterConfig(model="S6-EH1P", wattage=[3000, 3600, 5000, 6000, 8000], phases=1, type=InverterType.HYBRID,
                   features=[InverterFeature.SMART_PORT]),
    InverterConfig(model="S6-EH3P", wattage=[8000, 10000, 12000, 15000], phases=3, type=InverterType.HYBRID,
                   features=[InverterFeature.SMART_PORT]),
    InverterConfig(model="S6-EO1P", wattage=[4000, 5000], phases=1, type=InverterType.HYBRID,
                   features=[InverterFeature.SMART_PORT]),
    InverterConfig(model="S6-GR1P", wattage=[3000, 3600, 4000, 4600, 5000, 6000], phases=1, type=InverterType.GRID,
                   features=[InverterFeature.SMART_PORT]),
    InverterConfig(model="S5-EH1P", wattage=[4000, 5000], phases=1, type=InverterType.HYBRID,
                   features=[]),
    InverterConfig(model="S5-EO1P", wattage=[4000, 5000], phases=1, type=InverterType.HYBRID,
                   features=[]),
    InverterConfig(model="S5-GR1P", wattage=[7000, 10000, 10000], phases=1, type=InverterType.GRID,
                   features=[]),
    InverterConfig(model="S5-GR3P", wattage=[5000, 10000], phases=3, type=InverterType.GRID,
                   features=[]),
    InverterConfig(model="S5-GC", wattage=[25000, 30000, 33000, 36000, 40000, 50000], phases=3, type=InverterType.HYBRID,
                   features=[]),
    InverterConfig(model="RHI-*", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=3, type=InverterType.HYBRID,
                   features=[]),
    InverterConfig(model="RHI-1P", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=1, type=InverterType.HYBRID,
                   features=[]),
    InverterConfig(model="RHI-3P", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=3, type=InverterType.HYBRID,
                   features=[]),
    InverterConfig(model="RAI-*", wattage=[3000, 4000, 5000, 6000, 8000, 10000], phases=3, type=InverterType.ENERGY,
                   features=[]),
    InverterConfig(model="RAI-3K-48ES-5G", wattage=[3000], phases=1, type=InverterType.HYBRID,
                   features=[]),
    InverterConfig(model="WAVESHARE", wattage=[10000], phases=3, type=InverterType.HYBRID),
]

CONNECTION_METHOD = {
    "S2_WL_ST": "S2_WL_ST",
    "WAVESHARE": "WAVESHARE",
}
