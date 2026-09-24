# Heishamon by Lutarym

**English** · [Deutsch](README.de.md) · [Français](README.fr.md) · [日本語](README.ja.md)

Home Assistant integration for Panasonic Aquarea heat pumps through HeishaMon, without MQTT, straight over the HTTP interface.

Version 1.0.1

## What the integration does

It reads `http://<ip>/json` and creates one entity for each of the 144 HeishaMon topics. Writing commands go through `http://<ip>/command?Command=Value`.

All topic names and all SET commands are taken 1:1 from the HeishaMon firmware source (`decode.h`, `commands.h`), not guessed.

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

Interval, control mode and steady readings can be changed later through "Configure" without recreating the entry.

## Entities

One device, containing:

- 137 sensors, one per topic, `sensor.heishamon_<address>_top0` to `..._top143`
- 7 setpoints as Number, only when "Read only" is disabled
- 16 switches and 4 select lists, likewise only with control enabled

The display names follow the language setting of Home Assistant. Available are German, English, French and Japanese. If the language is not among them, English is used. The entity ID contains the address of the board and the TOP number and stays language independent, so automations do not break on a language change. With several HeishaMon boards every ID therefore stays unique.

Example for topic TOP5 at address 192.168.1.50 (`sensor.heishamon_192_168_1_50_top5`):

| Language | Display name |
|---|---|
| German | TOP5 Ruecklauftemperatur |
| English | TOP5 Return water temperature |
| French | TOP5 Temperature retour d'eau |
| Japanese | TOP5 戻り水温度 |

The names are deliberately phrased to be easy to understand rather than translated word for word. `Ipm_Temp`, for example, becomes "Power electronics temperature", `Sterilization_State` becomes "Sterilisation running".

The plain text description that HeishaMon supplies is available as the attribute `beschreibung` on every entity.

### Writable setpoints

| Topic | Command | Range |
|---|---|---|
| TOP9 | SetDHWTemp | 40 to 75 |
| TOP27 | SetZ1HeatRequestTemperature | -5 to 50 |
| TOP28 | SetZ1CoolRequestTemperature | -5 to 20 |
| TOP34 | SetZ2HeatRequestTemperature | -5 to 50 |
| TOP35 | SetZ2CoolRequestTemperature | -5 to 20 |
| TOP77 | SetHeatingOffOutdoorTemp | 5 to 35 |
| TOP78 | SetHeaterOnOutdoorTemp | -15 to 20 |

## Known limitations

- The zones are represented as Number and Select, there is no Climate entity.
- The sections `1wire` and `s0` are read along, but no fixed entities are defined for them.
- The setpoint ranges come from the HeishaMon documentation and may differ depending on the heat pump model.
- The French and Japanese translations have not been checked by native speakers.

## License

MIT, 2026 Lutarym
