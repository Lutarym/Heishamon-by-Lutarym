# Heishamon by Lutarym

Home Assistant Integration für Panasonic Aquarea Wärmepumpen über Heishamon (HTTP API, kein MQTT nötig).

## Features

- **Vollständige Unterstützung**: Alle 143 Heishamon Topics
- **Direkter HTTP Zugang**: Keine externen Broker nötig
- **Flexible Modi**: Listen-Only oder Vollsteuerung wählbar
- **Mehrsprachig**: Deutsch, Englisch, Französisch, Niederländisch, Italienisch
- **Native Entities**: Sensoren, Nummern, Schalter, Auswahl, Klima

## Installation

### 1. Manuell (für Entwicklung)

Kopiere den `heishamon_lutarym` Ordner in:
```
~/.homeassistant/custom_components/
```

Starte Home Assistant neu.

### 2. Über HACS (später verfügbar)

1. Öffne HACS
2. Suche nach "Heishamon by Lutarym"
3. Klick auf "Install"
4. Starte Home Assistant neu

## Konfiguration

1. Gehe zu **Einstellungen > Geräte und Dienste > Integrationen**
2. Klick auf **Neue Integration erstellen**
3. Suche nach **Heishamon by Lutarym**
4. Gib ein:
   - **Host**: IP-Adresse deines Heishamon (z.B. 192.168.1.100)
   - **Username**: (optional) Falls aktiviert
   - **Password**: (optional) Falls aktiviert
   - **Update-Intervall**: Sekunden (Standard: 30)
   - **Listening Only**: Nur Sensor-Daten (keine Steuerung) oder Vollzugriff

## Sensoren

Die Integration erstellt automatisch Entities für alle 143 Heishamon Topics:

- **Temperaturen**: Main_Inlet_Temp, Main_Outlet_Temp, DHW_Temp, etc.
- **Leistung**: Heat_Power_Production, Cool_Power_Production, etc.
- **Zustände**: Heatpump_State, Operating_Mode, Defrosting_State, etc.
- **Steuerung** (nur bei Vollzugriff): SetHeatpump, SetDHWTemp, SetOperationMode, etc.

## Steuerung

Bei **Listening Only = false** werden zusätzlich verfügbar:

- **Switches**: Wärmepumpe an/aus, Defrost, DHW, etc.
- **Numbers**: DHW-Temperatur, Heiz-/Kühlkurven, etc.
- **Select**: Betriebsmodus, Ruhe-Level, Power-Modus
- **Climate**: Zone 1 & Zone 2 mit Temperatursteuerung

## Problembehebung

### Verbindung fehlgeschlagen
- Prüfe, dass Heishamon unter dieser IP erreichbar ist
- `ping 192.168.x.x`
- Öffne im Browser: `http://192.168.x.x/json`

### Entities werden nicht angezeigt
- Überprüfe das Update-Intervall (nicht zu kurz)
- Prüfe Home Assistant Logs: **Einstellungen > Systeminformation > Logs**

### Steuerung funktioniert nicht
- Stelle sicher, dass "Listening Only" NICHT aktiviert ist
- Prüfe Heishamon Credentials (Username/Password)

## GitHub

Repository: https://github.com/Lutarym/heishamon-homeassistant-lutarym

Issues: https://github.com/Lutarym/heishamon-homeassistant-lutarym/issues

## Lizenz

MIT License
