# Heishamon by Lutarym - Home Assistant Integration

**Vollständige Home Assistant Integration für Panasonic Aquarea Wärmepumpen über Heishamon (HTTP API - kein MQTT nötig)**

Version: 0.1.0

## Features

✅ **Alle 143 Heishamon Topics** als native Home Assistant Entities
✅ **Direkte HTTP API** - keine externe Broker nötig
✅ **Device + Entities** mit korrektem Device Registry
✅ **Entity-IDs mit TOP-Nummern** (z.B. `sensor.heishamon_top5_main_inlet_temp`)
✅ **Flexible Modi**: Listening-Only oder Vollsteuerung
✅ **5 Sprachen**: Deutsch, Englisch, Französisch, Niederländisch, Italienisch
✅ **Vollständige Steuerung**: 25+ SET Commands
✅ **Climate Integration**: Zone 1 & Zone 2 Steuerung

## Installation

### Option 1: Manuell (für Entwicklung)

1. Lade die ZIP herunter und extrahiere sie
2. Kopiere `heishamon_lutarym` nach:
   ```
   ~/.homeassistant/custom_components/
   ```
3. Starte Home Assistant neu

### Option 2: HACS (später verfügbar)

1. Öffne HACS
2. Suche nach "Heishamon by Lutarym"
3. Installiere die Integration
4. Starte Home Assistant neu

## Konfiguration

1. Gehe zu **Einstellungen > Geräte und Dienste > Integrationen**
2. Klick auf **Neue Integration erstellen**
3. Suche nach **Heishamon by Lutarym**
4. Trage ein:
   - **Heishamon IP**: z.B. `192.168.1.100`
   - **Username**: (optional, falls aktiviert)
   - **Password**: (optional, falls aktiviert)
   - **Update-Intervall**: Sekunden (Standard: 30)
   - **Listening Only**: 
     - ✓ aktiviert = nur Sensoren (read-only)
     - ✗ deaktiviert = Sensoren + Steuerung

## Entity-Struktur

### Sensors (alle 143 Topics als Sensoren)

Die Entities haben folgende Namenskonvention:
```
sensor.heishamon_TOP5_main_inlet_temp
sensor.heishamon_TOP6_main_outlet_temp
sensor.heishamon_TOP10_dhw_temp
...
```

**Wichtige Sensoren**:
- `TOP5`: Rücklauftemperatur Wärmeerzeuger
- `TOP6`: Vorlauftemperatur Wärmeerzeuger
- `TOP10`: Warmwasser Ist-Temperatur
- `TOP14`: Außentemperatur
- `TOP15/TOP16`: Heiz-Leistung (Watt)

### Number Entities (bei Vollsteuerung)

Temperatur- und Einstellungs-Kontrolle:
- `number.heishamon_TOP9_dhw_target_temp` - Warmwasser Solltemperatur
- `number.heishamon_TOP27_z1_heat_request_temp` - Zone 1 Heiz-Solltemp
- `number.heishamon_TOP77_heating_off_outdoor_temp` - Heizung-Abschalt-Temp

### Switches (bei Vollsteuerung)

Schalter für Steuerungen:
- `switch.heishamon_setheatpump` - Wärmepumpe An/Aus
- `switch.heishamon_setforcedwh` - Warmwasser erzwingen
- `switch.heishamon_setforcedefrost` - Abtauen erzwingen

### Select Entities (bei Vollsteuerung)

Betriebsmodi und Einstellungen:
- `select.heishamon_setoperationmode` - Heat/Cool/Auto/DHW
- `select.heishamon_setquietmode` - Ruhe-Level (0-3)
- `select.heishamon_setpowerfulmode` - Power-Modus (0/30/60/90 min)

### Climate (bei Vollsteuerung)

Klima-Steuerung für beide Zonen:
- `climate.heishamon_z1_climate` - Zone 1
- `climate.heishamon_z2_climate` - Zone 2

## Troubleshooting

### Verbindung fehlgeschlagen?

```bash
# Test ob Heishamon erreichbar ist:
curl http://192.168.x.x/json

# Bei Auth:
curl -u username:password http://192.168.x.x/json
```

### Entities werden nicht angezeigt?

1. Prüfe Home Assistant Logs: **Einstellungen > Systeminformation > Logs**
2. Suche nach "heishamon"
3. Überprüfe Update-Intervall (nicht zu kurz)

### Steuerung funktioniert nicht?

- Stelle sicher, dass "Listening Only" **NICHT** aktiviert ist
- Prüfe Username/Password in Heishamon Einstellungen
- Teste direkt: `curl -X GET "http://192.168.x.x/command?SetHeatpump=1"`

## All 143 Topics

Die Integration unterstützt alle Topics von TOP0 bis TOP143:

| TOP | Name | Typ | Einheit |
|-----|------|-----|---------|
| TOP5 | Main_Inlet_Temp | sensor | °C |
| TOP6 | Main_Outlet_Temp | sensor | °C |
| TOP10 | DHW_Temp | sensor | °C |
| TOP15 | Heat_Power_Production | sensor | W |
| ... | ... | ... | ... |

Siehe `const.py` für die komplette Liste.

## GitHub

Repository: https://github.com/Lutarym/heishamon-homeassistant-lutarym

Issues: https://github.com/Lutarym/heishamon-homeassistant-lutarym/issues

## Lizenz

MIT License 2026 Lutarym

## Credits

- **Heishamon**: https://github.com/heishamon/HeishaMon
- **Panasonic Aquarea**: https://www.panasonic.com/
- **Home Assistant**: https://www.home-assistant.io/
