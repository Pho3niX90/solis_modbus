# S6-EA1P6K-L compatibility

The S6-EA1P6K-L is a single-phase, low-voltage, AC-coupled storage inverter.
Its existing integration profile is **S6-EA1P**, which includes the 6000 W
variant. A separate model profile is not required for product code `0x4105`.

## Device identity

The following identity values were observed on an S6-EA1P6K-L installation
on 20 October 2026. Product and family values came from the integration's
existing cache; their original sampling times were unavailable.

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

| Area | Evidence and remaining qualification |
| --- | --- |
| Product and family identity | Cached words agree with the matching cloud device record and the protocol's AC-coupled family definition |
| DSP/HMI version fields | Major fields observed in cache; minor fields read through the existing connection |
| Sensor decoding | Clean upstream definitions can decode the copied cache; individual sensor accuracy still needs comparison with independent readings |
| Storage controls | Available in current upstream code; behavior on this device needs a controlled live test |
| Time-of-use and remote dispatch | Firmware capability and behavior must be established separately; zero-filled registers alone do not prove support |
| Clean upstream operation | Live qualification under the S6-EA1P profile remains outstanding |

The battery is owner-reported as a 32 kWh Fogstar LiFePO4 unit emulating
Pylontech communication. The observed battery model setting is `PYLON_LV`.
That setting does not independently confirm battery hardware or capacity,
or establish compatibility with every Pylontech-compatible battery.

## Before testing a replacement build

Compare the installed integration with its reported upstream release and
check automations for dependencies on local services or entities. The
observed installation includes local charge/export control services absent
from upstream; replacing its files could remove those services.

A reload can briefly interrupt telemetry, and a profile change can alter
the available entities and rating-dependent advice. Prepare a backup and
restoration procedure before live changes. Read-only register requests also
add traffic: use the existing connection and pacing, and stop extra queries
if communication degrades.

## Manufacturer references

- *Solis S6-EA1P(3.6-6)K-L User Manual*, version 1.0, February 2024:
  technical data for the 5 kW and 6 kW variants, PDF pages 48–49.
- *Communication Protocol for Energy Storage Inverters*, Ver3.5:
  input register identity definitions on page 7, inverter family table on
  page 133, and handling of unimplemented registers on page 5.

The communication protocol states that unimplemented reads can return zero
and unimplemented writes can receive normal acknowledgements. Establish
support from meaningful values and observed behavior, rather than from
successful Modbus replies alone.
