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

Version 4.4.0 includes ENERGY storage selectors, switches, and time entities
through [PR #530](https://github.com/Pho3niX90/solis_modbus/pull/530). These
controls and the existing public dispatch services provide the integration
interfaces used by the observed household charging/export scripts.

## Validation status

On 21 October 2026, the observed installation was migrated to **unmodified
Solis Modbus 4.4.0** on Home Assistant 2026.10.2. All 41 integration source
files matched release commit `80456a036ee4f817c18acd22f1074da4f021cba7`.
Seven existing household scripts were adapted to ordinary public dispatch
and stop calls. They no longer depend on private integration services.

The initial stock and PR-build trials used **S6-EH1P**, whose default rating
is 8000 W, with direct PV, generator, and high-voltage battery options disabled.
The physical inverter rating and household request ceiling are 6000 W.
The installation now uses **S6-EA1P**, retained after the separate stock-profile
test below, with the other effective configuration settings preserved.

An earlier offline comparison of the two profiles found matching register
groups, named sensor definitions, and storage control definitions with those
feature options. A repeated comparison against release 4.4.0 confirmed equal
features, selectors, switches, and time controls, with default ratings of
6000 W and 8000 W respectively. The setup regression test exercises the
ENERGY profile with direct PV disabled and checks storage control and time
entity creation. These offline checks do not qualify a live profile change.

Three additional passive snapshots were replayed through clean S6-EA1P
sensor entities. Each reproduced twelve observed values, including battery
voltage/current/power/SOC, BMS voltage/current, grid frequency, meter power,
and derived battery/grid power. One snapshot includes a signed meter value
of -62 W, which the net-grid sensor presents as 62 W import. The storage
selector also interprets the observed word 33 as Self-Use. These are cached
observations from the earlier modified installation, rather than independent
physical measurements.

### Bounded live observations

The following tests used the public services on 21 October 2026, with the
unchanged S6-EH1P configuration. The PR build used the exact 41-file runtime
tree from commit `78259cb7252617ec25a050d35cd527e2e0818e14` on HA 2026.10.2.

| Test | Stock 4.4.0 | PR build |
| --- | --- | --- |
| Firmware guard | Release checks dispatch capability only | Fresh capability/version words were `0xAA55`/`1`; explicit discharge-prohibition and PV-limit requests returned the expected V02/V03 validation errors |
| `battery_charge`, 500 W DC | Native charging power reached 492 W and 497 W | Settled native charging power was 493 W during a roughly 41-second pulse |
| `grid_port_import` | At a 6000 W AC target, the port tracked approximately 5980–6000 W import, with up to approximately 5.5 kW battery charging | At a 500 W AC target, the port tracked 500 W import, with 444–445 W battery charging |
| Overnight-script daylight rehearsal | Mechanically equivalent temporary copies with a synthetic window exercised minute renewals, five-minute resampling, holding at 96% SOC, manual stop, same-window recovery suppression, and window expiry | Rehearsal was on stock only |
| `grid_export`, 100 W net grid target | Approximately 95–123 W export at the household meter during a roughly 51-second trial | Approximately 117–132 W export during a roughly 41-second pulse |

Ordinary dispatch stop calls completed without errors after the power trials.
The PR build was then replaced with the exact saved stock 4.4.0 tree, using
two Core restarts for the install/restore procedure. Normal automation states,
the original export limit, household configuration and helpers were restored;
polling was healthy with zero connection failures at the recorded checks.
The stock rehearsal's temporary entities were also removed.

After the PR AC-port import stop, one house-meter sample showed 605 W export;
the native meter sample about one second later showed zero. Before proceeding,
an extra passive check found 14 W export at the house meter and zero at the
native meter. These asynchronous observations do not establish the duration
of any physical excursion.

These trials qualify bounded V1 behavior and the new V2/V3 rejection on the
device under S6-EH1P. Actual overnight scheduling, full-power export/heating
restoration, and native inverter schedules remain unobserved.

### S6-EA1P profile on stock 4.4.0

After restoring stock 4.4.0, the model was changed through the integration's
options flow to S6-EA1P. It initialized as single-phase ENERGY with a 6000 W
rating. All 552 registry entries preserved their unique IDs, entity IDs and device mappings, along with the
existing household script and dashboard references. This used one Solis
integration reload and no Core restart.

Three further roughly 41-second pulses passed: a 500 W DC charge request
settled at 493 W; 500 W AC-port import tracked 500 W with 444 W battery
charging; a 100 W net-export request produced 104–105 W export at the house
meter. Ordinary stops completed and subsequent native observations returned
to normal Self-Use with zero charging and zero net grid flow. The normal
polling cadence means the first post-stop snapshot can retain pre-stop values.

The S6-EA1P profile was retained. All four battery automations were enabled,
the original export limit and helpers were preserved, and Watchman reported
zero missing entities/actions. The source remained the exact 41-file stock
release and household YAML was unchanged. This profile test used released
4.4.0; the PR guard's live tests above used S6-EH1P.

## Remote dispatch firmware versions

A fresh read on 20 October 2026 returned `34502 = 0xAA55` and `34503 = 1`,
matching the three earlier passive snapshots. The first word advertises remote dispatch;
the second is its function version. It is distinct from the time-of-use flag
in register 33289. A fresh read during the PR live test on 21 October returned
the same capability/version values.

The protocol's version history assigns different features to each version:

| Function version in 34503 | Dispatch features |
| --- | --- |
| V01 | Battery hold/charge/discharge and grid-point/AC-port power targets |
| V02 | Adds Self-Use/Feed-in Priority dispatch modes, battery reserve, and discharge prohibition |
| V03 | Adds PV output percentage limiting |

The function-version check in this change rejects requests for newer features
before writing any registers. If the version is absent from cache, an advanced
request reads 34503 through the existing controller; an unknown or insufficient version
raises a validation error. Base V01 requests do not need that additional
version read. The ordinary Storage Mode selector uses register 43110 and
is separate from these versioned dispatch commands.

Mocked service tests cover supported, insufficient, and unknown versions for
both real-time and scheduled calls. They also check that existing V1 household
charging/export requests require no function-version lookup. The stock V1
physical observations above do not exercise V2/V3 features.

## Time of use flag

A fresh input-register read on 20 October 2026 returned `33289 = 0x0000`.
The protocol defines `0xAA55` as the active V2 time-of-use marker, so that marker was absent on
this firmware at the time of the read. Zero alone does not distinguish an
unimplemented register from an implemented inactive function. The configured
`has_v2` option and zero-filled schedule words do not independently establish
support for the V2 scheduling controls. The household rehearsal used Home
Assistant-managed windows and real-time dispatch; it did not qualify native
time-of-use or dispatch schedules.

## Qualification summary

| Area | Evidence and remaining qualification |
| --- | --- |
| Product and family identity | Fresh words agree with earlier cache, the matching cloud device record and the protocol's AC-coupled family definition |
| DSP/HMI version fields | Major words freshly read as 9 and 13; minor words previously read as 14 and 6 through the existing connection |
| Sensor decoding | Three captured snapshots reproduce twelve observed sensor values each; physical accuracy still needs independent comparison |
| Stock integration operation | Exact unmodified 4.4.0 source; bounded charge/import/export and ordinary stops observed under both S6-EH1P and S6-EA1P |
| S6-EA1P profile | Live 6 kW ENERGY profile retained after bounded tests; all 552 entity identities and household references preserved |
| Real-time remote dispatch | V1 charge, AC-port import, low-power grid export, and ordinary stop observed. Full-power export remains unobserved |
| Firmware-version check | V02/V03 requests rejected on the live V1 device; supported/unknown versions also covered offline. V2/V3-capable hardware remains unqualified |
| Native schedules | Active V2 TOU marker absent; zero does not establish non-implementation. Native TOU/dispatch schedule behavior remains untested |
| Household scheduling | Daylight rehearsal passed; actual overnight and full export/heating cycles remain unobserved |

On 20 October 2026, four read-only service requests succeeded during a
23-second collection window, including two passive preflight observations twenty seconds apart.
The global polling heartbeat advanced before the requests; post-read checks
showed no new failures or unavailable states. Seven pre-existing unavailable
entities remained unchanged. This bounded observation does not establish
their runtime attachment, continuous link reliability or freshness of every
cached register.

The battery is owner-reported as a 32 kWh Fogstar LiFePO4 unit emulating
Pylontech communication. The observed battery model setting is `PYLON_LV`.
That setting does not independently confirm battery hardware or capacity,
or establish compatibility with every Pylontech-compatible battery.

## Changing an existing installation

The observed household now runs standard 4.4.0 with S6-EA1P and ordinary Home
Assistant scripts; daily operation does not depend on this PR build. An existing
S6-EH1P configuration should be reviewed before switching to S6-EA1P because
entity identities and rating-dependent advice may change. Offline profile
equivalence does not establish that an in-place switch preserves every
automation reference.

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
