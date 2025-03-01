from typing import List
from custom_components.solis_modbus.data.enums import InverterType, InverterFeature


class InverterOptions:
    def __init__(self, pv: bool = True, battery: bool = True, generator: bool = True, v2: bool = True):
        self.pv = pv
        self.battery = battery
        self.generator = generator
        self.v2 = v2

class InverterConfig:
    def __init__(self, model: str, wattage: List[int], phases: int, type: InverterType, options: InverterOptions = InverterOptions(), connection = "S2_WL_ST"):
        self.model = model
        self.wattage = wattage
        self.phases = phases
        self.type = type
        self.options = options
        self.connection = connection
        self.features: [InverterFeature] = []

        if options.pv:
            self.features.append(InverterFeature.PV)
        if options.generator:
            self.features.append(InverterFeature.GENERATOR)
        if options.battery:
            self.features.append(InverterFeature.BATTERY)
        if options.v2:
            self.features.append(InverterFeature.V2)


SOLIS_INVERTERS = [
    InverterConfig(model="S6-EH1P", wattage=[3000, 3600, 5000, 6000, 8000], phases=1, type=InverterType.HYBRID),
    InverterConfig(model="S6-EH3P", wattage=[8000, 10000, 12000, 15000], phases=3, type=InverterType.HYBRID),
    InverterConfig(model="S6-EO1P", wattage=[4000, 5000], phases=1, type=InverterType.HYBRID),
    InverterConfig(model="S6-GR1P", wattage=[2500,3000,3600,4000,4600,5000,6000], phases=1, type=InverterType.GRID),
    InverterConfig(model="S5-EH1P", wattage=[4000, 5000], phases=1, type=InverterType.HYBRID),
    InverterConfig(model="S5-EO1P", wattage=[4000, 5000], phases=1, type=InverterType.HYBRID),
    InverterConfig(model="S5-GR1P", wattage=[7000, 10000, 10000], phases=1, type=InverterType.GRID),
    InverterConfig(model="S5-GR3P", wattage=[5000, 10000], phases=3, type=InverterType.GRID),
    InverterConfig(model="RHI-*", wattage=[3000,4000,5000,6000,8000,10000], phases=3, type=InverterType.HYBRID),
    InverterConfig(model="RAI-*", wattage=[3000,4000,5000,6000,8000,10000], phases=3, type=InverterType.ENERGY),
    InverterConfig(model="WAVESHARE", wattage=[10000], phases=3, type=InverterType.HYBRID),
]

CONNECTION_METHOD = {
    "S2_WL_ST": "S2_WL_ST",
    "WAVESHARE": "WAVESHARE",
}