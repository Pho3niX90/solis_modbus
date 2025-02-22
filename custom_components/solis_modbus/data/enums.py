from enum import Enum


class PollSpeed(Enum):
    ONCE = "once"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"

class InverterType(Enum):
    HYBRID = "hybrid"
    STRING = "string"
    GRID = "grid"
    ENERGY = "energy"
    WAVESHARE = "waveshare"

class InverterFeature(Enum):
    PV = "pv",
    BATTERY = "battery",
    GRID = "grid",
    GENERATOR = "generator",
    V2 = "v2"