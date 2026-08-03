---
myst:
  enable_extensions: [ "colon_fence" ]
---

The following sensors are provided in the integration.

Tables below are generated from the integration definition files (`hybrid_sensors.py`, `string_sensors.py`, switches/selects/times). Hybrid and string are separate hardware profiles — only one applies per install. Optional feature entities (Meter 2, dispatch, V2 Grid TOU, Smart Port, etc.) are listed even if disabled in your options.

# String Inverter Registers
The string inverter uses the following register ranges:
- 2xxx: Basic information and measurements
- 3xxx: AC and DC measurements, status information
- 36xxx: Additional measurements and energy data

# Hybrid Inverter Registers
The hybrid inverter uses the following register ranges:
- 33xxx: Basic information and measurements
- 34xxx: Additional measurements
- 35xxx: Inverter type definition
- 43xxx / 44xxx: Control settings and parameters
- 90xxx: Derived values

# Input Control Sensors
Editable number entities (hybrid).

| Name                                                      | Device Class   | Unit Of Measurement  | State Class | Registers |
|-----------------------------------------------------------|----------------|----------------------|-------------|-----------|
| Solis Max Charge SOC                                      |                | %                    | MEASUREMENT | 43010     |
| Solis Overdischarge SOC                                   | BATTERY        | %                    | MEASUREMENT | 43011     |
| Solis Max Charge Current                                  | CURRENT        | AMPERE               |             | 43012     |
| Solis Max Discharge Current                               | CURRENT        | AMPERE               |             | 43013     |
| Solis Floating Charge Voltage                             | VOLTAGE        | VOLT                 | MEASUREMENT | 43016     |
| Solis Equalizing Charge Voltage                           | VOLTAGE        | VOLT                 | MEASUREMENT | 43017     |
| Solis Force Charge SOC                                    |                | %                    | MEASUREMENT | 43018     |
| Solis Battery Rated Capacity                              |                | Ah                   |             | 43019     |
| Solis Overdischarge Voltage                               | VOLTAGE        | VOLT                 | MEASUREMENT | 43020     |
| Solis Forcecharge Voltage                                 | VOLTAGE        | VOLT                 | MEASUREMENT | 43021     |
| Solis Backup SOC                                          |                | %                    | MEASUREMENT | 43024     |
| Solis Force-charge Power Limitation                       | POWER          | WATT                 | MEASUREMENT | 43027     |
| Solis Backflow Power                                      | POWER          | WATT                 |             | 43074     |
| Solis Output Power Clamp                                  | POWER          | WATT                 | MEASUREMENT | 43081     |
| Solis Battery Max Charge Current                          | CURRENT        | AMPERE               |             | 43117     |
| Solis Battery Max Discharge Current                       | CURRENT        | AMPERE               |             | 43118     |
| Solis RC Inverter AC Grid Active Power                    | POWER          | WATT                 | MEASUREMENT | 43128     |
| Solis RC Force Battery Discharge Power                    | POWER          | WATT                 | MEASUREMENT | 43129     |
| Solis Battery Charge Limit Power                          | POWER          | WATT                 | MEASUREMENT | 43130     |
| Solis Battery Discharge Limit Power                       | POWER          | WATT                 | MEASUREMENT | 43131     |
| Solis RC Grid Active Power                                | POWER          | WATT                 | MEASUREMENT | 43133     |
| Solis RC Grid Reactive Power                              | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT | 43134     |
| Solis RC Force Battery Charge Power                       | POWER          | WATT                 | MEASUREMENT | 43136     |
| Solis Off-Grid Overdischarge SOC                          | BATTERY        | %                    | MEASUREMENT | 43137     |
| Solis Time-Charging Charge Current                        | CURRENT        | AMPERE               | MEASUREMENT | 43141     |
| Solis Time-Charging Discharge Current                     | CURRENT        | AMPERE               | MEASUREMENT | 43142     |
| Solis Export Calibration                                  | POWER          | WATT                 |             | 43195     |
| Solis RC Timeout                                          |                | MINUTES              |             | 43282     |
| Solis Flexible Export Backflow Power                      | POWER          | WATT                 | MEASUREMENT | 43291     |
| Solis MPPT Scanning Interval                              |                | SECONDS              | MEASUREMENT | 43361     |
| Solis Rated Input Power of Generator                      | POWER          | KILO_WATT            | MEASUREMENT | 43364     |
| Solis Maximum Allowable Percentage of Generator           |                | %                    | MEASUREMENT | 43367     |
| Solis Generator Target Power                              | POWER          | KILO_WATT            | MEASUREMENT | 43368     |
| Solis Generator Charging Power                            | POWER          | KILO_WATT            | MEASUREMENT | 43369     |
| Solis Peak Baseline SOC                                   |                | %                    | MEASUREMENT | 43487     |
| Solis Peak Max Usable Grid Power                          | POWER          | WATT                 | MEASUREMENT | 43488     |
| Solis Grid Time of Use Charge cut off SOC (Slot 1)        |                | %                    | MEASUREMENT | 43708     |
| Solis Grid Time of Use Charge battery current (Slot 1)    | CURRENT        | AMPERE               | MEASUREMENT | 43709     |
| Solis Grid Time of Use Charge cut off voltage (Slot 1)    | VOLTAGE        | VOLT                 | MEASUREMENT | 43710     |
| Solis Grid Time of Use Charge cut off SOC (Slot 2)        |                | %                    | MEASUREMENT | 43715     |
| Solis Grid Time of Use Charge battery current (Slot 2)    | CURRENT        | AMPERE               | MEASUREMENT | 43716     |
| Solis Grid Time of Use Charge cut off voltage (Slot 2)    | VOLTAGE        | VOLT                 | MEASUREMENT | 43717     |
| Solis Grid Time of Use Charge cut off SOC (Slot 3)        |                | %                    | MEASUREMENT | 43722     |
| Solis Grid Time of Use Charge battery current (Slot 3)    | CURRENT        | AMPERE               | MEASUREMENT | 43723     |
| Solis Grid Time of Use Charge cut off voltage (Slot 3)    | VOLTAGE        | VOLT                 | MEASUREMENT | 43724     |
| Solis Grid Time of Use Charge cut off SOC (Slot 4)        |                | %                    | MEASUREMENT | 43729     |
| Solis Grid Time of Use Charge battery current (Slot 4)    | CURRENT        | AMPERE               | MEASUREMENT | 43730     |
| Solis Grid Time of Use Charge cut off voltage (Slot 4)    | VOLTAGE        | VOLT                 | MEASUREMENT | 43731     |
| Solis Grid Time of Use Charge cut off SOC (Slot 5)        |                | %                    | MEASUREMENT | 43736     |
| Solis Grid Time of Use Charge battery current (Slot 5)    | CURRENT        | AMPERE               | MEASUREMENT | 43737     |
| Solis Grid Time of Use Charge cut off voltage (Slot 5)    | VOLTAGE        | VOLT                 | MEASUREMENT | 43738     |
| Solis Grid Time of Use Charge cut off SOC (Slot 6)        |                | %                    | MEASUREMENT | 43743     |
| Solis Grid Time of Use Charge battery current (Slot 6)    | CURRENT        | AMPERE               | MEASUREMENT | 43744     |
| Solis Grid Time of Use Charge cut off voltage (Slot 6)    | VOLTAGE        | VOLT                 | MEASUREMENT | 43745     |
| Solis Grid Time of Use Discharge cut off SOC (Slot 1)     |                | %                    | MEASUREMENT | 43750     |
| Solis Grid Time of Use Discharge battery current (Slot 1) | CURRENT        | AMPERE               | MEASUREMENT | 43751     |
| Solis Grid Time of Use Discharge cut off voltage (Slot 1) | VOLTAGE        | VOLT                 | MEASUREMENT | 43752     |
| Solis Grid Time of Use Discharge cut off SOC (Slot 2)     |                | %                    | MEASUREMENT | 43757     |
| Solis Grid Time of Use Discharge battery current (Slot 2) | CURRENT        | AMPERE               | MEASUREMENT | 43758     |
| Solis Grid Time of Use Discharge cut off voltage (Slot 2) | VOLTAGE        | VOLT                 | MEASUREMENT | 43759     |
| Solis Grid Time of Use Discharge cut off SOC (Slot 3)     |                | %                    | MEASUREMENT | 43764     |
| Solis Grid Time of Use Discharge battery current (Slot 3) | CURRENT        | AMPERE               | MEASUREMENT | 43765     |
| Solis Grid Time of Use Discharge cut off voltage (Slot 3) | VOLTAGE        | VOLT                 | MEASUREMENT | 43766     |
| Solis Grid Time of Use Discharge cut off SOC (Slot 4)     |                | %                    | MEASUREMENT | 43771     |
| Solis Grid Time of Use Discharge battery current (Slot 4) | CURRENT        | AMPERE               | MEASUREMENT | 43772     |
| Solis Grid Time of Use Discharge cut off voltage (Slot 4) | VOLTAGE        | VOLT                 | MEASUREMENT | 43773     |
| Solis Grid Time of Use Discharge cut off SOC (Slot 5)     |                | %                    | MEASUREMENT | 43778     |
| Solis Grid Time of Use Discharge battery current (Slot 5) | CURRENT        | AMPERE               | MEASUREMENT | 43779     |
| Solis Grid Time of Use Discharge cut off voltage (Slot 5) | VOLTAGE        | VOLT                 | MEASUREMENT | 43780     |
| Solis Grid Time of Use Discharge cut off SOC (Slot 6)     |                | %                    | MEASUREMENT | 43785     |
| Solis Grid Time of Use Discharge battery current (Slot 6) | CURRENT        | AMPERE               | MEASUREMENT | 43786     |
| Solis Grid Time of Use Discharge cut off voltage (Slot 6) | VOLTAGE        | VOLT                 | MEASUREMENT | 43787     |

# Switch Control Sensors

| Name                                                                     | Register | Bit Position | Note                |
|--------------------------------------------------------------------------|----------|--------------|---------------------|
| Solis Power State                                                        | 43007    |              |                     |
| Solis Output Limit Gate                                                  | 43070    |              |                     |
| Solis Grid feed in power limit switch                                    | 43073    | 4            |                     |
| Solis Self-Use Mode                                                      | 43110    | 0            |                     |
| Solis Time of Use                                                        | 43110    | 1            |                     |
| Solis Battery Healing Mode                                               | 43110    | 10           |                     |
| Solis Peak Shaving Mode                                                  | 43110    | 11           |                     |
| Solis Off-Grid Mode                                                      | 43110    | 2            |                     |
| Solis Battery Wakeup Switch                                              | 43110    | 3            |                     |
| Solis Reserve Battery Mode                                               | 43110    | 4            |                     |
| Solis Allow Grid to Charge the Battery                                   | 43110    | 5            |                     |
| Solis Feed-In Priority Mode                                              | 43110    | 6            |                     |
| Solis Batt OVC                                                           | 43110    | 7            |                     |
| Solis Battery Forcecharge Peakshaving                                    | 43110    | 8            |                     |
| Solis Battery Current Correction                                         | 43110    | 9            |                     |
| Solis RC Force Battery Charge                                            | 43135    |              |                     |
| Solis RC Force Battery Discharge                                         | 43135    |              |                     |
| Solis MPPT Parallel Function                                             | 43249    | 0            |                     |
| Solis IgFollow                                                           | 43249    | 1            |                     |
| Solis Relay Protection                                                   | 43249    | 2            |                     |
| Solis I-Leak Protection                                                  | 43249    | 3            |                     |
| Solis PV ISO Protection                                                  | 43249    | 4            |                     |
| Solis Grid-Interference Protection                                       | 43249    | 5            |                     |
| Solis The DC component of the grid current protection switch             | 43249    | 6            |                     |
| Solis Const Voltage Mode Enable Const Voltage                            | 43249    | 7            |                     |
| Solis Flexible Export Enabling Switch                                    | 43292    |              |                     |
| Solis Boost not-generate-wave function (off control)                     | 43302    | 0            | Inverted            |
| Solis DC injection adjustment function (off control)                     | 43302    | 1            | Inverted            |
| Solis MPPT Multi-peak scanning                                           | 43302    | 12           |                     |
| Solis 24-hour switch enable (S5 low-voltage energy storage)              | 43302    | 13           |                     |
| Solis Daily PV insulation detection                                      | 43302    | 14           |                     |
| Solis AFCI self-check                                                    | 43302    | 3            |                     |
| Solis AFCI self-check mode (abnormal / arc test data)                    | 43302    | 4            |                     |
| Solis Hybrid grid connect with neutral (1PH L1-L2-N / 3PH L1-L2-L3-N)    | 43302    | 8            | Inverted            |
| Solis PV enable (Alpha all-in-one)                                       | 43302    | 9            | Inverted            |
| Solis Generator Input Mode (off = Manual, on = Auto)                     | 43340    | 0            |                     |
| Solis Generator Charge Enable                                            | 43340    | 1            |                     |
| Solis Force Start Generator                                              | 43363    |              |                     |
| Solis Generator connection position                                      | 43365    | 0            |                     |
| Solis With Generator                                                     | 43365    | 1            |                     |
| Solis Generator enable signal                                            | 43365    | 2            |                     |
| Solis AC Coupling Position (off = GEN port, on = Backup port)            | 43365    | 3            |                     |
| Solis Generator access location                                          | 43365    | 4            |                     |
| Solis Dual Backup Enable                                                 | 43483    | 0            |                     |
| Solis AC Coupling Enable                                                 | 43483    | 1            |                     |
| Solis Smart load port grid-connected forced output                       | 43483    | 2            |                     |
| Solis Allow export switch under self-generation and self-use             | 43483    | 3            | Inverted            |
| Solis Backup2Load manual/automatic switch (off = Manual, on = Automatic) | 43483    | 4            |                     |
| Solis Backup2Load manual enable                                          | 43483    | 5            |                     |
| Solis Smart load port stops output when off-grid                         | 43483    | 6            |                     |
| Solis Grid Peak-shaving power enable                                     | 43483    | 7            |                     |
| Solis Grid Time of Use Charging Period 1                                 | 43707    | 0            |                     |
| Solis Grid Time of Use Charging Period 2                                 | 43707    | 1            |                     |
| Solis Grid Time of Use Discharge Period 5                                | 43707    | 10           |                     |
| Solis Grid Time of Use Discharge Period 6                                | 43707    | 11           |                     |
| Solis Grid Time of Use Charging Period 3                                 | 43707    | 2            |                     |
| Solis Grid Time of Use Charging Period 4                                 | 43707    | 3            |                     |
| Solis Grid Time of Use Charging Period 5                                 | 43707    | 4            |                     |
| Solis Grid Time of Use Charging Period 6                                 | 43707    | 5            |                     |
| Solis Grid Time of Use Discharge Period 1                                | 43707    | 6            |                     |
| Solis Grid Time of Use Discharge Period 2                                | 43707    | 7            |                     |
| Solis Grid Time of Use Discharge Period 3                                | 43707    | 8            |                     |
| Solis Grid Time of Use Discharge Period 4                                | 43707    | 9            |                     |
| Solis Generator charging period 1 switch                                 | 43815    | 0            |                     |
| Solis Generator charging period 2 switch                                 | 43815    | 1            |                     |
| Solis Generator charging period 3 switch                                 | 43815    | 2            |                     |
| Solis Generator charging period 4 switch                                 | 43815    | 3            |                     |
| Solis Generator charging period 5 switch                                 | 43815    | 4            |                     |
| Solis Generator charging period 6 switch                                 | 43815    | 5            |                     |
| Solis PV Shutdown                                                        | 44280    | 4            | Keep-alive while ON |
| Solis Modbus Enabled                                                     | 90005    | 0            |                     |
| Solis Enable power limit feature                                         | 3089     |              | write 3069          |

# Select Control Sensors

| Name                            | Register | Options                                                                                                                                                                                                                                                                                 |
|---------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Solis RC Grid Adjustment        | 43132    | OFF, System Grid Connection Point, Inverter AC Grid Port                                                                                                                                                                                                                                |
| Solis RC Force Charge/Discharge | 43135    | None, Solis RC Force Battery Charge, Solis RC Force Battery Discharge                                                                                                                                                                                                                   |
| Solis Storage Mode              | 43110    | Self-Use, Self-Use + TOU, Feed-in Priority, Feed-in Priority + TOU, Reserve / Backup, Reserve / Backup + TOU, Off-Grid Operation, Peak Shaving                                                                                                                                          |
| Solis Battery Model             | 43009    | No battery, PYLON_HV, User define, B_BOX_HV BYD, LG_HV LG, SOLUNA_HV, Dyness HV, Aoboet HV, WECO HV, Alpha HV, GS Energy, BYD-HVS/HVM/HVL, Jinko, FOX, LG_16H, PureDrive, UZ ENERGY, Reserve017, Lotus, Fortress, AMPACE_HV, WTS, J-PACK-HV, SUNWODA HV, LG Enblock S, General-LiBat-HV |

# Time Control Sensors

| Name                                            | Register |
|-------------------------------------------------|----------|
| Solis Time-Charging Charge Start (Slot 1)       | 43143    |
| Solis Time-Charging Charge End (Slot 1)         | 43145    |
| Solis Time-Charging Discharge Start (Slot 1)    | 43147    |
| Solis Time-Charging Discharge End (Slot 1)      | 43149    |
| Solis Time-Charging Charge Start (Slot 2)       | 43153    |
| Solis Time-Charging Charge End (Slot 2)         | 43155    |
| Solis Time-Charging Discharge Start (Slot 2)    | 43157    |
| Solis Time-Charging Discharge End (Slot 2)      | 43159    |
| Solis Time-Charging Charge Start (Slot 3)       | 43163    |
| Solis Time-Charging Charge End (Slot 3)         | 43165    |
| Solis Time-Charging Discharge Start (Slot 3)    | 43167    |
| Solis Time-Charging Discharge End (Slot 3)      | 43169    |
| Solis Time-Charging Charge Start (Slot 4)       | 43173    |
| Solis Time-Charging Charge End (Slot 4)         | 43175    |
| Solis Time-Charging Discharge Start (Slot 4)    | 43177    |
| Solis Time-Charging Discharge End (Slot 4)      | 43179    |
| Solis Time-Charging Charge Start (Slot 5)       | 43183    |
| Solis Time-Charging Charge End (Slot 5)         | 43185    |
| Solis Time-Charging Discharge Start (Slot 5)    | 43187    |
| Solis Time-Charging Discharge End (Slot 5)      | 43189    |
| Solis Grid Time of Use Charge Start (Slot 1)    | 43711    |
| Solis Grid Time of Use Charge End (Slot 1)      | 43713    |
| Solis Grid Time of Use Discharge Start (Slot 1) | 43753    |
| Solis Grid Time of Use Discharge End (Slot 1)   | 43755    |
| Solis Grid Time of Use Charge Start (Slot 2)    | 43718    |
| Solis Grid Time of Use Charge End (Slot 2)      | 43720    |
| Solis Grid Time of Use Discharge Start (Slot 2) | 43760    |
| Solis Grid Time of Use Discharge End (Slot 2)   | 43762    |
| Solis Grid Time of Use Charge Start (Slot 3)    | 43725    |
| Solis Grid Time of Use Charge End (Slot 3)      | 43727    |
| Solis Grid Time of Use Discharge Start (Slot 3) | 43767    |
| Solis Grid Time of Use Discharge End (Slot 3)   | 43769    |
| Solis Grid Time of Use Charge Start (Slot 4)    | 43732    |
| Solis Grid Time of Use Charge End (Slot 4)      | 43734    |
| Solis Grid Time of Use Discharge Start (Slot 4) | 43774    |
| Solis Grid Time of Use Discharge End (Slot 4)   | 43776    |
| Solis Grid Time of Use Charge Start (Slot 5)    | 43739    |
| Solis Grid Time of Use Charge End (Slot 5)      | 43741    |
| Solis Grid Time of Use Discharge Start (Slot 5) | 43781    |
| Solis Grid Time of Use Discharge End (Slot 5)   | 43783    |
| Solis Grid Time of Use Charge Start (Slot 6)    | 43746    |
| Solis Grid Time of Use Charge End (Slot 6)      | 43748    |
| Solis Grid Time of Use Discharge Start (Slot 6) | 43788    |
| Solis Grid Time of Use Discharge End (Slot 6)   | 43790    |

# Hybrid Inverter Sensors

| Name                                                      | Device Class   | Unit Of Measurement  | State Class      | Registers                                       |
|-----------------------------------------------------------|----------------|----------------------|------------------|-------------------------------------------------|
| Solis Model No                                            |                |                      |                  | 33000                                           |
| Solis DSP Version                                         |                |                      |                  | 33001                                           |
| Solis HMI Version                                         |                |                      |                  | 33002                                           |
| Solis Protocol Version                                    |                |                      |                  | 33003                                           |
| Solis Serial Number                                       |                |                      |                  | 33004 - 33019                                   |
| Solis Clock (Year)                                        |                |                      | MEASUREMENT      | 33022                                           |
| Solis Clock (Month)                                       |                |                      | MEASUREMENT      | 33023                                           |
| Solis Clock (Day)                                         |                |                      | MEASUREMENT      | 33024                                           |
| Solis Clock (Hours)                                       |                | HOURS                | MEASUREMENT      | 33025                                           |
| Solis Clock (Minutes)                                     |                | MINUTES              | MEASUREMENT      | 33026                                           |
| Solis Clock (Seconds)                                     |                | SECONDS              | MEASUREMENT      | 33027                                           |
| Solis PV Total Energy Generation                          | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33029, 33030                                    |
| Solis PV Current Month Energy Generation                  | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33031, 33032                                    |
| Solis PV Last Month Energy Generation                     | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33033, 33034                                    |
| Solis PV Today Energy Generation                          | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33035                                           |
| Solis PV Yesterday Energy Generation                      | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33036                                           |
| Solis PV This Year Energy Generation                      | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33037, 33038                                    |
| Solis PV Last Year Energy Generation                      | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33039, 33040                                    |
| Solis Max Inverter Current                                | CURRENT        | AMPERE               | MEASUREMENT      | 33041                                           |
| Solis Battery Temperature (BMS)                           | TEMPERATURE    | CELSIUS              | MEASUREMENT      | 33043                                           |
| Solis PV Power 1                                          | POWER          | WATT                 | MEASUREMENT      | 33049, 33050                                    |
| Solis PV Voltage 1                                        | VOLTAGE        | VOLT                 | MEASUREMENT      | 33049                                           |
| Solis PV Current 1                                        | CURRENT        | AMPERE               | MEASUREMENT      | 33050                                           |
| Solis PV Power 2                                          | POWER          | WATT                 | MEASUREMENT      | 33051, 33052                                    |
| Solis PV Voltage 2                                        | VOLTAGE        | VOLT                 | MEASUREMENT      | 33051                                           |
| Solis PV Current 2                                        | CURRENT        | AMPERE               | MEASUREMENT      | 33052                                           |
| Solis PV Power 3                                          | POWER          | WATT                 | MEASUREMENT      | 33053, 33054                                    |
| Solis PV Voltage 3                                        | VOLTAGE        | VOLT                 | MEASUREMENT      | 33053                                           |
| Solis PV Current 3                                        | CURRENT        | AMPERE               | MEASUREMENT      | 33054                                           |
| Solis PV Power 4                                          | POWER          | WATT                 | MEASUREMENT      | 33055, 33056                                    |
| Solis PV Voltage 4                                        | VOLTAGE        | VOLT                 | MEASUREMENT      | 33055                                           |
| Solis PV Current 4                                        | CURRENT        | AMPERE               | MEASUREMENT      | 33056                                           |
| Solis Total PV Power                                      | POWER          | WATT                 | MEASUREMENT      | 33057, 33058                                    |
| Solis Alarm code data                                     |                |                      | MEASUREMENT      | 33070                                           |
| Solis PV Bus Voltage                                      | VOLTAGE        | VOLT                 | MEASUREMENT      | 33071                                           |
| Solis PV Bus Half Voltage                                 | VOLTAGE        | VOLT                 | MEASUREMENT      | 33072                                           |
| Solis A Phase Voltage                                     | VOLTAGE        | VOLT                 | MEASUREMENT      | 33073                                           |
| Solis B Phase Voltage                                     | VOLTAGE        | VOLT                 | MEASUREMENT      | 33074                                           |
| Solis C Phase Voltage                                     | VOLTAGE        | VOLT                 | MEASUREMENT      | 33075                                           |
| Solis A Phase Current                                     | CURRENT        | AMPERE               | MEASUREMENT      | 33076                                           |
| Solis B Phase Current                                     | CURRENT        | AMPERE               | MEASUREMENT      | 33077                                           |
| Solis C Phase Current                                     | CURRENT        | AMPERE               | MEASUREMENT      | 33078                                           |
| Solis Active Power                                        | POWER          | WATT                 | MEASUREMENT      | 33079, 33080                                    |
| Solis Power Factor                                        |                |                      | MEASUREMENT      | 33079 - 33082                                   |
| Solis Reactive Power                                      | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 33081, 33082                                    |
| Solis Apparent Power                                      | APPARENT_POWER | VOLT_AMPERE          | MEASUREMENT      | 33083, 33084                                    |
| Solis Temperature                                         | TEMPERATURE    | CELSIUS              | MEASUREMENT      | 33093                                           |
| Solis Grid Frequency                                      | FREQUENCY      | HERTZ                | MEASUREMENT      | 33094                                           |
| Solis Status                                              |                |                      | MEASUREMENT      | 33095                                           |
| Solis Status String                                       |                |                      |                  | 33095                                           |
| Solis Lead-acid Battery Temperature                       | TEMPERATURE    | CELSIUS              | MEASUREMENT      | 33096                                           |
| Solis Grid Fault Status Bits                              |                |                      | MEASUREMENT      | 33116                                           |
| Solis Backup Fault Status Bits                            |                |                      | MEASUREMENT      | 33117                                           |
| Solis Battery Fault Status Bits                           |                |                      | MEASUREMENT      | 33118                                           |
| Solis Inverter Fault Status Bits 1                        |                |                      | MEASUREMENT      | 33119                                           |
| Solis Inverter Fault Status Bits 2                        |                |                      | MEASUREMENT      | 33120                                           |
| Solis Operating Status Bits                               |                |                      | MEASUREMENT      | 33121                                           |
| Solis Operating Mode                                      |                |                      | MEASUREMENT      | 33122                                           |
| Solis Grid Standard Mode Bits                             |                |                      | MEASUREMENT      | 33123                                           |
| Solis Meter Total Active Energy                           | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33126, 33127                                    |
| Solis Meter Voltage                                       | VOLTAGE        | VOLT                 | MEASUREMENT      | 33128                                           |
| Solis Meter Current                                       | CURRENT        | AMPERE               | MEASUREMENT      | 33129                                           |
| Solis Meter Active Power                                  | POWER          | WATT                 | MEASUREMENT      | 33130, 33131                                    |
| Solis Storage Control Switching Value                     |                |                      | MEASUREMENT      | 33132                                           |
| Solis Battery Voltage                                     | VOLTAGE        | VOLT                 | MEASUREMENT      | 33133                                           |
| Solis Battery Current                                     | CURRENT        | AMPERE               | MEASUREMENT      | 33134                                           |
| Solis Battery Current Direction                           |                |                      | MEASUREMENT      | 33135                                           |
| Solis LLC Bus Voltage                                     | VOLTAGE        | VOLT                 | MEASUREMENT      | 33136                                           |
| Solis Backup AC Voltage Phase A                           | VOLTAGE        | VOLT                 | MEASUREMENT      | 33137                                           |
| Solis Backup AC Current Phase A                           | CURRENT        | AMPERE               | MEASUREMENT      | 33138                                           |
| Solis Battery SOC                                         | BATTERY        | %                    | MEASUREMENT      | 33139                                           |
| Solis Battery SOH                                         |                | %                    | MEASUREMENT      | 33140                                           |
| Solis Battery Voltage (BMS)                               | VOLTAGE        | VOLT                 | MEASUREMENT      | 33141                                           |
| Solis Battery Current (BMS)                               | CURRENT        | AMPERE               | MEASUREMENT      | 33142                                           |
| Solis Battery Charge Current Limitation (BMS)             | CURRENT        | AMPERE               | MEASUREMENT      | 33143                                           |
| Solis Battery Discharge Current Limitation (BMS)          | CURRENT        | AMPERE               | MEASUREMENT      | 33144                                           |
| Solis Battery Fault Status 1 (BMS)                        |                |                      | MEASUREMENT      | 33145                                           |
| Solis Battery Fault Status 2 (BMS)                        |                |                      | MEASUREMENT      | 33146                                           |
| Solis Household load power                                | POWER          | WATT                 | MEASUREMENT      | 33147                                           |
| Solis Backup Load power                                   | POWER          | WATT                 | MEASUREMENT      | 33148                                           |
| Solis Battery Charge Power                                | POWER          | WATT                 | MEASUREMENT      | 33149, 33150, 33135, 0                          |
| Solis Battery Discharge Power                             | POWER          | WATT                 | MEASUREMENT      | 33149, 33150, 33135, 1                          |
| Solis Battery Power                                       | POWER          | WATT                 | MEASUREMENT      | 33149, 33150                                    |
| Solis Battery Power Net                                   | POWER          | WATT                 | MEASUREMENT      | 33149, 33150, 33135                             |
| Solis AC Grid Port Power                                  | POWER          | WATT                 | MEASUREMENT      | 33151, 33152                                    |
| Solis Backup AC Voltage Phase B                           | VOLTAGE        | VOLT                 | MEASUREMENT      | 33153                                           |
| Solis Backup AC Current Phase B                           | CURRENT        | AMPERE               | MEASUREMENT      | 33154                                           |
| Solis Backup AC Voltage Phase C                           | VOLTAGE        | VOLT                 | MEASUREMENT      | 33155                                           |
| Solis Backup AC Current Phase C                           | CURRENT        | AMPERE               | MEASUREMENT      | 33156                                           |
| Solis Inverting Rectifying Power                          | POWER          | WATT                 | MEASUREMENT      | 33157                                           |
| Solis Total Battery Charge Energy                         | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33161, 33162                                    |
| Solis Today Battery Charge Energy                         | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33163                                           |
| Solis Yesterday Battery Charge Energy                     | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33164                                           |
| Solis Total Battery Discharge Energy                      | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33165, 33166                                    |
| Solis Today Battery Discharge Energy                      | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33167                                           |
| Solis Yesterday Battery Discharge Energy                  | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33168                                           |
| Solis Total Energy Imported From Grid                     | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33169, 33170                                    |
| Solis Today Energy Imported From Grid                     | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33171                                           |
| Solis Yesterday Energy Imported From Grid                 | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33172                                           |
| Solis Total Energy Fed Into Grid                          | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33173, 33174                                    |
| Solis Today Energy Fed Into Grid                          | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33175                                           |
| Solis Today Net Grid Energy                               | ENERGY         | KILO_WATT_HOUR       | TOTAL            | 33175, 33171                                    |
| Solis Yesterday Energy Fed Into Grid                      | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33176                                           |
| Solis Total Energy Consumption                            | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33177, 33178                                    |
| Solis Today Energy Consumption                            | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33179                                           |
| Solis Yesterday Energy Consumption                        | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33180                                           |
| Solis AC Grid Port Total Energy Fed In                    | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33186, 33187                                    |
| Solis AC Grid Port Total Energy Consumption               | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33188, 33189                                    |
| Solis Backup Output Enabled Mirror                        |                |                      | MEASUREMENT      | 33200                                           |
| Solis Backup Voltage Reference                            | VOLTAGE        | VOLT                 | MEASUREMENT      | 33201                                           |
| Solis Backup Frequency Reference                          | FREQUENCY      | HERTZ                | MEASUREMENT      | 33202                                           |
| Solis Battery Charge Discharge Enabled Mirror             |                |                      | MEASUREMENT      | 33203                                           |
| Solis Battery Direction Mirror                            |                |                      | MEASUREMENT      | 33204                                           |
| Solis Battery Max Charge Current Mirror                   | CURRENT        | AMPERE               | MEASUREMENT      | 33206                                           |
| Solis Battery Max Discharge Current Mirror                | CURRENT        | AMPERE               | MEASUREMENT      | 33207                                           |
| Solis Overdischarge SOC Mirror                            | BATTERY        | %                    | MEASUREMENT      | 33213                                           |
| Solis Force Charge SOC Mirror                             | BATTERY        | %                    | MEASUREMENT      | 33214                                           |
| Solis AFCI Status                                         |                |                      | MEASUREMENT      | 33215                                           |
| Solis Leakage Current                                     | CURRENT        | AMPERE               | MEASUREMENT      | 33216                                           |
| Solis Battery Current Fast                                | CURRENT        | AMPERE               | MEASUREMENT      | 33217                                           |
| Solis Parallel Inverter AC Current                        | CURRENT        | AMPERE               | MEASUREMENT      | 33243                                           |
| Solis Parallel Inverter AC Voltage                        | VOLTAGE        | VOLT                 | MEASUREMENT      | 33244                                           |
| Solis Parallel Inverter Power                             | POWER          | KILO_WATT            | MEASUREMENT      | 33245                                           |
| Solis Parallel CT Detection                               |                |                      | MEASUREMENT      | 33246                                           |
| Solis EPM Setpoint Power                                  | POWER          | WATT                 | MEASUREMENT      | 33247                                           |
| Solis EPM Status Bits                                     |                |                      | MEASUREMENT      | 33248                                           |
| Solis EPM Backflow Power Realtime                         | POWER          | WATT                 | MEASUREMENT      | 33249                                           |
| Solis Meter Placement Status Bits                         |                |                      | MEASUREMENT      | 33250                                           |
| Solis Meter AC Voltage A                                  | VOLTAGE        | VOLT                 | MEASUREMENT      | 33251                                           |
| Solis Meter AC Current A                                  | CURRENT        | AMPERE               | MEASUREMENT      | 33252                                           |
| Solis Meter AC Voltage B                                  | VOLTAGE        | VOLT                 | MEASUREMENT      | 33253                                           |
| Solis Meter AC Current B                                  | CURRENT        | AMPERE               | MEASUREMENT      | 33254                                           |
| Solis Meter AC Voltage C                                  | VOLTAGE        | VOLT                 | MEASUREMENT      | 33255                                           |
| Solis Meter AC Current C                                  | CURRENT        | AMPERE               | MEASUREMENT      | 33256                                           |
| Solis Meter Active Power A                                | POWER          | WATT                 | MEASUREMENT      | 33257, 33258                                    |
| Solis Meter Active Power B                                | POWER          | WATT                 | MEASUREMENT      | 33259, 33260                                    |
| Solis Meter Active Power C                                | POWER          | WATT                 | MEASUREMENT      | 33261, 33262                                    |
| Solis Grid Power Net                                      | POWER          | WATT                 | MEASUREMENT      | 33263, 33264                                    |
| Solis Meter Total Active Power                            | POWER          | WATT                 | MEASUREMENT      | 33263, 33264                                    |
| Solis Meter Reactive Power A                              | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 33265, 33266                                    |
| Solis Meter Reactive Power B                              | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 33267, 33268                                    |
| Solis Meter Reactive Power C                              | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 33269, 33270                                    |
| Solis Meter Total Reactive Power                          | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 33271, 33272                                    |
| Solis Meter Apparent Power A                              | APPARENT_POWER | VOLT_AMPERE          | MEASUREMENT      | 33273, 33274                                    |
| Solis Meter Apparent Power B                              | APPARENT_POWER | VOLT_AMPERE          | MEASUREMENT      | 33275, 33276                                    |
| Solis Meter Apparent Power C                              | APPARENT_POWER | VOLT_AMPERE          | MEASUREMENT      | 33277, 33278                                    |
| Solis Meter Total Apparent Power                          | APPARENT_POWER | VOLT_AMPERE          | MEASUREMENT      | 33279, 33280                                    |
| Solis Meter Power Factor                                  | POWER_FACTOR   | %                    | MEASUREMENT      | 33281                                           |
| Solis Meter Grid Frequency                                | FREQUENCY      | HERTZ                | MEASUREMENT      | 33282                                           |
| Solis Meter Total Active Energy From Grid                 | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33283, 33284                                    |
| Solis Meter Total Active Energy To Grid                   | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33285, 33286                                    |
| Solis Meter 1 Type and Location                           |                |                      | MEASUREMENT      | 33300                                           |
| Solis Meter 2 Type and Location                           |                |                      | MEASUREMENT      | 33301                                           |
| Solis Meter 2 AC Voltage A                                | VOLTAGE        | VOLT                 | MEASUREMENT      | 33302                                           |
| Solis Meter 2 AC Current A                                | CURRENT        | AMPERE               | MEASUREMENT      | 33303                                           |
| Solis Meter 2 AC Voltage B                                | VOLTAGE        | VOLT                 | MEASUREMENT      | 33304                                           |
| Solis Meter 2 AC Current B                                | CURRENT        | AMPERE               | MEASUREMENT      | 33305                                           |
| Solis Meter 2 AC Voltage C                                | VOLTAGE        | VOLT                 | MEASUREMENT      | 33306                                           |
| Solis Meter 2 AC Current C                                | CURRENT        | AMPERE               | MEASUREMENT      | 33307                                           |
| Solis Meter 2 Active Power A                              | POWER          | WATT                 | MEASUREMENT      | 33308, 33309                                    |
| Solis Meter 2 Active Power B                              | POWER          | WATT                 | MEASUREMENT      | 33310, 33311                                    |
| Solis Meter 2 Active Power C                              | POWER          | WATT                 | MEASUREMENT      | 33312, 33313                                    |
| Solis Meter 2 Total Active Power                          | POWER          | WATT                 | MEASUREMENT      | 33314, 33315                                    |
| Solis Meter 2 Reactive Power A                            | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 33316, 33317                                    |
| Solis Meter 2 Reactive Power B                            | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 33318, 33319                                    |
| Solis Meter 2 Reactive Power C                            | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 33320, 33321                                    |
| Solis Meter 2 Total Reactive Power                        | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 33322, 33323                                    |
| Solis Meter 2 Apparent Power A                            | APPARENT_POWER | VOLT_AMPERE          | MEASUREMENT      | 33324, 33325                                    |
| Solis Meter 2 Apparent Power B                            | APPARENT_POWER | VOLT_AMPERE          | MEASUREMENT      | 33326, 33327                                    |
| Solis Meter 2 Apparent Power C                            | APPARENT_POWER | VOLT_AMPERE          | MEASUREMENT      | 33328, 33329                                    |
| Solis Meter 2 Total Apparent Power                        | APPARENT_POWER | VOLT_AMPERE          | MEASUREMENT      | 33330, 33331                                    |
| Solis Meter 2 Power Factor                                | POWER_FACTOR   | %                    | MEASUREMENT      | 33332                                           |
| Solis Meter 2 Grid Frequency                              | FREQUENCY      | HERTZ                | MEASUREMENT      | 33333                                           |
| Solis Meter 2 Total Active Energy From Grid               | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33334, 33335                                    |
| Solis Meter 2 Total Active Energy To Grid                 | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33336, 33337                                    |
| Solis Generator Phase A Active Power                      | POWER          | WATT                 | MEASUREMENT      | 33530                                           |
| Solis Generator Today Energy                              | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33531                                           |
| Solis Generator Total Energy                              | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33532, 33533                                    |
| Solis Generator Phase B Active Power                      | POWER          | WATT                 | MEASUREMENT      | 33534                                           |
| Solis Generator Phase C Active Power                      | POWER          | WATT                 | MEASUREMENT      | 33535                                           |
| Solis Household Load Total Energy                         | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33580, 33581                                    |
| Solis Household Load Year Energy                          | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33582, 33583                                    |
| Solis Household Load Month Energy                         | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33584, 33585                                    |
| Solis Household Load Today Energy                         | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33586                                           |
| Solis Backup Load Total Energy                            | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33590, 33591                                    |
| Solis Backup Load Year Energy                             | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33592, 33593                                    |
| Solis Backup Load Month Energy                            | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33594, 33595                                    |
| Solis Backup Load Today Energy                            | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 33596                                           |
| Solis Parallel Synchronization Setting Parameter Result   |                |                      |                  | 34243                                           |
| Solis SmartPort A Phase Voltage                           | VOLTAGE        | VOLT                 | MEASUREMENT      | 34328                                           |
| Solis SmartPort B Phase Voltage                           | VOLTAGE        | VOLT                 | MEASUREMENT      | 34329                                           |
| Solis SmartPort C Phase Voltage                           | VOLTAGE        | VOLT                 | MEASUREMENT      | 34330                                           |
| Solis SmartPort A Phase Current                           | CURRENT        | AMPERE               | MEASUREMENT      | 34331                                           |
| Solis SmartPort B Phase Current                           | CURRENT        | AMPERE               | MEASUREMENT      | 34332                                           |
| Solis SmartPort C Phase Current                           | CURRENT        | AMPERE               | MEASUREMENT      | 34333                                           |
| Solis Smart Port Phase A Active Power                     | POWER          | WATT                 | MEASUREMENT      | 34391                                           |
| Solis Smart Port Phase B Active Power                     | POWER          | WATT                 | MEASUREMENT      | 34392                                           |
| Solis Smart Port Phase C Active Power                     | POWER          | WATT                 | MEASUREMENT      | 34393                                           |
| Solis AC Coupling Total Power Generation                  | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 34445, 34446                                    |
| Solis AC Coupling Year Power Generation                   | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 34447, 34448                                    |
| Solis AC Coupling Month Power Generation                  | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 34449, 34450                                    |
| Solis AC Coupling Today Power Generation                  | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 34451                                           |
| Solis AC Coupling Yesterday Power Generation              | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 34452                                           |
| Solis AC Coupling Total Active Power                      | POWER          | WATT                 | MEASUREMENT      | 34496, 34497                                    |
| Solis Remote Dispatch Capability                          |                |                      | MEASUREMENT      | 34502                                           |
| Solis Remote Dispatch Function Map                        |                |                      | MEASUREMENT      | 34503                                           |
| Solis Remote Dispatch Running Status                      |                |                      | MEASUREMENT      | 34504                                           |
| Solis Inverter Type Definition                            |                |                      |                  | 35000                                           |
| Solis Inverter model definition                           |                |                      |                  | 35000                                           |
| Solis Power State                                         |                |                      | MEASUREMENT      | 43007                                           |
| Solis Battery Model                                       |                |                      | MEASUREMENT      | 43009                                           |
| Solis Max Charge SOC                                      |                | %                    | MEASUREMENT      | 43010                                           |
| Solis Overdischarge SOC                                   | BATTERY        | %                    | MEASUREMENT      | 43011                                           |
| Solis Max Charge Current                                  | CURRENT        | AMPERE               |                  | 43012                                           |
| Solis Max Discharge Current                               | CURRENT        | AMPERE               |                  | 43013                                           |
| Solis Floating Charge Voltage                             | VOLTAGE        | VOLT                 | MEASUREMENT      | 43016                                           |
| Solis Equalizing Charge Voltage                           | VOLTAGE        | VOLT                 | MEASUREMENT      | 43017                                           |
| Solis Force Charge SOC                                    |                | %                    | MEASUREMENT      | 43018                                           |
| Solis Battery Rated Capacity                              |                | Ah                   |                  | 43019                                           |
| Solis Overdischarge Voltage                               | VOLTAGE        | VOLT                 | MEASUREMENT      | 43020                                           |
| Solis Forcecharge Voltage                                 | VOLTAGE        | VOLT                 | MEASUREMENT      | 43021                                           |
| Solis Backup SOC                                          |                | %                    | MEASUREMENT      | 43024                                           |
| Solis Force-charge Power Limitation                       | POWER          | WATT                 | MEASUREMENT      | 43027                                           |
| Solis Battery Force Charge Source                         |                |                      | MEASUREMENT      | 43028                                           |
| Solis Output Limit Gate                                   |                |                      | MEASUREMENT      | 43070                                           |
| Solis Grid feed in Switch value                           |                |                      | MEASUREMENT      | 43073                                           |
| Solis Backflow Power                                      | POWER          | WATT                 |                  | 43074                                           |
| Solis Output Power Clamp                                  | POWER          | WATT                 | MEASUREMENT      | 43081                                           |
| Solis Storage control Switch value                        |                |                      | MEASUREMENT      | 43110                                           |
| Solis Battery Max Charge Current                          | CURRENT        | AMPERE               |                  | 43117                                           |
| Solis Battery Max Discharge Current                       | CURRENT        | AMPERE               |                  | 43118                                           |
| Solis RC Inverter AC Grid Active Power                    | POWER          | WATT                 | MEASUREMENT      | 43128                                           |
| Solis RC Force Battery Discharge Power                    | POWER          | WATT                 | MEASUREMENT      | 43129                                           |
| Solis Battery Charge Limit Power                          | POWER          | WATT                 | MEASUREMENT      | 43130                                           |
| Solis Battery Discharge Limit Power                       | POWER          | WATT                 | MEASUREMENT      | 43131                                           |
| Solis RC Grid Adjustment                                  |                |                      | MEASUREMENT      | 43132                                           |
| Solis RC Grid Active Power                                | POWER          | WATT                 | MEASUREMENT      | 43133                                           |
| Solis RC Grid Reactive Power                              | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 43134                                           |
| Solis RC Force Battery Charge/discharge                   |                |                      | MEASUREMENT      | 43135                                           |
| Solis RC Force Battery Charge Power                       | POWER          | WATT                 | MEASUREMENT      | 43136                                           |
| Solis Off-Grid Overdischarge SOC                          | BATTERY        | %                    | MEASUREMENT      | 43137                                           |
| Solis Time-Charging Charge Current                        | CURRENT        | AMPERE               | MEASUREMENT      | 43141                                           |
| Solis Time-Charging Discharge Current                     | CURRENT        | AMPERE               | MEASUREMENT      | 43142                                           |
| Solis Time-Charging Charge Start Hour (Slot 1)            |                | HOURS                | MEASUREMENT      | 43143                                           |
| Solis Time-Charging Charge Start Minute (Slot 1)          |                | MINUTES              | MEASUREMENT      | 43144                                           |
| Solis Time-Charging Charge End Hour (Slot 1)              |                | HOURS                | MEASUREMENT      | 43145                                           |
| Solis Time-Charging Charge End Minute (Slot 1)            |                | MINUTES              | MEASUREMENT      | 43146                                           |
| Solis Time-Charging Discharge Start Hour (Slot 1)         |                | HOURS                | MEASUREMENT      | 43147                                           |
| Solis Time-Charging Discharge Start Minute (Slot 1)       |                | MINUTES              | MEASUREMENT      | 43148                                           |
| Solis Time-Charging Discharge End Hour (Slot 1)           |                | HOURS                | MEASUREMENT      | 43149                                           |
| Solis Time-Charging Discharge End Minute (Slot 1)         |                | MINUTES              | MEASUREMENT      | 43150                                           |
| Solis Time-Charging Charge Start Hour (Slot 2)            |                | HOURS                | MEASUREMENT      | 43153                                           |
| Solis Time-Charging Charge Start Minute (Slot 2)          |                | MINUTES              | MEASUREMENT      | 43154                                           |
| Solis Time-Charging Charge End Hour (Slot 2)              |                | HOURS                | MEASUREMENT      | 43155                                           |
| Solis Time-Charging Charge End Minute (Slot 2)            |                | MINUTES              | MEASUREMENT      | 43156                                           |
| Solis Time-Charging Discharge Start Hour (Slot 2)         |                | HOURS                | MEASUREMENT      | 43157                                           |
| Solis Time-Charging Discharge Start Minute (Slot 2)       |                | MINUTES              | MEASUREMENT      | 43158                                           |
| Solis Time-Charging Discharge End Hour (Slot 2)           |                | HOURS                | MEASUREMENT      | 43159                                           |
| Solis Time-Charging Discharge End Minute (Slot 2)         |                | MINUTES              | MEASUREMENT      | 43160                                           |
| Solis Time-Charging Charge Start Hour (Slot 3)            |                | HOURS                | MEASUREMENT      | 43163                                           |
| Solis Time-Charging Charge Start Minute (Slot 3)          |                | MINUTES              | MEASUREMENT      | 43164                                           |
| Solis Time-Charging Charge End Hour (Slot 3)              |                | HOURS                | MEASUREMENT      | 43165                                           |
| Solis Time-Charging Charge End Minute (Slot 3)            |                | MINUTES              | MEASUREMENT      | 43166                                           |
| Solis Time-Charging Discharge Start Hour (Slot 3)         |                | HOURS                | MEASUREMENT      | 43167                                           |
| Solis Time-Charging Discharge Start Minute (Slot 3)       |                | MINUTES              | MEASUREMENT      | 43168                                           |
| Solis Time-Charging Discharge End Hour (Slot 3)           |                | HOURS                | MEASUREMENT      | 43169                                           |
| Solis Time-Charging Discharge End Minute (Slot 3)         |                | MINUTES              | MEASUREMENT      | 43170                                           |
| Solis Time-Charging Charge Start Hour (Slot 4)            |                | HOURS                | MEASUREMENT      | 43173                                           |
| Solis Time-Charging Charge Start Minute (Slot 4)          |                | MINUTES              | MEASUREMENT      | 43174                                           |
| Solis Time-Charging Charge End Hour (Slot 4)              |                | HOURS                | MEASUREMENT      | 43175                                           |
| Solis Time-Charging Charge End Minute (Slot 4)            |                | MINUTES              | MEASUREMENT      | 43176                                           |
| Solis Time-Charging Discharge Start Hour (Slot 4)         |                | HOURS                | MEASUREMENT      | 43177                                           |
| Solis Time-Charging Discharge Start Minute (Slot 4)       |                | MINUTES              | MEASUREMENT      | 43178                                           |
| Solis Time-Charging Discharge End Hour (Slot 4)           |                | HOURS                | MEASUREMENT      | 43179                                           |
| Solis Time-Charging Discharge End Minute (Slot 4)         |                | MINUTES              | MEASUREMENT      | 43180                                           |
| Solis Time-Charging Charge Start Hour (Slot 5)            |                | HOURS                | MEASUREMENT      | 43183                                           |
| Solis Time-Charging Charge Start Minute (Slot 5)          |                | MINUTES              | MEASUREMENT      | 43184                                           |
| Solis Time-Charging Charge End Hour (Slot 5)              |                | HOURS                | MEASUREMENT      | 43185                                           |
| Solis Time-Charging Charge End Minute (Slot 5)            |                | MINUTES              | MEASUREMENT      | 43186                                           |
| Solis Time-Charging Discharge Start Hour (Slot 5)         |                | HOURS                | MEASUREMENT      | 43187                                           |
| Solis Time-Charging Discharge Start Minute (Slot 5)       |                | MINUTES              | MEASUREMENT      | 43188                                           |
| Solis Time-Charging Discharge End Hour (Slot 5)           |                | HOURS                | MEASUREMENT      | 43189                                           |
| Solis Time-Charging Discharge End Minute (Slot 5)         |                | MINUTES              | MEASUREMENT      | 43190                                           |
| Solis Export Calibration                                  | POWER          | WATT                 |                  | 43195                                           |
| Solis Special Settings                                    |                |                      | MEASUREMENT      | 43249                                           |
| Solis RC Timeout                                          |                | MINUTES              |                  | 43282                                           |
| Solis Flexible Export Backflow Power                      | POWER          | WATT                 | MEASUREMENT      | 43291                                           |
| Solis Flexible Export Enabling Switch                     |                |                      | MEASUREMENT      | 43292                                           |
| Solis Hybrid auxiliary control flags                      |                |                      | MEASUREMENT      | 43302                                           |
| Solis Generator Set Enable Switch                         |                |                      | MEASUREMENT      | 43340                                           |
| Solis MPPT Scanning Interval                              |                | SECONDS              | MEASUREMENT      | 43361                                           |
| Solis Forced Start of Generator                           |                |                      | MEASUREMENT      | 43363                                           |
| Solis Rated Input Power of Generator                      | POWER          | KILO_WATT            | MEASUREMENT      | 43364                                           |
| Solis Generator Setting Switch                            |                |                      | MEASUREMENT      | 43365                                           |
| Solis Generator Forced Stop of Generator                  |                |                      | MEASUREMENT      | 43366                                           |
| Solis Maximum Allowable Percentage of Generator           |                | %                    | MEASUREMENT      | 43367                                           |
| Solis Generator Target Power                              | POWER          | KILO_WATT            | MEASUREMENT      | 43368                                           |
| Solis Generator Charging Power                            | POWER          | KILO_WATT            | MEASUREMENT      | 43369                                           |
| Solis Hybrid Function Control                             |                |                      | MEASUREMENT      | 43483                                           |
| Solis Peak Baseline SOC                                   |                | %                    | MEASUREMENT      | 43487                                           |
| Solis Peak Max Usable Grid Power                          | POWER          | WATT                 | MEASUREMENT      | 43488                                           |
| Solis Time of Use V2 Switch                               |                |                      |                  | 43707                                           |
| Solis Grid Time of Use Charge cut off SOC (Slot 1)        |                | %                    | MEASUREMENT      | 43708                                           |
| Solis Grid Time of Use Charge battery current (Slot 1)    | CURRENT        | AMPERE               | MEASUREMENT      | 43709                                           |
| Solis Grid Time of Use Charge cut off voltage (Slot 1)    | VOLTAGE        | VOLT                 | MEASUREMENT      | 43710                                           |
| Solis Grid Time of Use Charge Start Hour (Slot 1)         |                | HOURS                | MEASUREMENT      | 43711                                           |
| Solis Grid Time of Use Charge Start Minute (Slot 1)       |                | MINUTES              | MEASUREMENT      | 43712                                           |
| Solis Grid Time of Use Charge End Hour (Slot 1)           |                | HOURS                | MEASUREMENT      | 43713                                           |
| Solis Grid Time of Use Charge End Minute (Slot 1)         |                | MINUTES              | MEASUREMENT      | 43714                                           |
| Solis Grid Time of Use Charge cut off SOC (Slot 2)        |                | %                    | MEASUREMENT      | 43715                                           |
| Solis Grid Time of Use Charge battery current (Slot 2)    | CURRENT        | AMPERE               | MEASUREMENT      | 43716                                           |
| Solis Grid Time of Use Charge cut off voltage (Slot 2)    | VOLTAGE        | VOLT                 | MEASUREMENT      | 43717                                           |
| Solis Grid Time of Use Charge Start Hour (Slot 2)         |                | HOURS                | MEASUREMENT      | 43718                                           |
| Solis Grid Time of Use Charge Start Minute (Slot 2)       |                | MINUTES              | MEASUREMENT      | 43719                                           |
| Solis Grid Time of Use Charge End Hour (Slot 2)           |                | HOURS                | MEASUREMENT      | 43720                                           |
| Solis Grid Time of Use Charge End Minute (Slot 2)         |                | MINUTES              | MEASUREMENT      | 43721                                           |
| Solis Grid Time of Use Charge cut off SOC (Slot 3)        |                | %                    | MEASUREMENT      | 43722                                           |
| Solis Grid Time of Use Charge battery current (Slot 3)    | CURRENT        | AMPERE               | MEASUREMENT      | 43723                                           |
| Solis Grid Time of Use Charge cut off voltage (Slot 3)    | VOLTAGE        | VOLT                 | MEASUREMENT      | 43724                                           |
| Solis Grid Time of Use Charge Start Hour (Slot 3)         |                | HOURS                | MEASUREMENT      | 43725                                           |
| Solis Grid Time of Use Charge Start Minute (Slot 3)       |                | MINUTES              | MEASUREMENT      | 43726                                           |
| Solis Grid Time of Use Charge End Hour (Slot 3)           |                | HOURS                | MEASUREMENT      | 43727                                           |
| Solis Grid Time of Use Charge End Minute (Slot 3)         |                | MINUTES              | MEASUREMENT      | 43728                                           |
| Solis Grid Time of Use Charge cut off SOC (Slot 4)        |                | %                    | MEASUREMENT      | 43729                                           |
| Solis Grid Time of Use Charge battery current (Slot 4)    | CURRENT        | AMPERE               | MEASUREMENT      | 43730                                           |
| Solis Grid Time of Use Charge cut off voltage (Slot 4)    | VOLTAGE        | VOLT                 | MEASUREMENT      | 43731                                           |
| Solis Grid Time of Use Charge Start Hour (Slot 4)         |                | HOURS                | MEASUREMENT      | 43732                                           |
| Solis Grid Time of Use Charge Start Minute (Slot 4)       |                | MINUTES              | MEASUREMENT      | 43733                                           |
| Solis Grid Time of Use Charge End Hour (Slot 4)           |                | HOURS                | MEASUREMENT      | 43734                                           |
| Solis Grid Time of Use Charge End Minute (Slot 4)         |                | MINUTES              | MEASUREMENT      | 43735                                           |
| Solis Grid Time of Use Charge cut off SOC (Slot 5)        |                | %                    | MEASUREMENT      | 43736                                           |
| Solis Grid Time of Use Charge battery current (Slot 5)    | CURRENT        | AMPERE               | MEASUREMENT      | 43737                                           |
| Solis Grid Time of Use Charge cut off voltage (Slot 5)    | VOLTAGE        | VOLT                 | MEASUREMENT      | 43738                                           |
| Solis Grid Time of Use Charge Start Hour (Slot 5)         |                | HOURS                | MEASUREMENT      | 43739                                           |
| Solis Grid Time of Use Charge Start Minute (Slot 5)       |                | MINUTES              | MEASUREMENT      | 43740                                           |
| Solis Grid Time of Use Charge End Hour (Slot 5)           |                | HOURS                | MEASUREMENT      | 43741                                           |
| Solis Grid Time of Use Charge End Minute (Slot 5)         |                | MINUTES              | MEASUREMENT      | 43742                                           |
| Solis Grid Time of Use Charge cut off SOC (Slot 6)        |                | %                    | MEASUREMENT      | 43743                                           |
| Solis Grid Time of Use Charge battery current (Slot 6)    | CURRENT        | AMPERE               | MEASUREMENT      | 43744                                           |
| Solis Grid Time of Use Charge cut off voltage (Slot 6)    | VOLTAGE        | VOLT                 | MEASUREMENT      | 43745                                           |
| Solis Grid Time of Use Charge Start Hour (Slot 6)         |                | HOURS                | MEASUREMENT      | 43746                                           |
| Solis Grid Time of Use Charge Start Minute (Slot 6)       |                | MINUTES              | MEASUREMENT      | 43747                                           |
| Solis Grid Time of Use Charge End Hour (Slot 6)           |                | HOURS                | MEASUREMENT      | 43748                                           |
| Solis Grid Time of Use Charge End Minute (Slot 6)         |                | MINUTES              | MEASUREMENT      | 43749                                           |
| Solis Grid Time of Use Discharge cut off SOC (Slot 1)     |                | %                    | MEASUREMENT      | 43750                                           |
| Solis Grid Time of Use Discharge battery current (Slot 1) | CURRENT        | AMPERE               | MEASUREMENT      | 43751                                           |
| Solis Grid Time of Use Discharge cut off voltage (Slot 1) | VOLTAGE        | VOLT                 | MEASUREMENT      | 43752                                           |
| Solis Grid Time of Use Discharge Start Hour (Slot 1)      |                | HOURS                | MEASUREMENT      | 43753                                           |
| Solis Grid Time of Use Discharge Start Minute (Slot 1)    |                | MINUTES              | MEASUREMENT      | 43754                                           |
| Solis Grid Time of Use Discharge End Hour (Slot 1)        |                | HOURS                | MEASUREMENT      | 43755                                           |
| Solis Grid Time of Use Discharge End Minute (Slot 1)      |                | MINUTES              | MEASUREMENT      | 43756                                           |
| Solis Grid Time of Use Discharge cut off SOC (Slot 2)     |                | %                    | MEASUREMENT      | 43757                                           |
| Solis Grid Time of Use Discharge battery current (Slot 2) | CURRENT        | AMPERE               | MEASUREMENT      | 43758                                           |
| Solis Grid Time of Use Discharge cut off voltage (Slot 2) | VOLTAGE        | VOLT                 | MEASUREMENT      | 43759                                           |
| Solis Grid Time of Use Discharge Start Hour (Slot 2)      |                | HOURS                | MEASUREMENT      | 43760                                           |
| Solis Grid Time of Use Discharge Start Minute (Slot 2)    |                | MINUTES              | MEASUREMENT      | 43761                                           |
| Solis Grid Time of Use Discharge End Hour (Slot 2)        |                | HOURS                | MEASUREMENT      | 43762                                           |
| Solis Grid Time of Use Discharge End Minute (Slot 2)      |                | MINUTES              | MEASUREMENT      | 43763                                           |
| Solis Grid Time of Use Discharge cut off SOC (Slot 3)     |                | %                    | MEASUREMENT      | 43764                                           |
| Solis Grid Time of Use Discharge battery current (Slot 3) | CURRENT        | AMPERE               | MEASUREMENT      | 43765                                           |
| Solis Grid Time of Use Discharge cut off voltage (Slot 3) | VOLTAGE        | VOLT                 | MEASUREMENT      | 43766                                           |
| Solis Grid Time of Use Discharge Start Hour (Slot 3)      |                | HOURS                | MEASUREMENT      | 43767                                           |
| Solis Grid Time of Use Discharge Start Minute (Slot 3)    |                | MINUTES              | MEASUREMENT      | 43768                                           |
| Solis Grid Time of Use Discharge End Hour (Slot 3)        |                | HOURS                | MEASUREMENT      | 43769                                           |
| Solis Grid Time of Use Discharge End Minute (Slot 3)      |                | MINUTES              | MEASUREMENT      | 43770                                           |
| Solis Grid Time of Use Discharge cut off SOC (Slot 4)     |                | %                    | MEASUREMENT      | 43771                                           |
| Solis Grid Time of Use Discharge battery current (Slot 4) | CURRENT        | AMPERE               | MEASUREMENT      | 43772                                           |
| Solis Grid Time of Use Discharge cut off voltage (Slot 4) | VOLTAGE        | VOLT                 | MEASUREMENT      | 43773                                           |
| Solis Grid Time of Use Discharge Start Hour (Slot 4)      |                | HOURS                | MEASUREMENT      | 43774                                           |
| Solis Grid Time of Use Discharge Start Minute (Slot 4)    |                | MINUTES              | MEASUREMENT      | 43775                                           |
| Solis Grid Time of Use Discharge End Hour (Slot 4)        |                | HOURS                | MEASUREMENT      | 43776                                           |
| Solis Grid Time of Use Discharge End Minute (Slot 4)      |                | MINUTES              | MEASUREMENT      | 43777                                           |
| Solis Grid Time of Use Discharge cut off SOC (Slot 5)     |                | %                    | MEASUREMENT      | 43778                                           |
| Solis Grid Time of Use Discharge battery current (Slot 5) | CURRENT        | AMPERE               | MEASUREMENT      | 43779                                           |
| Solis Grid Time of Use Discharge cut off voltage (Slot 5) | VOLTAGE        | VOLT                 | MEASUREMENT      | 43780                                           |
| Solis Grid Time of Use Discharge Start Hour (Slot 5)      |                | HOURS                | MEASUREMENT      | 43781                                           |
| Solis Grid Time of Use Discharge Start Minute (Slot 5)    |                | MINUTES              | MEASUREMENT      | 43782                                           |
| Solis Grid Time of Use Discharge End Hour (Slot 5)        |                | HOURS                | MEASUREMENT      | 43783                                           |
| Solis Grid Time of Use Discharge End Minute (Slot 5)      |                | MINUTES              | MEASUREMENT      | 43784                                           |
| Solis Grid Time of Use Discharge cut off SOC (Slot 6)     |                | %                    | MEASUREMENT      | 43785                                           |
| Solis Grid Time of Use Discharge battery current (Slot 6) | CURRENT        | AMPERE               | MEASUREMENT      | 43786                                           |
| Solis Grid Time of Use Discharge cut off voltage (Slot 6) | VOLTAGE        | VOLT                 | MEASUREMENT      | 43787                                           |
| Solis Grid Time of Use Discharge Start Hour (Slot 6)      |                | HOURS                | MEASUREMENT      | 43788                                           |
| Solis Grid Time of Use Discharge Start Minute (Slot 6)    |                | MINUTES              | MEASUREMENT      | 43789                                           |
| Solis Grid Time of Use Discharge End Hour (Slot 6)        |                | HOURS                | MEASUREMENT      | 43790                                           |
| Solis Grid Time of Use Discharge End Minute (Slot 6)      |                | MINUTES              | MEASUREMENT      | 43791                                           |
| Solis Generator charging switch                           |                |                      | MEASUREMENT      | 43815                                           |
| Solis Dispatch Active                                     |                |                      | MEASUREMENT      | 44100                                           |
| Solis Dispatch Failsafe Interval                          |                | MINUTES              | MEASUREMENT      | 44101                                           |
| Solis Dispatch Limit Switches                             |                |                      | MEASUREMENT      | 44102                                           |
| Solis Dispatch Import Limit                               | POWER          | WATT                 | MEASUREMENT      | 44103                                           |
| Solis Dispatch Export Limit                               | POWER          | WATT                 | MEASUREMENT      | 44104                                           |
| Solis Dispatch Control Mode                               |                |                      | MEASUREMENT      | 44105                                           |
| Solis Dispatch Power Target                               | POWER          | WATT                 | MEASUREMENT      | 44106, 44107                                    |
| Solis Dispatch Function Bits                              |                |                      | MEASUREMENT      | 44108                                           |
| Solis Dispatch SOC Lower Limit                            | BATTERY        | %                    | MEASUREMENT      | 44109                                           |
| Solis Dispatch SOC Upper Limit                            | BATTERY        | %                    | MEASUREMENT      | 44110                                           |
| Solis Dispatch Battery Reserve SOC                        | BATTERY        | %                    | MEASUREMENT      | 44111                                           |
| Solis Dispatch PV Limit Percentage                        |                | %                    | MEASUREMENT      | 44112                                           |
| Solis Remote Active Power Control Command                 |                |                      | MEASUREMENT      | 44280                                           |
| Solis Last Modbus Success                                 | TIMESTAMP      |                      |                  | 90006                                           |
| Solis Last Clock Adjustment                               | TIMESTAMP      |                      |                  | 90007, 33022, 33023, 33024, 33025, 33026, 33027 |

# Waveshare
This is only required if your values are higher than expected, if you aren't experiencing this, this should be disabled.

| register | Name                               | Default | Waveshare | Example                 |
|----------|------------------------------------|---------|-----------|-------------------------|
| 33142    | Solis Battery Current (BMS)        | 0.1     | 0.01      | Changes 30A to 3A       |
| 33161    | Total Battery Charge Energy        | 1       | 0.01      | Changes 100kwh to 1kwh  |
| 33163    | Today Battery Charge Energy        | 0.1     | 0.01      | Changes 100kwh to 10kwh |
| 33164    | Yesterday Battery Charge Energy    | 0.1     | 0.01      | Changes 100kwh to 10kwh |
| 33165    | Total Battery Discharge Energy     | 1       | 0.01      | Changes 100kwh to 1kwh  |
| 33167    | Today Battery Discharge Energy     | 0.1     | 0.01      | Changes 100kwh to 10kwh |
| 33168    | Yesterday Battery Discharge Energy | 0.1     | 0.01      | Changes 100kwh to 10kwh |

# String Inverter Sensors

| Name                                                     | Device Class   | Unit Of Measurement  | State Class      | Registers    |
|----------------------------------------------------------|----------------|----------------------|------------------|--------------|
| Product Model                                            |                |                      | MEASUREMENT      | 2999         |
| DSP Software Version                                     |                |                      | MEASUREMENT      | 3000         |
| HMI Major Version                                        |                |                      | MEASUREMENT      | 3001         |
| AC Output Type                                           |                |                      | MEASUREMENT      | 3002         |
| DC Input Type                                            |                |                      | MEASUREMENT      | 3003         |
| Active Power                                             | POWER          | WATT                 | MEASUREMENT      | 3004, 3005   |
| Total DC Output Power                                    | POWER          | WATT                 | MEASUREMENT      | 3006, 3007   |
| Total Energy                                             | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 3008, 3009   |
| Energy This Month                                        | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 3010, 3011   |
| Energy Last Month                                        | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 3012, 3013   |
| Energy Today                                             | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 3014         |
| Energy Yesterday                                         | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 3015         |
| Energy This Year                                         | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 3016, 3017   |
| Energy Last Year                                         | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 3018, 3019   |
| DC Power 1                                               | POWER          | WATT                 | MEASUREMENT      | 3021, 3022   |
| DC Voltage 1                                             | VOLTAGE        | VOLT                 | MEASUREMENT      | 3021         |
| DC Current 1                                             | CURRENT        | AMPERE               | MEASUREMENT      | 3022         |
| DC Power 2                                               | POWER          | WATT                 | MEASUREMENT      | 3023, 3024   |
| DC Voltage 2                                             | VOLTAGE        | VOLT                 | MEASUREMENT      | 3023         |
| DC Current 2                                             | CURRENT        | AMPERE               | MEASUREMENT      | 3024         |
| DC Power 3                                               | POWER          | WATT                 | MEASUREMENT      | 3025, 3026   |
| DC Voltage 3                                             | VOLTAGE        | VOLT                 | MEASUREMENT      | 3025         |
| DC Current 3                                             | CURRENT        | AMPERE               | MEASUREMENT      | 3026         |
| DC Power 4                                               | POWER          | WATT                 | MEASUREMENT      | 3027, 3028   |
| DC Voltage 4                                             | VOLTAGE        | VOLT                 | MEASUREMENT      | 3027         |
| DC Current 4                                             | CURRENT        | AMPERE               | MEASUREMENT      | 3028         |
| A Phase Voltage                                          | VOLTAGE        | VOLT                 | MEASUREMENT      | 3033         |
| B Phase Voltage                                          | VOLTAGE        | VOLT                 | MEASUREMENT      | 3034         |
| C Phase Voltage                                          | VOLTAGE        | VOLT                 | MEASUREMENT      | 3035         |
| A Phase Current                                          | CURRENT        | AMPERE               | MEASUREMENT      | 3036         |
| B Phase Current                                          | CURRENT        | AMPERE               | MEASUREMENT      | 3037         |
| C Phase Current                                          | CURRENT        | AMPERE               | MEASUREMENT      | 3038         |
| Working Mode                                             |                |                      | MEASUREMENT      | 3040         |
| Inverter Temperature                                     | TEMPERATURE    | CELSIUS              | MEASUREMENT      | 3041         |
| Grid Frequency                                           | FREQUENCY      | HERTZ                | MEASUREMENT      | 3042         |
| Inverter Status                                          |                |                      | MEASUREMENT      | 3043         |
| Limited active power adjustment rated power output value | POWER          | WATT                 | MEASUREMENT      | 3044, 3045   |
| Reactive power regulation rated power output value       | REACTIVE_POWER | VOLT_AMPERE_REACTIVE | MEASUREMENT      | 3046, 3047   |
| Actual Limited Active Power                              |                | %                    | MEASUREMENT      | 3049         |
| Actual Adjusted Power Factor                             |                | %                    | MEASUREMENT      | 3050         |
| Actual Power Factor Adjustment                           |                |                      | MEASUREMENT      | 3051         |
| Power Limitation Switch (89)                             |                |                      | MEASUREMENT      | 3089         |
| Shading MPPT Scan Enable                                 | VOLTAGE        | VOLT                 | MEASUREMENT      | 3179         |
| Shading MPPT Scan Time Interval                          |                | MINUTES              | MEASUREMENT      | 3180         |
| Meter AC Voltage A                                       | VOLTAGE        | VOLT                 | MEASUREMENT      | 3250         |
| Meter AC Current A                                       | CURRENT        | AMPERE               | MEASUREMENT      | 3251         |
| Meter AC Voltage B                                       | VOLTAGE        | VOLT                 | MEASUREMENT      | 3252         |
| Meter AC Current B                                       | CURRENT        | AMPERE               | MEASUREMENT      | 3253         |
| Meter AC Voltage C                                       | VOLTAGE        | VOLT                 | MEASUREMENT      | 3254         |
| Meter AC Current C                                       | CURRENT        | AMPERE               | MEASUREMENT      | 3255         |
| Meter AC Active Power A                                  | POWER          | KILO_WATT            | MEASUREMENT      | 3256, 3257   |
| Meter AC Active Power B                                  | POWER          | KILO_WATT            | MEASUREMENT      | 3258, 3259   |
| Meter AC Active Power C                                  | POWER          | KILO_WATT            | MEASUREMENT      | 3260, 3261   |
| Meter AC Active Power Total                              | POWER          | KILO_WATT            | MEASUREMENT      | 3262, 3263   |
| Meter Power Factor                                       | POWER_FACTOR   |                      | MEASUREMENT      | 3280         |
| Meter Grid Frequency                                     | FREQUENCY      | HERTZ                | MEASUREMENT      | 3281         |
| Meter Grid Import Total Energy                           | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 3282, 3283   |
| Meter Grid Export Total Energy                           | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 3284, 3285   |
| EPM Model No                                             |                |                      |                  | 36013        |
| Inverter EPM Firmware Version                            |                |                      |                  | 36014        |
| Clock (Hours)                                            |                | HOURS                | MEASUREMENT      | 36022        |
| Clock (Minutes)                                          |                | MINUTES              | MEASUREMENT      | 36023        |
| Clock (Seconds)                                          |                | SECONDS              | MEASUREMENT      | 36024        |
| Total Load power                                         | POWER          | WATT                 | MEASUREMENT      | 36028, 36029 |
| Total Generation Energy                                  | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 36050, 36051 |
| Load Total Consumption Energy                            | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 36052, 36053 |
| Grid Import Total Active Energy                          | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 36054, 36055 |
| Grid Export Total Active Energy                          | ENERGY         | KILO_WATT_HOUR       | TOTAL_INCREASING | 36056, 36057 |

# Solar Inverter Modes in Solis Inverters

## 1. Feed-in Priority Mode
- **Solis Implementation**: In this mode, the system prioritizes exporting solar power to the grid. The battery remains inactive unless "Time Charging" is enabled and configured.
- This mode is ideal for users with large PV systems relative to their consumption and battery capacity.
- [Source](https://usservice.solisinverters.com/support/solutions/articles/73000558755-12-of-20-energy-storage-operating-modes-feed-in-priority)

## 2. Off-Grid Mode
- **Solis Implementation**: Designed for installations without grid power.
- The inverter supplies power to backup loads from PV and the battery, depending on availability.
- [Source](https://usservice.solisinverters.com/support/solutions/articles/73000560490-energy-storage-operating-modes)

## 3. Reserve Battery Mode
- **Solis Implementation**: Known as "Backup" mode.
- The system reserves a portion of the battery's charge for backup purposes during grid outages.
- The "Backup SOC" setting determines the minimum state of charge maintained for emergencies.
- [Source](https://usservice.solisinverters.com/support/solutions/articles/73000560490-energy-storage-operating-modes)

## 4. Self-Use Mode
- **Solis Implementation**: The inverter stores excess PV power in the battery for later use, such as during evening hours when grid power may be more expensive.
- Supports energy arbitrage or peak-rate shaving.
- [Source](https://usservice.solisinverters.com/support/solutions/articles/73000558744-11-of-20-energy-storage-operating-modes-self-use)

## 5. Time-of-Use (TOU) Mode
- **Solis Implementation**: Known as "Time Charging."
- Users can set specific charge and discharge periods, allowing the battery to charge during times of low grid rates or high solar production and discharge during peak rate periods.
- [Source](https://usservice.solisinverters.com/support/solutions/articles/73000560490-energy-storage-operating-modes)

## 6. Peak Shaving Mode
- **Solis Implementation**: While not explicitly named, the combination of "Self-Use" and "Time Charging" modes can achieve peak shaving.
- The battery discharges during peak demand times to reduce grid reliance and associated costs.
- [Source](https://usservice.solisinverters.com/support/solutions/articles/73000560490-energy-storage-operating-modes)

For detailed configuration and to ensure optimal performance tailored to your needs, consult the Solis inverter manual or contact their technical support.
