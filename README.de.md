# Heishamon by Lutarym

[English](README.md) · **Deutsch** · [Français](README.fr.md) · [日本語](README.ja.md)

Home Assistant Integration für Panasonic Aquarea Wärmepumpen über HeishaMon, ohne MQTT, direkt über die HTTP-Schnittstelle.

Version 1.0.1

## Was die Integration macht

Sie liest `http://<ip>/json` aus und legt für jedes der 144 HeishaMon-Topics eine Entity an. Schreibende Befehle gehen über `http://<ip>/command?Kommando=Wert`.

Alle Topic-Namen und alle SET-Kommandos stammen 1:1 aus dem HeishaMon-Firmware-Quellcode (`decode.h`, `commands.h`) und sind nicht geraten.

## Installation

### Manuell

1. Ordner `custom_components/heishamon_lutarym` nach `<config>/custom_components/` kopieren
2. Home Assistant neu starten
3. Einstellungen, Geräte und Dienste, Integration hinzufügen, "Heishamon by Lutarym"

### HACS

Als eigenes Repository (Custom Repository) mit der Kategorie **Integration** hinzufügen, dann installieren und Home Assistant neu starten.

## Konfiguration

| Feld | Bedeutung |
|---|---|
| IP-Adresse | Adresse der HeishaMon-Platine |
| Benutzername, Passwort | nur nötig, wenn im HeishaMon gesetzt |
| Aktualisierung | Abstand in Sekunden, Standard 5, Bereich 1 bis 300 |
| Nur lesen | aktiv: nur Sensoren. Inaktiv: zusätzlich Steuerung |
| Werte beruhigen | glättet das Zappeln ganzzahliger Temperaturwerte |
| Nötige Wiederholungen | wie oft ein neuer Wert bestätigt sein muss, 2 bis 20 |

Takt, Steuerbarkeit und Beruhigung lassen sich später über "Konfigurieren" ändern, ohne den Eintrag neu anzulegen.

## Entities

Ein Gerät, darunter:

- 137 Sensoren, je Topic einer, `sensor.heishamon_<adresse>_top0` bis `..._top143`
- 7 Sollwerte als Number, nur wenn "Nur lesen" deaktiviert ist
- 16 Schalter und 4 Auswahllisten, ebenfalls nur bei aktiver Steuerung

Die Anzeigenamen folgen der Spracheinstellung von Home Assistant. Verfügbar sind Deutsch, Englisch, Französisch und Japanisch. Ist die Sprache nicht dabei, wird Englisch genutzt. Die Entity-ID enthält die Adresse der Platine und die TOP-Nummer und bleibt sprachunabhängig, Automationen brechen also beim Sprachwechsel nicht. Bei mehreren HeishaMon-Geräten bleibt so jede ID eindeutig.

Beispiel für Topic TOP5 bei der Adresse 192.168.1.50 (`sensor.heishamon_192_168_1_50_top5`):

| Sprache | Anzeigename |
|---|---|
| Deutsch | TOP5 Ruecklauftemperatur |
| Englisch | TOP5 Return water temperature |
| Französisch | TOP5 Temperature retour d'eau |
| Japanisch | TOP5 戻り水温度 |

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
- Die Übersetzungen ins Französische und Japanische sind nicht von Muttersprachlern geprüft.

## Lizenz

MIT, 2026 Lutarym
