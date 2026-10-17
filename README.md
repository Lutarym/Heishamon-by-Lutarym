# Heishamon by Lutarym

**English** · [Deutsch](README.de.md) · [Français](README.fr.md) · [日本語](README.ja.md)

Home Assistant integration for Panasonic Aquarea heat pumps through HeishaMon, without MQTT, straight over the HTTP interface.

Version 1.3.0

## What the integration does

It reads `http://<ip>/json` and creates one sensor for each of the 144 HeishaMon topics. If the board supplies them, it adds the precise power values (XTOP), the optional PCB values (OPT), 1-Wire temperature sensors and S0 meters. Writing commands go through `http://<ip>/command?Command=Value`.

All topic names, commands, value ranges and encodings are taken from the HeishaMon firmware source and documentation (`decode.h`, `commands.h`, `commands.cpp`, `MQTT-Topics.md`, `OptionalPCB.md` in [heishamon/HeishaMon](https://github.com/heishamon/HeishaMon)), not guessed.

## Requirements

- Home Assistant 2024.11.0 or later
- HeishaMon board reachable on the network

## Installation

### Manual

1. Copy the folder `custom_components/heishamon_lutarym` into `<config>/custom_components/`
2. Restart Home Assistant
3. Settings, Devices and Services, Add Integration, "Heishamon by Lutarym"

### HACS

Add the project as a Custom Repository with category **Integration**, then install it and restart Home Assistant.

## Configuration

| Field | Meaning |
|---|---|
| IP address | Address of the HeishaMon board |
| Username, password | only needed if set on the HeishaMon |
| Update interval | interval in seconds, default 5, range 1 to 300 |
| Read only | on: sensors only. Off: controls in addition |
| Steady readings | smooths the jitter of integer temperature values |
| Required repetitions | how often a new value must be confirmed, 2 to 20 |
| External power meter | optional, power sensor for the heat pump only, for example a Shelly |

Interval, control mode, steady readings and power meter can be changed later through "Configure". Address, username and password through "Reconfigure". If the address changes, device, entities and history are kept.

## Entities

One device, containing:

| Kind | Count | When |
|---|---|---|
| Sensors TOP0 to TOP143 | 144 | always |
| Sensors XTOP0 to XTOP5 (precise power values) | 6 | if the heat pump sends them (K/L series and newer) |
| Sensors OPT0 to OPT6 | 7 | if optional PCB emulation is enabled in HeishaMon |
| 1-Wire temperature sensors | one per sensor | if 1-Wire is enabled in HeishaMon |
| S0 meters, power and meter reading | two per port | if S0 is enabled in HeishaMon |
| COP heating, COP hot water | 2 | always |
| Select COP source | 1 | with an external power meter, also in read only mode |
| Adjustable values (Number) | 36 | only with control |
| Switches | 17 | only with control |
| Select lists | 11 | only with control |
| Button "Reset error" | 1 | only with control |
| Optional PCB: 8 values, 2 switches, 3 selects | 13 | only with control and active emulation |

XTOP, OPT, 1-Wire and S0 are detected when the integration loads. If they are added later, reload the integration.

The display names follow the language setting of Home Assistant. Available are German, English, French and Japanese. If the language is not among them, English is used. The entity ID contains the address of the board and the TOP number and stays language independent, so automations do not break on a language change.

Example for topic TOP5 at address 192.168.1.50 (`sensor.heishamon_192_168_1_50_top5`):

| Language | Display name |
|---|---|
| German | TOP5 Rücklauftemperatur |
| English | TOP5 Return water temperature |
| French | TOP5 Température retour d'eau |
| Japanese | TOP5 戻り水温度 |

The names are deliberately phrased to be easy to understand rather than translated word for word. `Ipm_Temp`, for example, becomes "Power electronics temperature", `Sterilization_State` becomes "Sterilisation running".

The plain text description that HeishaMon supplies is available as the attribute `beschreibung` on every entity.

### COP

Heating and hot water are calculated separately. The COP is the heat energy divided by the electrical energy of the current run, however long the run takes. A run starts when the compressor starts and ends when the compressor stops or the three way valve (TOP20) changes the operating mode. After that the state is "unknown". Defrosting is part of the run, because it uses electricity and takes heat from the water. Cooling is not covered.

The energy is summed up at every poll as power times the time since the previous poll.

The COP source select decides where the displayed value comes from. Switching takes effect immediately, both calculations always run in the background. The choice is kept after a restart.

| COP source | Heat energy | Electrical energy |
|---|---|---|
| Heat pump | as reported by the heat pump | as reported by the heat pump |
| Measured (power meter) | volume flow × density × heat capacity × (outlet − inlet) | external power meter |

Density and heat capacity of water are taken from table values at the mean water temperature. With glycol in the circuit the measured COP is therefore not correct.

Units of the K/L series and newer report precise power values (XTOP0 to XTOP5), which are then used. Older units report power only in steps of 200 W, so the COP from the heat pump is correspondingly coarse there. The attribute `werte` shows which values are used (XTOP or TOP).

The power meter must measure the heat pump only and report in W, kW, mW or MW.

If the COP is above the Carnot limit (theoretical maximum from outlet and outdoor temperature), it is physically impossible and is shown as "unknown".

Attributes on the sensor: `quelle`, `waermemenge_kwh`, `strommenge_kwh`, `laufzeit_min`.

## Control

Important: the HeishaMon board answers every command with "OK", even if it discards a value. The integration therefore checks every value before sending and shows an error in the UI if it is outside the valid range. If the board cannot be reached, an error is shown as well.

### Adjustable values

| Topic | Command | Range |
|---|---|---|
| TOP9 | SetDHWTemp | 40 to 75 °C |
| TOP27, TOP34 | SetZ1/Z2HeatRequestTemperature | see zones |
| TOP28, TOP35 | SetZ1/Z2CoolRequestTemperature | see zones |
| TOP77 | SetHeatingOffOutdoorTemp | 5 to 35 °C |
| TOP78 | SetHeaterOnOutdoorTemp | -15 to 20 °C |
| TOP95 | SetMaxPumpDuty | 64 to 254 |
| TOP23 | SetFloorHeatDelta | 1 to 15 K |
| TOP24 | SetFloorCoolDelta | 1 to 15 K |
| TOP22 | SetDHWHeatDelta | -12 to -2 K |
| TOP113 | SetBufferDelta | 0 to 10 K |
| TOP131 | SetBivalentStartTemp | -15 to 35 °C |
| TOP134 | SetBivalentAPStartTemp | -15 to 35 °C |
| TOP135 | SetBivalentAPStopTemp | -15 to 35 °C |
| TOP70 | SetSterilizationTemp | 55 to 75 °C |
| TOP71 | SetSterilizationMaxTime | 5 to 60 min in steps of 5 |
| TOP96 | SetHeaterDelayTime (J series only) | 0 to 254 min * |
| TOP97 | SetHeaterStartDelta (J series only) | -127 to 127 K * |
| TOP98 | SetHeaterStopDelta (J series only) | -127 to 127 K * |
| TOP29 to TOP32, TOP72 to TOP75, TOP82 to TOP89 | SetCurves (heating and cooling curves, zone 1 and 2) | -127 to 127 °C * |

\* The HeishaMon documentation gives no range. The limits are those of the encoding in the firmware. Which values the heat pump accepts is not known.

Each curve point is sent on its own. The small HeishaMon board (ESP8266) handles only 128 bytes per request, the whole curve at once does not fit.

### Zones

According to the HeishaMon documentation, the valid range depends on whether the zone runs on the heating curve or with a direct temperature. The heat pump reports this in TOP76 (heating) and TOP81 (cooling). The control adjusts its range accordingly.

| | Heating curve (shift) | Direct temperature |
|---|---|---|
| Heating | -5 to 5 | 20 to 75 °C |
| Cooling | -5 to 5 | 5 to 20 °C |

For direct heating the documentation says "20 to max". 75 °C is the highest water setpoint HeishaMon documents. The real maximum depends on the model.

According to the HeishaMon documentation, in thermostat or thermistor mode the direct temperature cannot be set with these values, but with the high point of the heating curve.

### Select lists

| Command | Options |
|---|---|
| SetOperationMode | Heat, Cool, Auto, Hot water, Heat + hot water, Cool + hot water, Auto + hot water |
| SetQuietMode | Off, level 1 to 3 |
| SetPowerfulMode | Off, 30, 60, 90 minutes |
| SetZones | Zone 1, zone 2, both |
| SetExternalPadHeater | Off, type A, type B |
| SetBivalentMode | Alternative, parallel, advanced parallel |
| SetHeatingControl | Comfort, efficiency |
| SetSmartDHW | Variable, standard |
| SetQuietModePriority | Sound, capacity |
| SetPumpFlowrateMode | Delta T, maximum flow |
| SetDHWSensorSelection | Top, center (K/L series All-in-One only) |

The heat pump also reports the operating modes "Auto (cool)" and "Auto (cool) + hot water". They are shown as Auto and Auto + hot water.

### Switches and button

17 switches, among them heat pump on/off, force hot water, force defrost, start sterilisation, emergency heater, holiday mode, schedule, buffer tank, external controls, bivalent control and the backup heaters for room and hot water.

The button "Reset error" acknowledges a pending heat pump error (for example H72), like the reset button on the remote control.

### Optional PCB

Only if optional PCB emulation is enabled in HeishaMon. According to the HeishaMon documentation it is experimental, and the heat pump goes to standby with error H74 if the board stops sending for about 40 seconds. Read [OptionalPCB.md](https://github.com/heishamon/HeishaMon/blob/master/OptionalPCB.md) first.

| Command | Kind |
|---|---|
| SetSmartGridMode | Select: normal, capacity 1, heat pump and hot water off, capacity 2 |
| SetExternalThermostat1State, SetExternalThermostat2State | Select: no demand, cooling, heating, both |
| SetHeatCoolMode, SetCompressorState | Switch |
| SetDemandControl | Value 43 to 234 (according to the documentation 5 % to 100 %) |
| SetPoolTemp, SetBufferTemp, SetZ1RoomTemp, SetZ1WaterTemp, SetZ2RoomTemp, SetZ2WaterTemp, SetSolarTemp | Temperature -78 to 120 °C |

The board does not report these values back. The last value set is shown and kept after a restart. `SetOptPCBByte9` is not included, the documentation does not describe its meaning.

## Known limitations

- The zones are represented as Number and Select, there is no Climate entity.
- The OpenTherm section of the board is not used.
- The value ranges come from the HeishaMon documentation and may differ depending on the heat pump model.
- The optional PCB commands and the SmartGrid mapping follow the HeishaMon documentation but have not been tested on a heat pump.
- The French and Japanese translations have not been checked by native speakers.

## License

MIT, 2026 Lutarym
