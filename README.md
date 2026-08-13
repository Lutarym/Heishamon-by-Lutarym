# Heishamon by Lutarym

Home Assistant Integration für Panasonic Aquarea Wärmepumpen über HeishaMon, ohne MQTT, direkt über die HTTP-Schnittstelle.

Version 0.3.0

## Was die Integration macht

Sie liest `http://<ip>/json` aus und legt für jedes der 144 HeishaMon-Topics eine Entity an. Schreibende Befehle gehen über `http://<ip>/command?Kommando=Wert`.

Alle Topic-Namen und alle SET-Kommandos stammen 1:1 aus dem HeishaMon-Firmware-Quellcode (`decode.h`, `commands.h`) und sind nicht geraten.

## Installation

1. Ordner `custom_components/heishamon_lutarym` nach `<config>/custom_components/` kopieren
2. Home Assistant neu starten
3. Einstellungen, Geräte und Dienste, Integration hinzufügen, "Heishamon by Lutarym"

## Konfiguration

| Feld | Bedeutung |
|---|---|
| IP-Adresse | Adresse der HeishaMon-Platine |
| Benutzername, Passwort | nur nötig, wenn im HeishaMon gesetzt |
| Aktualisierung | Abstand in Sekunden, Standard 30 |
| Nur lesen | aktiv: nur Sensoren. Inaktiv: zusätzlich Steuerung |

## Entities

Ein Gerät, darunter:

- 137 Sensoren, `sensor.heishamon_top0` bis `sensor.heishamon_top143`
- 7 Sollwerte als Number, nur wenn "Nur lesen" deaktiviert ist
- 16 Schalter, 3 Auswahllisten, ebenfalls nur bei aktiver Steuerung

Die Anzeigenamen folgen der Spracheinstellung von Home Assistant. Verfügbar sind Deutsch, Englisch, Französisch, Niederländisch und Italienisch. Die Entity-ID enthält immer die TOP-Nummer und bleibt sprachunabhängig, Automationen brechen also beim Sprachwechsel nicht.

Beispiel für `sensor.heishamon_top5`:

| Sprache | Anzeigename |
|---|---|
| Deutsch | TOP5 Ruecklauftemperatur |
| Englisch | TOP5 Return water temperature |
| Französisch | TOP5 Temperature retour d'eau |
| Niederländisch | TOP5 Retourtemperatuur water |
| Italienisch | TOP5 Temperatura ritorno acqua |

Die Namen sind bewusst allgemeinverständlich formuliert statt wörtlich übersetzt. Aus `Ipm_Temp` wird zum Beispiel "Temperatur Leistungselektronik", aus `Sterilization_State` wird "Legionellenschutz laeuft".

Die Klartext-Beschreibung, die HeishaMon mitliefert, steht als Attribut `beschreibung` an jeder Entity.

### Schreibbare Sollwerte

| Topic | Kommando | Bereich |
|---|---|---|
| TOP9 | SetDHWTemp | 40 bis 75 |
| TOP27 | SetZ1HeatRequestTemperature | -5 bis 50 |
| TOP28 | SetZ1CoolRequestTemperature | -5 bis 20 |
| TOP34 | SetZ2HeatRequestTemperature | -5 bis 50 |
| TOP35 | SetZ2CoolRequestTemperature | -5 bis 20 |
| TOP77 | SetHeatingOffOutdoorTemp | 5 bis 35 |
| TOP78 | SetHeaterOnOutdoorTemp | -15 bis 20 |

## Bekannte Einschränkungen

- Die Zonen sind als Number und Select abgebildet, es gibt keine Climate-Entity.
- Die Sektionen `1wire` und `s0` werden mitgelesen, aber es sind dafür keine festen Entities definiert.
- Die Wertebereiche der Sollwerte stammen aus der HeishaMon-Dokumentation und können je nach Wärmepumpenmodell abweichen.
- Die Übersetzungen ins Französische, Niederländische und Italienische sind nicht von Muttersprachlern geprüft.

## Lizenz

MIT, 2026 Lutarym
