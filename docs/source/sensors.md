---
myst:
  enable_extensions: [ "colon_fence" ]
---

The following sensors are provided in the integration.

# Input Control Sensors
| Name                                                | Device Class | Unit Of Measurement | State Class | Registers |
|-----------------------------------------------------|--------------|---------------------|-------------|-----------|
| Solis Time-Charging Charge Current                  | CURRENT      | AMPERE              |             | 43141     |
| Solis Time-Charging Discharge Current               | CURRENT      | AMPERE              |             | 43142     |
| Solis Backup SOC                                    |              | PERCENTAGE          |             | 43024     |
| Solis Battery Force-charge Power Limitation         |              | WATT                |             | 43027     |
| Solis Overcharge SOC                                |              | PERCENTAGE          |             | 43010     |
| Solis Overdischarge SOC                             |              | PERCENTAGE          |             | 43011     |
| Solis Force Charge SOC                              |              | PERCENTAGE          |             | 43018     |

# Switch Control Sensors
| Name                                                                    | Register | Bit Position | Note                                                                                                                                                                                                                                                                                                          |
|-------------------------------------------------------------------------|----------|--------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Solis Self-Use Mode                                                     | 43110    | 0            |
| Solis Time Of Use Mode                                                  | 43110    | 1            |
| Solis OFF-Grid Mode                                                     | 43110    | 2            |
| Solis Battery Wakeup Switch                                             | 43110    | 3            |
| Solis Reserve Battery Mode                                              | 43110    | 4            |
| Solis Allow Grid To Charge The Battery                                  | 43110    | 5            |
| Solis Feed In Priority Mode                                             | 43110    | 6            |
| Solis Batt OVC                                                          | 43110    | 7            |
| Solis Battery Forcecharge Peakshaving                                   | 43110    | 8            |
| Solis Battery current correction                                        | 43110    | 9            |
| Solis Battery healing mode                                              | 43110    | 10           |
| Solis Peak-shaving mode                                                 | 43110    | 11           |
| Solis Generator connection position                                     | 43365    | 0            |
| Solis With Generator                                                    | 43365    | 1            |
| Solis Generator enable signal                                           | 43365    | 2            |
| Solis AC Coupling Position (off = GEN port, on = Backup port)           | 43365    | 3            |
| Solis Generator access location                                         | 43365    | 4            | Generator access location, used in combination with BIT00,  BIT04 = 0, BIT00 = 0, generator port (Smart port) (supported by models with Smart port), BIT04 = 0, BIT00 = 1, grid side, BIT04 = 1, BIT00 = 0, backup side currently only supports models without generator port), BIT04 = 1, BIT00 = 1, invalid |
| Solis Generator charging period 1 switch                                | 43815    | 0            |
| Solis Generator charging period 2 switch                                | 43815    | 1            |
| Solis Generator charging period 3 switch                                | 43815    | 2            |
| Solis Generator charging period 4 switch                                | 43815    | 3            |
| Solis Generator charging period 5 switch                                | 43815    | 4            |
| Solis Generator charging period 6 switch                                | 43815    | 5            |
| Solis Generator Input Mode (off = Manual, on = Auto)                    | 43340    | 0            |
| Solis Generator Charge Enable                                           | 43340    | 1            |
| Solis Dual Backup Enable                                                | 43483    | 0            | It cannot be enabled at the same time as the parallel function (43391);                                                                                                                                                                                                                                       |
| Solis AC Coupling Enable                                                | 43483    | 1            | It cannot be enabled at the same time as the With Generator (register 43365BIT01), otherwise it will be invalid, that is, you need to turn off one before turning on the other                                                                                                                                |
| Solis Smart load port grid-connected forced output                      | 43483    | 2            | Smart Load ongrid always on                                                                                                                                                                                                                                                                                   |
| Solis Allow export switch under self-generation and self-use            | 43483    | 3            |
| Solis Backup2Load manual/automatic switch (off = Manual, on = Automatic | 43483    | 4            |
| Solis Backup2Load manual enable                                         | 43483    | 5            |
| Solis Smart load port stops output when off-grid                        | 43483    | 6            |
| Solis Grid Peak-shaving power enable                                    | 43483    | 7            | When disabled, the battery charging power is notlimited according to the power situation on the public grid side; when enabled, the power taken from the public grid side exceeds the set value of 43488, and the battery charging power is limited;                                                          |

# Time Control Sensors
| Name                                         | Register |
|----------------------------------------------|----------|
| Solis Time-Charging Charge Start (Slot 1)    | 43143    |
| Solis Time-Charging Charge End (Slot 1)      | 43145    |
| Solis Time-Charging Discharge Start (Slot 1) | 43147    |
| Solis Time-Charging Discharge End (Slot 1)   | 43149    |
| Solis Time-Charging Charge Start (Slot 2)    | 43153    |
| Solis Time-Charging Charge End (Slot 2)      | 43155    |
| Solis Time-Charging Discharge Start (Slot 2) | 43157    |
| Solis Time-Charging Discharge End (Slot 2)   | 43159    |
| Solis Time-Charging Charge Start (Slot 3)    | 43163    |
| Solis Time-Charging Charge End (Slot 3)      | 43165    |
| Solis Time-Charging Discharge Start (Slot 3) | 43167    |
| Solis Time-Charging Discharge End (Slot 3)   | 43169    |
| Solis Time-Charging Charge Start (Slot 4)    | 43173    |
| Solis Time-Charging Charge End (Slot 4)      | 43175    |
| Solis Time-Charging Discharge Start (Slot 4) | 43177    |
| Solis Time-Charging Discharge End (Slot 4)   | 43179    |
| Solis Time-Charging Charge Start (Slot 5)    | 43183    |
| Solis Time-Charging Charge End (Slot 5)      | 43185    |
| Solis Time-Charging Discharge Start (Slot 5) | 43187    |
| Solis Time-Charging Discharge End (Slot 5)   | 43189    |

# Sensors
| Name                                                      | Device Class   | Unit Of Measurement        | State Class      | Registers                              |
|-----------------------------------------------------------|----------------|----------------------------|------------------|----------------------------------------|
| Solis Model No                                            |                |                            |                  | 33000                                  |
| Solis DSP Version                                         |                |                            |                  | 33001                                  |
| Solis HMI Version                                         |                |                            |                  | 33002                                  |
| Solis Protocol Version                                    |                |                            |                  | 33003                                  |
| Solis Serial Number                                       |                |                            |                  | 33004 - 33019                          |
| Solis PV Total Energy Generation                          | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33029, 33030                           |
| Solis PV Current Month Energy Generation                  | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33031, 33032                           |
| Solis PV Last Month Energy Generation                     | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33033, 33034                           |
| Solis PV Today Energy Generation                          | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33035                                  |
| Solis PV Yesterday Energy Generation                      | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33036                                  |
| Solis PV This Year Energy Generation                      | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33037, 33038                           |
| Solis PV Last Year Energy Generation                      | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33039, 33040                           |
| Solis PV Voltage 1                                        | VOLTAGE        | VOLT                       | MEASUREMENT      | 33049                                  |
| Solis PV Current 1                                        | CURRENT        | AMPERE                     | MEASUREMENT      | 33050                                  |
| Solis PV Voltage 2                                        | VOLTAGE        | VOLT                       | MEASUREMENT      | 33051                                  |
| Solis PV Current 2                                        | CURRENT        | AMPERE                     | MEASUREMENT      | 33052                                  |
| Solis PV Voltage 3                                        | VOLTAGE        | VOLT                       | MEASUREMENT      | 33053                                  |
| Solis PV Current 3                                        | CURRENT        | AMPERE                     | MEASUREMENT      | 33054                                  |
| Solis PV Voltage 4                                        | VOLTAGE        | VOLT                       | MEASUREMENT      | 33055                                  |
| Solis PV Current 4                                        | CURRENT        | AMPERE                     | MEASUREMENT      | 33056                                  |
| Solis Total PV Power                                      | POWER          | WATT                       | MEASUREMENT      | 33057, 33058                           |
| Solis PV Bus Half Voltage                                 | VOLTAGE        | VOLT                       | MEASUREMENT      | 33072                                  |
| Solis A Phase Voltage                                     | VOLTAGE        | VOLT                       | MEASUREMENT      | 33073                                  |
| Solis B Phase Voltage                                     | VOLTAGE        | VOLT                       | MEASUREMENT      | 33074                                  |
| Solis C Phase Voltage                                     | VOLTAGE        | VOLT                       | MEASUREMENT      | 33075                                  |
| Solis A Phase Current                                     | CURRENT        | AMPERE                     | MEASUREMENT      | 33076                                  |
| Solis B Phase Current                                     | CURRENT        | AMPERE                     | MEASUREMENT      | 33077                                  |
| Solis C Phase Current                                     | CURRENT        | AMPERE                     | MEASUREMENT      | 33078                                  |
| Solis Active Power                                        | POWER          | WATT                       | MEASUREMENT      | 33079, 33080                           |
| Solis Reactive Power                                      | REACTIVE_POWER | POWER_VOLT_AMPERE_REACTIVE | MEASUREMENT      | 33081, 33082                           |
| Solis Apparent Power                                      | APPARENT_POWER | VOLT_AMPERE                | MEASUREMENT      | 33083, 33084                           |
| Solis Temperature                                         | TEMPERATURE    | CELSIUS                    | MEASUREMENT      | 33093                                  |
| Solis Grid Frequency                                      | FREQUENCY      | HERTZ                      | MEASUREMENT      | 33094                                  |
| Solis Status                                              |                |                            | MEASUREMENT      | 33095                                  |
| Solis Lead-acid Battery Temperature                       | TEMPERATURE    | CELSIUS                    | MEASUREMENT      | 33096                                  |
| Solis Storage Control Switching Value                     |                |                            | MEASUREMENT      | 33132                                  |
| Solis Battery Voltage                                     | VOLTAGE        | VOLT                       | MEASUREMENT      | 33133                                  |
| Solis Battery Current                                     | CURRENT        | AMPERE                     | MEASUREMENT      | 33134                                  |
| Solis Battery Current Direction                           |                |                            | MEASUREMENT      | 33135                                  |
| Solis LLC Bus Voltage                                     | VOLTAGE        | VOLT                       | MEASUREMENT      | 33136                                  |
| Solis Backup AC Voltage Phase A                           | VOLTAGE        | VOLT                       | MEASUREMENT      | 33137                                  |
| Solis Backup AC Current Phase A                           | CURRENT        | AMPERE                     | MEASUREMENT      | 33138                                  |
| Solis Battery SOC                                         | BATTERY        | PERCENTAGE                 | MEASUREMENT      | 33139                                  |
| Solis Battery SOH                                         |                | PERCENTAGE                 | MEASUREMENT      | 33140                                  |
| Solis Battery Voltage (BMS)                               | VOLTAGE        | VOLT                       | MEASUREMENT      | 33141                                  |
| Solis Battery Current (BMS)                               | CURRENT        | AMPERE                     | MEASUREMENT      | 33142                                  |
| Solis Battery Charge Current Limitation (BMS)             | CURRENT        | AMPERE                     | MEASUREMENT      | 33143                                  |
| Solis Battery Discharge Current Limitation (BMS)          | CURRENT        | AMPERE                     | MEASUREMENT      | 33144                                  |
| Solis Battery Fault Status 1 (BMS)                        |                |                            | MEASUREMENT      | 33145                                  |
| Solis Battery Fault Status 2 (BMS)                        |                |                            | MEASUREMENT      | 33146                                  |
| Solis Household load power                                | POWER          | WATT                       | MEASUREMENT      | 33147                                  |
| Solis Backup Load power                                   | POWER          | WATT                       | MEASUREMENT      | 33148                                  |
| Solis Battery Power                                       | POWER          | WATT                       | MEASUREMENT      | 33149, 33150                           |
| Solis AC Grid Port Power                                  | POWER          | WATT                       | MEASUREMENT      | 33151, 33152                           |
| Solis Total Battery Charge Energy                         | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33161, 33162                           |
| Solis Today Battery Charge Energy                         | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33163                                  |
| Solis Yesterday Battery Charge Energy                     | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33164                                  |
| Solis Total Battery Discharge Energy                      | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33165, 33166                           |
| Solis Today Battery Discharge Energy                      | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33167                                  |
| Solis Yesterday Battery Discharge Energy                  | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33168                                  |
| Solis Total Energy Imported From Grid                     | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33169, 33170                           |
| Solis Today Energy Imported From Grid                     | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33171                                  |
| Solis Yesterday Energy Imported From Grid                 | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33172                                  |
| Solis Total Energy Fed Into Grid                          | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33173, 33174                           |
| Solis Today Energy Fed Into Grid                          | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33175                                  |
| Solis Yesterday Energy Fed Into Grid                      | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33176                                  |
| Solis Total Energy Consumption                            | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33177, 33178                           |
| Solis Today Energy Consumption                            | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33179                                  |
| Solis Yesterday Energy Consumption                        | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33180                                  |
| Solis Meter AC Voltage A                                  | VOLTAGE        | VOLT                       | MEASUREMENT      | 33251                                  |
| Solis Meter AC Current A                                  | CURRENT        | AMPERE                     | MEASUREMENT      | 33252                                  |
| Solis Meter AC Voltage B                                  | VOLTAGE        | VOLT                       | MEASUREMENT      | 33253                                  |
| Solis Meter AC Current B                                  | CURRENT        | AMPERE                     | MEASUREMENT      | 33254                                  |
| Solis Meter AC Voltage C                                  | VOLTAGE        | VOLT                       | MEASUREMENT      | 33255                                  |
| Solis Meter AC Current C                                  | CURRENT        | AMPERE                     | MEASUREMENT      | 33256                                  |
| Solis Meter Active Power A                                | POWER          | WATT                       | MEASUREMENT      | 33257, 33258                           |
| Solis Meter Active Power B                                | POWER          | WATT                       | MEASUREMENT      | 33259, 33260                           |
| Solis Meter Active Power C                                | POWER          | WATT                       | MEASUREMENT      | 33261, 33262                           |
| Solis Meter Total Active Power                            | POWER          | WATT                       | MEASUREMENT      | 33263, 33264                           |
| Solis Household Load Total Energy                         | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33580, 33581                           |
| Solis Household Load Year Energy                          | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33582, 33583                           |
| Solis Household Load Month Energy                         | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33584, 33585                           |
| Solis Household Load Today Energy                         | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33586                                  |
| Solis Backup Load Total Energy                            | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33590, 33591                           |
| Solis Backup Load Year Energy                             | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33592, 33593                           |
| Solis Backup Load Month Energy                            | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33594, 33595                           |
| Solis Backup Load Today Energy                            | ENERGY         | KILO_WATT_HOUR             | TOTAL_INCREASING | 33596                                  |
| Solis Overcharge SOC                                      |                | PERCENTAGE                 | MEASUREMENT      | 43010                                  |
| Solis Overdischarge SOC                                   |                | PERCENTAGE                 | MEASUREMENT      | 43011                                  |
| Solis Force Charge SOC                                    |                | PERCENTAGE                 | MEASUREMENT      | 43018                                  |
| Solis Backup SOC                                          |                | PERCENTAGE                 | MEASUREMENT      | 43024                                  |
| Solis Battery Force-charge Power Limitation               | POWER          | WATT                       | MEASUREMENT      | 43027                                  |
| Solis Battery Force Charge Source                         |                |                            | MEASUREMENT      | 43028                                  |
| Solis Off-Grid Overdischarge SOC                          |                | PERCENTAGE                 | MEASUREMENT      | 43137                                  |
| Solis Time-Charging Charge Current                        | CURRENT        | AMPERE                     | MEASUREMENT      | 43141                                  |
| Solis Time-Charging Discharge Current                     | CURRENT        | AMPERE                     | MEASUREMENT      | 43142                                  |
| Solis Time-Charging Charge Start Hour (Slot 1)            |                | HOURS                      | MEASUREMENT      | 43143                                  |
| Solis Time-Charging Charge Start Minute (Slot 1)          |                | MINUTES                    | MEASUREMENT      | 43144                                  |
| Solis Time-Charging Charge End Hour (Slot 1)              |                | HOURS                      | MEASUREMENT      | 43145                                  |
| Solis Time-Charging Charge End Minute (Slot 1)            |                | MINUTES                    | MEASUREMENT      | 43146                                  |
| Solis Time-Charging Discharge Start Hour (Slot 1)         |                | HOURS                      | MEASUREMENT      | 43147                                  |
| Solis Time-Charging Discharge Start Minute (Slot 1)       |                | MINUTES                    | MEASUREMENT      | 43148                                  |
| Solis Time-Charging Discharge End Hour (Slot 1)           |                | HOURS                      | MEASUREMENT      | 43149                                  |
| Solis Time-Charging Discharge End Minute (Slot 1)         |                | MINUTES                    | MEASUREMENT      | 43150                                  |
| Solis Time-Charging Charge Start Hour (Slot 2)            |                | HOURS                      | MEASUREMENT      | 43153                                  |
| Solis Time-Charging Charge Start Minute (Slot 2)          |                | MINUTES                    | MEASUREMENT      | 43154                                  |
| Solis Time-Charging Charge End Hour (Slot 2)              |                | HOURS                      | MEASUREMENT      | 43155                                  |
| Solis Time-Charging Charge End Minute (Slot 2)            |                | MINUTES                    | MEASUREMENT      | 43156                                  |
| Solis Time-Charging Discharge Start Hour (Slot 2)         |                | HOURS                      | MEASUREMENT      | 43157                                  |
| Solis Time-Charging Discharge Start Minute (Slot 2)       |                | MINUTES                    | MEASUREMENT      | 43158                                  |
| Solis Time-Charging Discharge End Hour (Slot 2)           |                | HOURS                      | MEASUREMENT      | 43159                                  |
| Solis Time-Charging Discharge End Minute (Slot 2)         |                | MINUTES                    | MEASUREMENT      | 43160                                  |
| Solis Time-Charging Charge Start Hour (Slot 3)            |                | HOURS                      | MEASUREMENT      | 43163                                  |
| Solis Time-Charging Charge Start Minute (Slot 3)          |                | MINUTES                    | MEASUREMENT      | 43164                                  |
| Solis Time-Charging Charge End Hour (Slot 3)              |                | HOURS                      | MEASUREMENT      | 43165                                  |
| Solis Time-Charging Charge End Minute (Slot 3)            |                | MINUTES                    | MEASUREMENT      | 43166                                  |
| Solis Time-Charging Discharge Start Hour (Slot 3)         |                | HOURS                      | MEASUREMENT      | 43167                                  |
| Solis Time-Charging Discharge Start Minute (Slot 3)       |                | MINUTES                    | MEASUREMENT      | 43168                                  |
| Solis Time-Charging Discharge End Hour (Slot 3)           |                | HOURS                      | MEASUREMENT      | 43169                                  |
| Solis Time-Charging Discharge End Minute (Slot 3)         |                | MINUTES                    | MEASUREMENT      | 43170                                  |
| Solis Time-Charging Charge Start Hour (Slot 4)            |                | HOURS                      | MEASUREMENT      | 43173                                  |
| Solis Time-Charging Charge Start Minute (Slot 4)          |                | MINUTES                    | MEASUREMENT      | 43174                                  |
| Solis Time-Charging Charge End Hour (Slot 4)              |                | HOURS                      | MEASUREMENT      | 43175                                  |
| Solis Time-Charging Charge End Minute (Slot 4)            |                | MINUTES                    | MEASUREMENT      | 43176                                  |
| Solis Time-Charging Discharge Start Hour (Slot 4)         |                | HOURS                      | MEASUREMENT      | 43177                                  |
| Solis Time-Charging Discharge Start Minute (Slot 4)       |                | MINUTES                    | MEASUREMENT      | 43178                                  |
| Solis Time-Charging Discharge End Hour (Slot 4)           |                | HOURS                      | MEASUREMENT      | 43179                                  |
| Solis Time-Charging Discharge End Minute (Slot 4)         |                | MINUTES                    | MEASUREMENT      | 43180                                  |
| Solis Time-Charging Charge Start Hour (Slot 5)            |                | HOURS                      | MEASUREMENT      | 43183                                  |
| Solis Time-Charging Charge Start Minute (Slot 5)          |                | MINUTES                    | MEASUREMENT      | 43184                                  |
| Solis Time-Charging Charge End Hour (Slot 5)              |                | HOURS                      | MEASUREMENT      | 43185                                  |
| Solis Time-Charging Charge End Minute (Slot 5)            |                | MINUTES                    | MEASUREMENT      | 43186                                  |
| Solis Time-Charging Discharge Start Hour (Slot 5)         |                | HOURS                      | MEASUREMENT      | 43187                                  |
| Solis Time-Charging Discharge Start Minute (Slot 5)       |                | MINUTES                    | MEASUREMENT      | 43188                                  |
| Solis Time-Charging Discharge End Hour (Slot 5)           |                | HOURS                      | MEASUREMENT      | 43189                                  |
| Solis Time-Charging Discharge End Minute (Slot 5)         |                | MINUTES                    | MEASUREMENT      | 43190                                  |
| Solis Forced Start of Generator                           |                |                            | MEASUREMENT      | 43363                                  |
| Solis Rated Input Power of Generator                      | POWER          |                            | MEASUREMENT      | 43364                                  |
| Solis Generator Setting Switch                            |                |                            | MEASUREMENT      | 43365                                  |
| Solis Generator Forced Stop of Generator                  |                |                            | MEASUREMENT      | 43366                                  |
| Solis Maximum Allowable Percentage of Generator           |                | PERCENTAGE                 | MEASUREMENT      | 43367                                  |
| Solis Generator Target Power                              | POWER          |                            | MEASUREMENT      | 43368                                  |
| Solis Generator Charging Power                            | POWER          |                            | MEASUREMENT      | 43369                                  |
| Solis Time of Use V2 Switch                               |                |                            |                  | 43707                                  |
| Solis Grid Time of Use Charge cut off SOC (Slot 1)        |                | PERCENTAGE                 | Measurement      | 43708                                  |
| Solis Grid Time of Use Charge battery current (Slot 1)    | CURRENT        | AMPERE                     | Measurement      | 43709                                  |
| Solis Grid Time of Use Charge cut off voltage (Slot 1)    | VOLTAGE        | VOLT                       | Measurement      | 43710                                  |
| Solis Grid Time of Use Charge Start Hour (Slot 1)         |                | HOURS                      | Measurement      | 43711                                  |
| Solis Grid Time of Use Charge Start Minute (Slot 1)       |                | MINUTES                    | Measurement      | 43712                                  |
| Solis Grid Time of Use Charge End Hour (Slot 1)           |                | HOURS                      | Measurement      | 43713                                  |
| Solis Grid Time of Use Charge End Minute (Slot 1)         |                | MINUTES                    | Measurement      | 43714                                  |
| Solis Grid Time of Use Charge cut off SOC (Slot 2)        |                | PERCENTAGE                 | Measurement      | 43715                                  |
| Solis Grid Time of Use Charge battery current (Slot 2)    | CURRENT        | AMPERE                     | Measurement      | 43716                                  |
| Solis Grid Time of Use Charge cut off voltage (Slot 2)    | VOLTAGE        | VOLT                       | Measurement      | 43717                                  |
| Solis Grid Time of Use Charge Start Hour (Slot 2)         |                | HOURS                      | Measurement      | 43718                                  |
| Solis Grid Time of Use Charge Start Minute (Slot 2)       |                | MINUTES                    | Measurement      | 43719                                  |
| Solis Grid Time of Use Charge End Hour (Slot 2)           |                | HOURS                      | Measurement      | 43720                                  |
| Solis Grid Time of Use Charge End Minute (Slot 2)         |                | MINUTES                    | Measurement      | 43721                                  |
| Solis Grid Time of Use Charge cut off SOC (Slot 3)        |                | PERCENTAGE                 | Measurement      | 43722                                  |
| Solis Grid Time of Use Charge battery current (Slot 3)    | CURRENT        | AMPERE                     | Measurement      | 43723                                  |
| Solis Grid Time of Use Charge cut off voltage (Slot 3)    | VOLTAGE        | VOLT                       | Measurement      | 43724                                  |
| Solis Grid Time of Use Charge Start Hour (Slot 3)         |                | HOURS                      | Measurement      | 43725                                  |
| Solis Grid Time of Use Charge Start Minute (Slot 3)       |                | MINUTES                    | Measurement      | 43726                                  |
| Solis Grid Time of Use Charge End Hour (Slot 3)           |                | HOURS                      | Measurement      | 43727                                  |
| Solis Grid Time of Use Charge End Minute (Slot 3)         |                | MINUTES                    | Measurement      | 43728                                  |
| Solis Grid Time of Use Charge cut off SOC (Slot 4)        |                | PERCENTAGE                 | Measurement      | 43729                                  |
| Solis Grid Time of Use Charge battery current (Slot 4)    | CURRENT        | AMPERE                     | Measurement      | 43730                                  |
| Solis Grid Time of Use Charge cut off voltage (Slot 4)    | VOLTAGE        | VOLT                       | Measurement      | 43731                                  |
| Solis Grid Time of Use Charge Start Hour (Slot 4)         |                | HOURS                      | Measurement      | 43732                                  |
| Solis Grid Time of Use Charge Start Minute (Slot 4)       |                | MINUTES                    | Measurement      | 43733                                  |
| Solis Grid Time of Use Charge End Hour (Slot 4)           |                | HOURS                      | Measurement      | 43734                                  |
| Solis Grid Time of Use Charge End Minute (Slot 4)         |                | MINUTES                    | Measurement      | 43735                                  |
| Solis Grid Time of Use Charge cut off SOC (Slot 5)        |                | PERCENTAGE                 | Measurement      | 43736                                  |
| Solis Grid Time of Use Charge battery current (Slot 5)    | CURRENT        | AMPERE                     | Measurement      | 43737                                  |
| Solis Grid Time of Use Charge cut off voltage (Slot 5)    | VOLTAGE        | VOLT                       | Measurement      | 43738                                  |
| Solis Grid Time of Use Charge Start Hour (Slot 5)         |                | HOURS                      | Measurement      | 43739                                  |
| Solis Grid Time of Use Charge Start Minute (Slot 5)       |                | MINUTES                    | Measurement      | 43740                                  |
| Solis Grid Time of Use Charge End Hour (Slot 5)           |                | HOURS                      | Measurement      | 43741                                  |
| Solis Grid Time of Use Charge End Minute (Slot 5)         |                | MINUTES                    | Measurement      | 43742                                  |
| Solis Grid Time of Use Charge cut off SOC (Slot 6)        |                | PERCENTAGE                 | Measurement      | 43743                                  |
| Solis Grid Time of Use Charge battery current (Slot 6)    | CURRENT        | AMPERE                     | Measurement      | 43744                                  |
| Solis Grid Time of Use Charge cut off voltage (Slot 6)    | VOLTAGE        | VOLT                       | Measurement      | 43745                                  |
| Solis Grid Time of Use Charge Start Hour (Slot 6)         |                | HOURS                      | Measurement      | 43746                                  |
| Solis Grid Time of Use Charge Start Minute (Slot 6)       |                | MINUTES                    | Measurement      | 43747                                  |
| Solis Grid Time of Use Charge End Hour (Slot 6)           |                | HOURS                      | Measurement      | 43748                                  |
| Solis Grid Time of Use Charge End Minute (Slot 6)         |                | MINUTES                    | Measurement      | 43749                                  |
| Solis Grid Time of Use Discharge cut off SOC (Slot 1)     |                | PERCENTAGE                 | Measurement      | 43750                                  |
| Solis Grid Time of Use Discharge battery current (Slot 1) | CURRENT        | AMPERE                     | Measurement      | 43751                                  |
| Solis Grid Time of Use Discharge cut off voltage (Slot 1) | VOLTAGE        | VOLT                       | Measurement      | 43752                                  |
| Solis Grid Time of Use Discharge Start Hour (Slot 1)      |                | HOURS                      | Measurement      | 43753                                  |
| Solis Grid Time of Use Discharge Start Minute (Slot 1)    |                | MINUTES                    | Measurement      | 43754                                  |
| Solis Grid Time of Use Discharge End Hour (Slot 1)        |                | HOURS                      | Measurement      | 43755                                  |
| Solis Grid Time of Use Discharge End Minute (Slot 1)      |                | MINUTES                    | Measurement      | 43756                                  |
| Solis Grid Time of Use Discharge cut off SOC (Slot 2)     |                | PERCENTAGE                 | Measurement      | 43757                                  |
| Solis Grid Time of Use Discharge battery current (Slot 2) | CURRENT        | AMPERE                     | Measurement      | 43758                                  |
| Solis Grid Time of Use Discharge cut off voltage (Slot 2) | VOLTAGE        | VOLT                       | Measurement      | 43759                                  |
| Solis Grid Time of Use Discharge Start Hour (Slot 2)      |                | HOURS                      | Measurement      | 43760                                  |
| Solis Grid Time of Use Discharge Start Minute (Slot 2)    |                | MINUTES                    | Measurement      | 43761                                  |
| Solis Grid Time of Use Discharge End Hour (Slot 2)        |                | HOURS                      | Measurement      | 43762                                  |
| Solis Grid Time of Use Discharge End Minute (Slot 2)      |                | MINUTES                    | Measurement      | 43763                                  |
| Solis Grid Time of Use Discharge cut off SOC (Slot 3)     |                | PERCENTAGE                 | Measurement      | 43764                                  |
| Solis Grid Time of Use Discharge battery current (Slot 3) | CURRENT        | AMPERE                     | Measurement      | 43765                                  |
| Solis Grid Time of Use Discharge cut off voltage (Slot 3) | VOLTAGE        | VOLT                       | Measurement      | 43766                                  |
| Solis Grid Time of Use Discharge Start Hour (Slot 3)      |                | HOURS                      | Measurement      | 43767                                  |
| Solis Grid Time of Use Discharge Start Minute (Slot 3)    |                | MINUTES                    | Measurement      | 43768                                  |
| Solis Grid Time of Use Discharge End Hour (Slot 3)        |                | HOURS                      | Measurement      | 43769                                  |
| Solis Grid Time of Use Discharge End Minute (Slot 3)      |                | MINUTES                    | Measurement      | 43770                                  |
| Solis Grid Time of Use Discharge cut off SOC (Slot 4)     |                | PERCENTAGE                 | Measurement      | 43771                                  |
| Solis Grid Time of Use Discharge battery current (Slot 4) | CURRENT        | AMPERE                     | Measurement      | 43772                                  |
| Solis Grid Time of Use Discharge cut off voltage (Slot 4) | VOLTAGE        | VOLT                       | Measurement      | 43773                                  |
| Solis Grid Time of Use Discharge Start Hour (Slot 4)      |                | HOURS                      | Measurement      | 43774                                  |
| Solis Grid Time of Use Discharge Start Minute (Slot 4)    |                | MINUTES                    | Measurement      | 43775                                  |
| Solis Grid Time of Use Discharge End Hour (Slot 4)        |                | HOURS                      | Measurement      | 43776                                  |
| Solis Grid Time of Use Discharge End Minute (Slot 4)      |                | MINUTES                    | Measurement      | 43777                                  |
| Solis Grid Time of Use Discharge cut off SOC (Slot 5)     |                | PERCENTAGE                 | Measurement      | 43778                                  |
| Solis Grid Time of Use Discharge battery current (Slot 5) | CURRENT        | AMPERE                     | Measurement      | 43779                                  |
| Solis Grid Time of Use Discharge cut off voltage (Slot 5) | VOLTAGE        | VOLT                       | Measurement      | 43780                                  |
| Solis Grid Time of Use Discharge Start Hour (Slot 5)      |                | HOURS                      | Measurement      | 43781                                  |
| Solis Grid Time of Use Discharge Start Minute (Slot 5)    |                | MINUTES                    | Measurement      | 43782                                  |
| Solis Grid Time of Use Discharge End Hour (Slot 5)        |                | HOURS                      | Measurement      | 43783                                  |
| Solis Grid Time of Use Discharge End Minute (Slot 5)      |                | MINUTES                    | Measurement      | 43784                                  |
| Solis Grid Time of Use Discharge cut off SOC (Slot 6)     |                | PERCENTAGE                 | Measurement      | 43785                                  |
| Solis Grid Time of Use Discharge battery current (Slot 6) | CURRENT        | AMPERE                     | Measurement      | 43786                                  |
| Solis Grid Time of Use Discharge cut off voltage (Slot 6) | VOLTAGE        | VOLT                       | Measurement      | 43787                                  |
| Solis Grid Time of Use Discharge Start Hour (Slot 6)      |                | HOURS                      | Measurement      | 43788                                  |
| Solis Grid Time of Use Discharge Start Minute (Slot 6)    |                | MINUTES                    | Measurement      | 43789                                  |
| Solis Grid Time of Use Discharge End Hour (Slot 6)        |                | HOURS                      | Measurement      | 43790                                  |
| Solis Grid Time of Use Discharge End Minute (Slot 6)      |                | MINUTES                    | Measurement      | 43791                                  |
| Solis Generator charging switch                           |                |                            | Measurement      | 43815                                  |
| Solis Generator Set Enable Switch                         |                |                            | Measurement      | 43340                                  |
| Solis Hybrid Function Control                             |                |                            | Measurement      | 43483                                  |
| Solis Status String                                       |                |                            |                  | 33095                                  |
| Solis PV Power 1                                          | POWER          | WATT                       | MEASUREMENT      | 33049, 33050                           |
| Solis PV Power 2                                          | POWER          | WATT                       | MEASUREMENT      | 33051, 33052                           |
| Solis Battery Charge Power                                | POWER          | WATT                       | MEASUREMENT      | if 33135 == 0 then 33149, 33150 else 0 |
| Solis Battery Discharge Power                             | POWER          | WATT                       | MEASUREMENT      | if 33135 == 1 then 33149, 33150 else 0 |
