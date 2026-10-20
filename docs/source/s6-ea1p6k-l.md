# S6-EA1P6K-L compatibility

The S6-EA1P6K-L is a single-phase, low-voltage, AC-coupled storage inverter.
Its existing integration profile is **S6-EA1P**, which includes the 6000 W
variant. A separate model profile is not required for product code `0x4105`.

## Device identity

The following identity values were read from an S6-EA1P6K-L installation
on 20 October 2026 at 11:28 UTC, using input-register requests through the
existing integration connection. They agree with earlier cached observations.

| Input register | Decimal value | Hexadecimal value | Meaning |
| --- | --- | --- | --- |
| 33000 | 16645 | `0x4105` | Product model word; its hex digits match the cloud model ID `4105` |
| 35000 | 8337 | `0x2091` | S6 single-phase low-voltage AC-coupled family |

The product code's hexadecimal notation matters: decimal **4105** is a
different register value. Register 35000 identifies the inverter family;
it does not replace the product word in register 33000.

The integration displays the high byte of register 35000 as `Protocol 32`.
That label is distinct from DSP/HMI firmware versions and from the document
revision of the manufacturer's communication protocol.

## Profile and feature options

Select **S6-EA1P** for this inverter. This profile is classified as `ENERGY`
and its default maximum listed rating is 6000 W. Direct PV input should be
disabled; the inverter can operate alongside a separate PV inverter on the
AC side. Configure battery, generator, meter, and time-of-use options for
the actual installation and firmware.

Current upstream gives ENERGY inverters the storage selectors, switches,
and time entities also available to hybrid inverters. This change is in
[PR #530](https://github.com/Pho3niX90/solis_modbus/pull/530).
Version 4.2.6 does not include that change, so availability of controls on a
locally modified 4.2.6 installation cannot establish their availability in
an unmodified release.

## Validation status

The observed installation runs Home Assistant 2026.10.2 with a locally
modified integration reporting version 4.2.6. It is configured as S6-EH1P,
with direct PV, generator, and high-voltage battery options disabled. That
profile defaults to 8000 W; this is a configuration default, not the physical
rating of the S6-EA1P6K-L.

An offline comparison at upstream commit
`011e31196ad2ac110d55b356869af03a3b6e7733` constructed the S6-EA1P and
S6-EH1P profiles with those same feature options. Their register groups,
named sensor definitions, and storage control definitions matched; the
default inverter rating differed. The setup regression test also exercises
the ENERGY profile with direct PV disabled and checks storage control and
time entity creation. These checks do not exercise physical control writes.

Three additional passive snapshots were replayed through clean S6-EA1P
sensor entities. Each reproduced twelve observed values, including battery
voltage/current/power/SOC, BMS voltage/current, grid frequency, meter power,
and derived battery/grid power. One snapshot includes a signed meter value
of -62 W, which the net-grid sensor presents as 62 W import. The storage
selector also interprets the observed word 33 as Self-Use. These are cached
observations from the existing installation, rather than independent
physical measurements or a clean upstream live deployment.

## Remote dispatch firmware versions

A fresh read returned `34502 = 0xAA55` and `34503 = 1`, matching the
three earlier passive snapshots. The first word advertises remote dispatch;
the second is its function version. It is distinct from the time-of-use flag
in register 33289.

The protocol's version history assigns different features to each version:

| Function version in 34503 | Dispatch features |
| --- | --- |
| V01 | Battery hold/charge/discharge and grid-point/AC-port power targets |
| V02 | Adds Self-Use/Feed-in Priority dispatch modes, battery reserve, and discharge prohibition |
| V03 | Adds PV output percentage limiting |

Dispatch services reject requests for newer features before writing any
registers. If the version is absent from cache, an advanced request reads
34503 through the existing controller; an unknown or insufficient version
raises a validation error. Base V01 requests do not need that additional
version read. The ordinary Storage Mode selector uses register 43110 and
is separate from these versioned dispatch commands.

The checks are covered by mocked service tests. Successful physical
dispatch and restoration on this inverter remain to be qualified in a
controlled live test.

## Time of use flag

A fresh input-register read returned `33289 = 0x0000`. The protocol defines
`0xAA55` as the active V2 time-of-use marker, so that marker was absent on
this firmware at the time of the read. Zero alone does not distinguish an
unimplemented register from an implemented inactive function. The configured
`has_v2` option and zero-filled schedule words do not independently establish
support for the V2 scheduling controls.

## Qualification summary

| Area | Evidence and remaining qualification |
| --- | --- |
| Product and family identity | Fresh words agree with earlier cache, the matching cloud device record and the protocol's AC-coupled family definition |
| DSP/HMI version fields | Major words freshly read as 9 and 13; minor words previously read as 14 and 6 through the existing connection |
| Sensor decoding | Three captured snapshots reproduce twelve observed sensor values each; physical accuracy still needs independent comparison |
| Storage controls | Available in current upstream code; behavior on this device needs a controlled live test |
| Time-of-use and remote dispatch | Dispatch advertises V1; the active V2 TOU marker is absent. Physical control and schedule behavior remain to be tested |
| Clean upstream operation | Live qualification under the S6-EA1P profile remains outstanding |

Four read-only service requests succeeded during a 23-second collection
window, including two passive preflight observations twenty seconds apart.
The global polling heartbeat advanced before the requests; post-read checks
showed no new failures or unavailable states. Seven pre-existing unavailable
entities remained unchanged. This bounded observation does not establish
their runtime attachment, continuous link reliability or freshness of every
cached register.

The battery is owner-reported as a 32 kWh Fogstar LiFePO4 unit emulating
Pylontech communication. The observed battery model setting is `PYLON_LV`.
That setting does not independently confirm battery hardware or capacity,
or establish compatibility with every Pylontech-compatible battery.

## Before testing a replacement build

Compare the installed integration with its reported upstream release and
check automations for dependencies on local services or entities. The
observed installation includes local charge/export control services absent
from upstream. Four stored scripts call these services, with related
automations and dashboard actions; replacing the integration would remove
service implementations they depend on.

Testing replacement Python code requires planning for a Home Assistant
restart, as in the project's
[production development workflow](https://contributors.home-assistant.io/core/development/tips/#try-a-change-on-your-production-system).
This interrupts Home Assistant processing, including other automations,
while it restarts. A profile change can also alter available entities and
rating-dependent advice. Prepare a backup and restoration procedure before
live changes. Read-only register requests also add traffic: use the existing
connection and pacing, and stop extra queries if communication degrades.

## Manufacturer references

- *Solis S6-EA1P(3.6-6)K-L User Manual*, version 1.0, February 2024:
  technical data for the 5 kW and 6 kW variants, PDF pages 48–49.
- *Communication Protocol for Energy Storage Inverters*, Ver3.5:
  input register identity definitions on page 7, inverter family table on
  page 133, dispatch function version history on page 114, and handling of
  unimplemented registers on page 5.

The communication protocol states that unimplemented reads can return zero
and unimplemented writes can receive normal acknowledgements. Establish
support from meaningful values and observed behavior, rather than from
successful Modbus replies alone.
