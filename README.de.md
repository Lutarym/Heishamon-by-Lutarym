# Heishamon by Lutarym

[English](README.md) · **Deutsch** · [Français](README.fr.md) · [日本語](README.ja.md)

Home Assistant Integration für Panasonic Aquarea Wärmepumpen über HeishaMon, ohne MQTT, direkt über die HTTP-Schnittstelle.

Version 1.3.0

## Was die Integration macht

Sie liest `http://<ip>/json` aus und legt für jedes der 144 HeishaMon-Topics einen Sensor an. Dazu kommen, sofern die Platine sie liefert, die genauen Leistungswerte (XTOP), die Werte der Optional-Platine (OPT), 1-Wire-Temperaturfühler und S0-Zähler. Schreibende Befehle gehen über `http://<ip>/command?Kommando=Wert`.

Alle Topic-Namen, Befehle, Wertebereiche und Kodierungen stammen aus dem HeishaMon-Firmware-Quellcode und der Doku (`decode.h`, `commands.h`, `commands.cpp`, `MQTT-Topics.md`, `OptionalPCB.md` in [heishamon/HeishaMon](https://github.com/heishamon/HeishaMon)) und sind nicht geraten.

## Voraussetzungen

- Home Assistant 2024.11.0 oder neuer
- HeishaMon-Platine im Netzwerk erreichbar

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
| Externer Strommesser | optional, Leistungssensor nur für die Wärmepumpe, etwa ein Shelly |

Takt, Steuerbarkeit, Beruhigung und Strommesser lassen sich später über "Konfigurieren" ändern. Adresse, Benutzer und Passwort über "Neu konfigurieren". Ändert sich die Adresse, bleiben Gerät, Entities und Verlauf erhalten.

## Entities

Ein Gerät, darunter:

| Art | Anzahl | Wann |
|---|---|---|
| Sensoren TOP0 bis TOP143 | 144 | immer |
| Sensoren XTOP0 bis XTOP5 (genaue Leistungswerte) | 6 | wenn die Wärmepumpe sie sendet (K/L-Serie und neuer) |
| Sensoren OPT0 bis OPT6 | 7 | wenn die Optional-Platine-Emulation in HeishaMon aktiv ist |
| 1-Wire-Temperaturfühler | je Fühler einer | wenn 1-Wire in HeishaMon aktiv ist |
| S0-Zähler, Leistung und Zählerstand | je Port zwei | wenn S0 in HeishaMon aktiv ist |
| COP Heizen, COP Warmwasser | 2 | immer |
| Auswahl COP Quelle | 1 | mit externem Strommesser, auch im Nur-Lesen-Betrieb |
| Einstellbare Werte (Number) | 36 | nur mit Steuerung |
| Schalter | 17 | nur mit Steuerung |
| Auswahllisten | 11 | nur mit Steuerung |
| Taster "Fehler zurücksetzen" | 1 | nur mit Steuerung |
| Optional-Platine: 8 Werte, 2 Schalter, 3 Auswahllisten | 13 | nur mit Steuerung und aktiver Emulation |

XTOP, OPT, 1-Wire und S0 werden beim Laden der Integration erkannt. Kommen sie später dazu, die Integration neu laden.

Die Anzeigenamen folgen der Spracheinstellung von Home Assistant. Verfügbar sind Deutsch, Englisch, Französisch und Japanisch. Ist die Sprache nicht dabei, wird Englisch genutzt. Die Entity-ID enthält die Adresse der Platine und die TOP-Nummer und bleibt sprachunabhängig, Automationen brechen also beim Sprachwechsel nicht.

Beispiel für Topic TOP5 bei der Adresse 192.168.1.50 (`sensor.heishamon_192_168_1_50_top5`):

| Sprache | Anzeigename |
|---|---|
| Deutsch | TOP5 Rücklauftemperatur |
| Englisch | TOP5 Return water temperature |
| Französisch | TOP5 Température retour d'eau |
| Japanisch | TOP5 戻り水温度 |

Die Namen sind bewusst allgemeinverständlich formuliert statt wörtlich übersetzt. Aus `Ipm_Temp` wird zum Beispiel "Temperatur Leistungselektronik", aus `Sterilization_State` wird "Legionellenschutz läuft".

Die Klartext-Beschreibung, die HeishaMon mitliefert, steht als Attribut `beschreibung` an jeder Entity.

### COP

Heizen und Warmwasser werden getrennt berechnet. Der COP ist die Wärmemenge geteilt durch die Strommenge des laufenden Laufs, egal wie lang der Lauf dauert. Ein Lauf beginnt mit dem Start des Verdichters und endet, wenn der Verdichter stoppt oder das Dreiwegeventil (TOP20) die Betriebsart wechselt. Danach ist der Zustand "unbekannt". Abtauen gehört zum Lauf, weil es Strom verbraucht und dem Wasser Wärme entzieht. Kühlen wird nicht erfasst.

Die Energie wird bei jeder Abfrage als Leistung mal Zeit seit der letzten Abfrage aufsummiert.

Mit der Auswahl COP Quelle legst du fest, woher der angezeigte Wert kommt. Das Umschalten wirkt sofort, beide Rechnungen laufen immer mit. Die Wahl bleibt nach einem Neustart erhalten.

| COP Quelle | Wärmemenge | Strommenge |
|---|---|---|
| Wärmepumpe | laut Wärmepumpe | laut Wärmepumpe |
| Gemessen (Strommesser) | Volumenstrom × Dichte × Wärmekapazität × (Vorlauf − Rücklauf) | externer Strommesser |

Dichte und Wärmekapazität von Wasser werden bei der mittleren Wassertemperatur aus Tabellenwerten bestimmt. Bei Glykol im Kreislauf stimmt der gemessene COP deshalb nicht.

Geräte der K/L-Serie und neuer melden genaue Leistungswerte (XTOP0 bis XTOP5), die dann verwendet werden. Ältere Geräte melden die Leistung nur im Raster von 200 W, der COP laut Wärmepumpe ist dort entsprechend grob. Welche Werte genutzt werden, steht im Attribut `werte` (XTOP oder TOP).

Der Strommesser muss ausschließlich die Wärmepumpe messen und in W, kW, mW oder MW melden.

Liegt der COP über der Carnot-Grenze (theoretischer Höchstwert aus Vorlauf- und Außentemperatur), ist er physikalisch unmöglich und wird als "unbekannt" angezeigt.

Attribute am Sensor: `quelle`, `waermemenge_kwh`, `strommenge_kwh`, `laufzeit_min`.

## Steuerung

Wichtig: Die HeishaMon-Platine antwortet auf jeden Befehl mit "OK", auch wenn sie einen Wert verwirft. Die Integration prüft deshalb jeden Wert vor dem Senden und zeigt einen Fehler in der Oberfläche, wenn er außerhalb des gültigen Bereichs liegt. Ist die Platine nicht erreichbar, erscheint ebenfalls ein Fehler.

### Einstellbare Werte

| Topic | Befehl | Bereich |
|---|---|---|
| TOP9 | SetDHWTemp | 40 bis 75 °C |
| TOP27, TOP34 | SetZ1/Z2HeatRequestTemperature | siehe Zonen |
| TOP28, TOP35 | SetZ1/Z2CoolRequestTemperature | siehe Zonen |
| TOP77 | SetHeatingOffOutdoorTemp | 5 bis 35 °C |
| TOP78 | SetHeaterOnOutdoorTemp | -15 bis 20 °C |
| TOP95 | SetMaxPumpDuty | 64 bis 254 |
| TOP23 | SetFloorHeatDelta | 1 bis 15 K |
| TOP24 | SetFloorCoolDelta | 1 bis 15 K |
| TOP22 | SetDHWHeatDelta | -12 bis -2 K |
| TOP113 | SetBufferDelta | 0 bis 10 K |
| TOP131 | SetBivalentStartTemp | -15 bis 35 °C |
| TOP134 | SetBivalentAPStartTemp | -15 bis 35 °C |
| TOP135 | SetBivalentAPStopTemp | -15 bis 35 °C |
| TOP70 | SetSterilizationTemp | 55 bis 75 °C |
| TOP71 | SetSterilizationMaxTime | 5 bis 60 min in 5er-Schritten |
| TOP96 | SetHeaterDelayTime (nur J-Serie) | 0 bis 254 min * |
| TOP97 | SetHeaterStartDelta (nur J-Serie) | -127 bis 127 K * |
| TOP98 | SetHeaterStopDelta (nur J-Serie) | -127 bis 127 K * |
| TOP29 bis TOP32, TOP72 bis TOP75, TOP82 bis TOP89 | SetCurves (Heiz- und Kühlkurven, Zone 1 und 2) | -127 bis 127 °C * |

\* Die HeishaMon-Doku nennt keinen Bereich. Die Grenzen sind die der Kodierung in der Firmware. Welche Werte die Wärmepumpe annimmt, ist nicht bekannt.

Jeder Kurvenpunkt wird einzeln gesendet. Die kleine HeishaMon-Platine (ESP8266) verarbeitet nur 128 Byte pro Anfrage, die ganze Kurve auf einmal passt nicht hinein.

### Zonen

Laut HeishaMon-Doku hängt der gültige Bereich davon ab, ob die Zone nach Heizkurve oder mit direkter Temperatur läuft. Das meldet die Wärmepumpe in TOP76 (Heizen) und TOP81 (Kühlen). Der Regler passt seinen Bereich daran an.

| | Heizkurve (Verschiebung) | Direkte Temperatur |
|---|---|---|
| Heizen | -5 bis 5 | 20 bis 75 °C |
| Kühlen | -5 bis 5 | 5 bis 20 °C |

Für direktes Heizen nennt die Doku "20 bis Maximum". 75 °C ist der höchste Wassersollwert, den HeishaMon dokumentiert. Das tatsächliche Maximum hängt vom Modell ab.

Laut HeishaMon-Doku lässt sich die direkte Temperatur im Thermostat- oder Fühlerbetrieb nicht über diese Werte setzen, sondern über den oberen Punkt der Heizkurve.

### Auswahllisten

| Befehl | Optionen |
|---|---|
| SetOperationMode | Heizen, Kühlen, Auto, Warmwasser, Heizen + Warmwasser, Kühlen + Warmwasser, Auto + Warmwasser |
| SetQuietMode | Aus, Stufe 1 bis 3 |
| SetPowerfulMode | Aus, 30, 60, 90 Minuten |
| SetZones | Zone 1, Zone 2, beide |
| SetExternalPadHeater | Aus, Typ A, Typ B |
| SetBivalentMode | Alternativ, Parallel, Erweitert parallel |
| SetHeatingControl | Komfort, Effizienz |
| SetSmartDHW | Variabel, Standard |
| SetQuietModePriority | Geräusch, Leistung |
| SetPumpFlowrateMode | Temperaturspreizung, Maximaler Durchfluss |
| SetDHWSensorSelection | Oben, Mitte (nur K/L-Serie All-in-One) |

Die Wärmepumpe meldet als Betriebsmodus auch "Auto (Kühlen)" und "Auto (Kühlen) + Warmwasser". Angezeigt werden sie als Auto bzw. Auto + Warmwasser.

### Schalter und Taster

17 Schalter, darunter Wärmepumpe ein/aus, Warmwasser erzwingen, Abtauen erzwingen, Legionellenschutz starten, Notheizung, Urlaubsmodus, Zeitprogramm, Pufferspeicher, externe Steuerungen, Bivalenz und die Heizstäbe für Raum und Warmwasser.

Der Taster "Fehler zurücksetzen" quittiert einen anstehenden Fehler der Wärmepumpe (etwa H72), wie die Reset-Taste an der Fernbedienung.

### Optional-Platine

Nur wenn in HeishaMon die Emulation der Optional-Platine aktiv ist. Laut HeishaMon-Doku ist sie experimentell, und die Wärmepumpe geht mit Fehler H74 in Bereitschaft, wenn die Platine etwa 40 Sekunden lang nicht sendet. Die Doku [OptionalPCB.md](https://github.com/heishamon/HeishaMon/blob/master/OptionalPCB.md) vorher lesen.

| Befehl | Art |
|---|---|
| SetSmartGridMode | Auswahl: Normal, Kapazität 1, Wärmepumpe und Warmwasser aus, Kapazität 2 |
| SetExternalThermostat1State, SetExternalThermostat2State | Auswahl: keine Anforderung, Kühlen, Heizen, beides |
| SetHeatCoolMode, SetCompressorState | Schalter |
| SetDemandControl | Wert 43 bis 234 (laut Doku 5 % bis 100 %) |
| SetPoolTemp, SetBufferTemp, SetZ1RoomTemp, SetZ1WaterTemp, SetZ2RoomTemp, SetZ2WaterTemp, SetSolarTemp | Temperatur -78 bis 120 °C |

Die Platine meldet diese Werte nicht zurück. Angezeigt wird der zuletzt gesetzte Wert, er bleibt nach einem Neustart erhalten. `SetOptPCBByte9` ist nicht eingebaut, die Doku beschreibt seine Bedeutung nicht.

## Bekannte Einschränkungen

- Die Zonen sind als Number und Select abgebildet, es gibt keine Climate-Entity.
- Der OpenTherm-Bereich der Platine wird nicht ausgewertet.
- Die Wertebereiche stammen aus der HeishaMon-Dokumentation und können je nach Wärmepumpenmodell abweichen.
- Die Optional-Platine-Befehle und die SmartGrid-Zuordnung sind nach der HeishaMon-Doku gebaut, aber nicht an einer Wärmepumpe getestet.
- Die Übersetzungen ins Französische und Japanische sind nicht von Muttersprachlern geprüft.

## Lizenz

MIT, 2026 Lutarym
