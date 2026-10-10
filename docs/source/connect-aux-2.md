# Home Assistant Connect AUX-2

[Home Assistant Connect AUX-2](https://github.com/Pho3niX90/solis_modbus/issues/483) is a small ESPHome-based device from Nabu Casa with two **RS-232** serial ports. Home Assistant reaches those ports over your network (Ethernet/PoE or Wi-Fi) as *serial proxies*, so the device can sit next to the inverter while Home Assistant runs elsewhere.

Solis inverters talk Modbus over **RS-485**, not RS-232, so you need an **RS-232 to RS-485 converter** between the AUX-2 and the inverter. With that in place, the integration uses the AUX-2 like any other serial port.

## Requirements

- **Home Assistant 2026.5 or newer**: serial proxy support arrived in 2026.5.
- **Solis Modbus 4.4.0 or newer**: earlier versions can't open serial proxy ports.
- **An RS-232 to RS-485 converter.**
  - Prefer one with **automatic send/receive switching** and its **own power input**. Converters that take power or direction control from the RS-232 handshake lines depend on signals the serial proxy may not provide.
- **A cable from the converter's RS-485 side to the inverter's RS-485 port.** This is the port the Solis datalogger stick normally uses.

## Wiring

```
Solis inverter                RS-485 to RS-232                Connect AUX-2
RS-485 port   ── A / B ──▶    converter            ──RS-232──▶  serial port 1 or 2  ──LAN / Wi-Fi──▶  Home Assistant
```

1. **Connect the RS-485 pair.** Wire the converter's **A (+)** and **B (−)** to the A and B pins of the inverter's RS-485 port.
   - The pinout differs between models; see your inverter's manual.
   - Connect GND too if both sides have one.
2. **Connect the RS-232 side** of the converter to one of the AUX-2's serial ports.
3. **Power the converter**, if it has a power input.

**One controller per port.** The Solis datalogger stick also polls the inverter over RS-485. Two controllers on the same bus collide, so use the AUX-2 *instead of* the stick on that port. You lose SolisCloud reporting through the stick unless your inverter has a second RS-485 port for it.

**Don't use the meter port.** It's a separate bus where the inverter is the one asking, so it won't answer requests there.

## Set up the AUX-2 in Home Assistant

1. **Adopt the AUX-2 in ESPHome.** Do this as you would any ESPHome device: it shows up under **Settings → Devices & services** as discovered.
2. **Check the ports are listed.** Open **Settings → Connectivity → Serial**. The AUX-2's ports appear under **Serial proxies**, with the device's name.
   - A proxied port is only listed while the AUX-2 is online. If the ports are missing, check that it's powered and connected.

## Add the inverter

1. Go to **Settings → Devices & services → Add integration → Solis Modbus**.
2. Choose **Serial (RS485)** as the connection type.
3. **Serial Port**: pick the AUX-2 port from the list. Its address starts with `esphome-hass://`.
4. **Line settings**: these must match the inverter. Solis defaults are **9600** baud, **8** data bits, parity **None**, **1** stop bit, which are also the integration's defaults.
5. **Slave** (Modbus address): the inverter's address, **1** unless you changed it on the inverter.
6. Fill in the inverter serial number and model, then submit.
   - The integration reads one register to check the link before it creates the entry.

Once added, the port shows under **Settings → Connectivity → Serial** as used by Solis Modbus.

### Several inverters on one AUX-2 port

RS-485 is a bus, so several inverters can share one AUX-2 port:

1. Daisy-chain their RS-485 ports (A to A, B to B).
2. Give each inverter a different Modbus address on its display.
3. Add one Solis Modbus entry per inverter, each picking the **same** AUX-2 port with its own slave address. The entries share one connection, and requests are spaced as the Solis protocol requires.

## Troubleshooting the AUX-2

| Symptom | Likely cause |
|---|---|
| The AUX-2 port isn't in the Serial Port list | The AUX-2 is offline or not adopted yet, or Home Assistant is older than 2026.5. Check **Settings → Connectivity → Serial**. |
| "This serial port can't be used" | Solis Modbus is older than 4.4.0, which can't open serial proxy ports. Update the integration. |
| "Failed to connect" when adding the inverter | Try these in order: <br>1. Swap A and B. <br>2. Check that the line settings and slave address match the inverter. <br>3. Make sure the converter is powered and nothing else (such as the datalogger stick) is on the same RS-485 port. |
| Works, then drops out | On long cable runs, add a 120 Ω termination resistor across A and B at each end of the bus. If the AUX-2 uses Wi-Fi, check its signal. |
| Readings stop after the AUX-2 restarts | The integration reconnects on its own once the AUX-2 is back. If it doesn't, reload the integration and include the logs in an issue. |

If you get stuck, open an [issue](https://github.com/Pho3niX90/solis_modbus/issues) with your inverter model, the converter you use and the integration's debug log.
