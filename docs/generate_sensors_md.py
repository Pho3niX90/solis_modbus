"""Regenerate docs/source/sensors.md entity tables from definition files.

Preserves the Waveshare and Solar Inverter Modes sections from the existing file.
Run from repo root: uv run python docs/generate_sensors_md.py
"""

from __future__ import annotations

import re
import sys
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.solis_modbus.data.enums import InverterFeature, InverterType  # noqa: E402
from custom_components.solis_modbus.data.solis_config import InverterConfig, InverterOptions  # noqa: E402
from custom_components.solis_modbus.sensor_data.hybrid_sensors import (  # noqa: E402
    hybrid_sensors,
    hybrid_sensors_derived,
)
from custom_components.solis_modbus.sensor_data.select_sensors import get_select_sensors  # noqa: E402
from custom_components.solis_modbus.sensor_data.string_sensors import (  # noqa: E402
    string_sensors,
    string_sensors_derived,
)
from custom_components.solis_modbus.sensor_data.switch_sensors import get_switch_sensors  # noqa: E402
from custom_components.solis_modbus.sensor_data.time_sensors import get_time_sensors  # noqa: E402

OUT = ROOT / "docs" / "source" / "sensors.md"


def enum_name(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return value.name
    return str(value)


def format_registers(registers) -> str:
    if not registers:
        return ""
    regs = [str(r) for r in registers]
    # Collapse long consecutive serial-number style ranges
    try:
        nums = [int(r) for r in regs]
    except ValueError:
        return ", ".join(regs)
    if len(nums) >= 4 and nums == list(range(nums[0], nums[0] + len(nums))):
        return f"{nums[0]} - {nums[-1]}"
    return ", ".join(regs)


def pad_row(cells: list[str], widths: list[int]) -> str:
    return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"


def pad_sep(widths: list[int]) -> str:
    return "|" + "|".join("-" * (w + 2) for w in widths) + "|"


def table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = [pad_row(headers, widths), pad_sep(widths)]
    lines.extend(pad_row(row, widths) for row in rows)
    return "\n".join(lines)


def iter_sensor_entities(groups):
    for group in groups:
        for entity in group.get("entities", []):
            if entity.get("type") == "reserve" or entity.get("name") == "reserve":
                continue
            yield entity


def sensor_row(entity: dict, *, prefix: str = "") -> list[str]:
    name = entity.get("name", "")
    if prefix and not name.startswith(prefix):
        name = f"{prefix}{name}"
    regs = entity.get("register", [])
    if isinstance(regs, (str, int)):
        regs = [regs]
    return [
        name,
        enum_name(entity.get("device_class")),
        enum_name(entity.get("unit_of_measurement")),
        enum_name(entity.get("state_class")),
        format_registers(regs),
    ]


def hybrid_config_all_features(*, hv_battery: bool = True) -> InverterConfig:
    """Config that enables every optional hybrid feature for full docs coverage."""
    return InverterConfig(
        model="S6-EH3P",
        wattage=[10000],
        phases=3,
        type=InverterType.HYBRID,
        options=InverterOptions(
            pv=True,
            battery=True,
            hv_battery=hv_battery,
            generator=True,
            v2=True,
            ac_coupling=True,
            parallel=True,
            dual_meter=True,
            epm=True,
        ),
        features=[InverterFeature.SMART_PORT],
    )


def string_config() -> InverterConfig:
    return InverterConfig(
        model="S5-GR3P",
        wattage=[10000],
        phases=3,
        type=InverterType.GRID,
        options=InverterOptions(epm=True),
        features=[],
    )


def build_input_rows(entities) -> list[list[str]]:
    rows = []
    for entity in entities:
        if not entity.get("editable"):
            continue
        rows.append(sensor_row(entity, prefix="Solis "))
    rows.sort(key=lambda r: (r[4], r[0]))
    return rows


def build_switch_rows(config) -> list[list[str]]:
    rows = []
    for group in get_switch_sensors(config):
        register = group.get("register", group.get("read_register"))
        for entity in group.get("entities", []):
            name = entity["name"]
            if not name.startswith("Solis "):
                name = f"Solis {name}"
            bit = entity.get("bit_position")
            bit_s = "" if bit is None else str(bit)
            note = ""
            if entity.get("inverted"):
                note = "Inverted"
            if entity.get("keep_alive"):
                note = (note + "; " if note else "") + "Keep-alive while ON"
            if group.get("write_register") and group.get("write_register") != register:
                note = (note + "; " if note else "") + f"write {group['write_register']}"
            rows.append([name, str(register), bit_s, note])
    rows.sort(key=lambda r: (int(r[1]), r[2] or "99", r[0]))
    return rows


def build_time_rows(config) -> list[list[str]]:
    rows = []
    for entity in get_time_sensors(config):
        name = entity["name"]
        if not name.startswith("Solis "):
            name = f"Solis {name}"
        rows.append([name, str(entity["register"])])
    return rows


def build_hybrid_select_rows() -> list[list[str]]:
    """Include both HV and LV Battery Model option sets."""
    rows = []
    for group in get_select_sensors(hybrid_config_all_features(hv_battery=True)):
        options = ", ".join(e["name"] for e in group.get("entities", []))
        name = f"Solis {group['name']}"
        if group["name"] == "Battery Model":
            name = f"{name} (HV)"
        rows.append([name, str(group["register"]), options])
    for group in get_select_sensors(hybrid_config_all_features(hv_battery=False)):
        if group["name"] != "Battery Model":
            continue
        options = ", ".join(e["name"] for e in group.get("entities", []))
        rows.append(["Solis Battery Model (LV)", str(group["register"]), options])
    return rows


def build_sensor_rows(groups, derived, *, prefix: str = "") -> list[list[str]]:
    rows = [sensor_row(e, prefix=prefix) for e in iter_sensor_entities(groups)]
    rows.extend(sensor_row(e, prefix=prefix) for e in derived)

    # Sort by first register then name
    def sort_key(row):
        regs = row[4]
        first = regs.split(",")[0].split("-")[0].strip()
        try:
            return (int(first), row[0])
        except ValueError:
            return (10**9, row[0])

    rows.sort(key=sort_key)
    return rows


def extract_preserved_sections(existing: str) -> tuple[str, str]:
    waveshare = ""
    modes = ""
    m = re.search(r"(# Waveshare\n.*?)(?=\n# String Inverter Sensors\n)", existing, re.S)
    if m:
        waveshare = m.group(1).rstrip() + "\n"
    m = re.search(r"(# Solar Inverter Modes in Solis Inverters\n.*)\Z", existing, re.S)
    if m:
        modes = m.group(1).rstrip() + "\n"
    return waveshare, modes


def main() -> None:
    existing = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    waveshare, modes = extract_preserved_sections(existing)
    if not waveshare:
        waveshare = "# Waveshare\nThis is only required if your values are higher than expected, if you aren't experiencing this, this should be disabled.\n"
    if not modes:
        modes = "# Solar Inverter Modes in Solis Inverters\n"

    hybrid_cfg = hybrid_config_all_features()
    string_cfg = string_config()

    hybrid_entities = list(iter_sensor_entities(hybrid_sensors))
    string_entities = list(iter_sensor_entities(string_sensors))

    sensor_headers = ["Name", "Device Class", "Unit Of Measurement", "State Class", "Registers"]

    hybrid_switch_rows = build_switch_rows(hybrid_cfg)
    string_switch_rows = [r for r in build_switch_rows(string_cfg) if r[1] not in {row[1] for row in hybrid_switch_rows} or "power limit" in r[0].lower()]
    # Avoid duplicating 90005 if present on both
    hybrid_names = {r[0] for r in hybrid_switch_rows}
    string_switch_rows = [r for r in string_switch_rows if r[0] not in hybrid_names]

    parts = [
        "---",
        "myst:",
        '  enable_extensions: [ "colon_fence" ]',
        "---",
        "",
        "The following sensors are provided in the integration.",
        "",
        "Tables below are generated from the integration definition files "
        "(`hybrid_sensors.py`, `string_sensors.py`, switches/selects/times). "
        "Hybrid and string are separate hardware profiles — only one applies per install. "
        "Optional feature entities (Meter 2, dispatch, V2 Grid TOU, Smart Port, etc.) "
        "are listed even if disabled in your options.",
        "",
        "# String Inverter Registers",
        "The string inverter uses the following register ranges:",
        "- 2xxx: Basic information and measurements",
        "- 3xxx: AC and DC measurements, status information",
        "- 36xxx: Additional measurements and energy data",
        "",
        "# Hybrid Inverter Registers",
        "The hybrid inverter uses the following register ranges:",
        "- 33xxx: Basic information and measurements",
        "- 34xxx: Additional measurements",
        "- 35xxx: Inverter type definition",
        "- 43xxx / 44xxx: Control settings and parameters",
        "- 90xxx: Derived values",
        "",
        "# Input Control Sensors",
        "Editable number entities (hybrid).",
        "",
        table(sensor_headers, build_input_rows(hybrid_entities)),
        "",
        "# Switch Control Sensors",
        "",
        table(
            ["Name", "Register", "Bit Position", "Note"],
            hybrid_switch_rows + string_switch_rows,
        ),
        "",
        "# Select Control Sensors",
        "",
        table(
            ["Name", "Register", "Options"],
            build_hybrid_select_rows(),
        ),
        "",
        "# Time Control Sensors",
        "",
        table(["Name", "Register"], build_time_rows(hybrid_cfg)),
        "",
        "# Hybrid Inverter Sensors",
        "",
        table(
            sensor_headers,
            build_sensor_rows(hybrid_sensors, hybrid_sensors_derived, prefix="Solis "),
        ),
        "",
        waveshare.rstrip(),
        "",
        "# String Inverter Sensors",
        "",
        table(
            sensor_headers,
            build_sensor_rows(string_sensors, string_sensors_derived, prefix=""),
        ),
        "",
        modes.rstrip(),
        "",
    ]

    text = "\n".join(parts)
    text = text.replace("| Solis Solis Modbus Enabled ", "| Solis Modbus Enabled ")
    OUT.write_text(text, encoding="utf-8")

    # Coverage report
    hybrid_count = len(hybrid_entities) + len(hybrid_sensors_derived)
    string_count = len(string_entities) + len(string_sensors_derived)
    select_rows = build_hybrid_select_rows()
    print(f"Wrote {OUT}")
    print(f"Hybrid sensors+derived: {hybrid_count}")
    print(f"String sensors+derived: {string_count}")
    print(f"Input (editable): {len(build_input_rows(hybrid_entities))}")
    print(f"Switches: {len(hybrid_switch_rows) + len(string_switch_rows)}")
    print(f"Selects: {len(select_rows)}")
    print(f"Times: {len(build_time_rows(hybrid_cfg))}")


if __name__ == "__main__":
    main()
