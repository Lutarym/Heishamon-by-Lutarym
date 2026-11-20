# Heishamon by Lutarym

[English](README.md) · **Deutsch** · [Français](README.fr.md) · [日本語](README.ja.md)

Home Assistant Integration für Panasonic Aquarea Wärmepumpen über HeishaMon, ohne MQTT, direkt über die HTTP-Schnittstelle.

Version 1.7.0

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
| Wetter-Entity | optional, für „Warmwasser zur wärmsten Tageszeit“, nur über „Konfigurieren“ einstellbar |
| Höchstdauer der Ladung | für die erzwungene Warmwasserladung, Minuten, Standard 120, Bereich 15 bis 240 |
| Frühester und spätester Start | Zeitfenster für den Start der Warmwasserladung, volle Stunden, Standard 11 bis 17 Uhr, die späteste Stunde zählt noch mit |

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

## Werte ab Firmware 4.3.0

HeishaMon 4.3.0 hat 55 Werte aus dem Installateurmenü und Ist-Zustände (TOP144 bis TOP198) sowie fünf Befehle hinzugefügt. Die Integration legt die neuen Sensoren nur an, wenn die Platine sie liefert. Die neuen Befehle erscheinen nur bei Firmware 4.3.0 oder neuer, weil ältere Firmware jeden Befehl mit HTTP 200 beantwortet, unbekannte aber ignoriert.

| Befehl | Entity | Bereich (aus HeishaMon commands.h) |
|---|---|---|
| SetRoomOperationMaxTime | TOP158 Heizbetrieb maximale Zeit | 30 bis 7620 Minuten, in 30er-Schritten |
| SetDHWHeatupMaxTime | TOP159 Warmwasser maximale Ladezeit | 1 bis 254 Minuten |
| SetHeatToCoolTemp | TOP79 | -127 bis 127 °C |
| SetCoolToHeatTemp | TOP80 | -127 bis 127 °C |
| SetQuietModeSchedule | Schalter „Leisebetrieb per Zeitplan“, Zustand TOP3 | ein, aus |

Wichtige neue Werte: TOP158 und TOP159 (Umschaltung zwischen Heizen und Warmwasser), SG-Ready-Einstellungen (TOP149, TOP154 bis TOP157, TOP184 bis TOP192), Fühlerkorrekturen (TOP177, TOP178, TOP193, TOP195, TOP196), Nennleistung und T-CAP (TOP197, TOP198). Sind in HeishaMon Topic-Gruppen abgeschaltet, fehlen die passenden Entities.

## Betriebsanalyse

Immer aktiv, auch im Nur-lesen-Modus. Den Strom liefert der externe Strommesser, wenn eingestellt, sonst die Werte der Wärmepumpe. Aufbewahrt werden 8 Wochen. Zu jedem Wert steht, was er bedeutet und was man damit anfangen kann.

| Entity | Was sie zeigt | Was man damit anfängt |
|---|---|---|
| Verdichterstarts 24 h | wie oft der Verdichter in den letzten 24 Stunden gestartet ist. Attribute: Starts pro Tag über 7 Tage, längster Lauf, Starts für Warmwasser, Zähler der Wärmepumpe (TOP12) | Jeder Start kostet Effizienz und Verschleiß. Viele Starts am Tag sind ein Zeichen, dass die Wärmepumpe mehr Wärme liefert, als das Haus abnimmt, zum Beispiel weil die Heizkurve zu hoch oder der Durchfluss zu klein ist. |
| Mittlere Laufzeit je Start | wie lange ein Verdichterlauf im Mittel dauert | Lange Läufe sind besser als viele kurze. |
| Kurze Verdichterläufe 24 h | Läufe unter 10 Minuten | Ist die Zahl hoch, Heizkurve, Hysterese und Puffer prüfen. |
| COP letzte Warmwasserladung | Wärme geteilt durch Strom der letzten Ladung. Attribute: Start, Dauer, Außentemperatur, kWh, PV-Anteil | Je höher, desto günstiger das Warmwasser. |
| Effizienteste Warmwasser-Startstunde | Startstunde mit dem besten mittleren COP (mindestens 2 Ladungen). Attribute: COP je Startstunde und je Außentemperatur | Zeigt mit deinen eigenen Daten, ob sich die Ladung zur wärmsten Stunde lohnt. |
| Kosten letzte Warmwasserladung, Warmwasserkosten pro Tag | Strom mal Preis (Option „Strompreis“). Mit Netzbezug-Sensor zählt nur der Strom aus dem Netz | Grundlage für Entscheidungen wie eine niedrigere Speichertemperatur. |
| Abtauvorgänge 24 h | Anzahl, Dauer und Strom der Abtauvorgänge. Attribut: Anzahl der letzten 7 Tage je Außentemperatur | Abtauen ist bei feuchter Kälte normal. Häufen sich Abtauvorgänge bei einer Temperatur, bei der es vorher nicht so war, die Außeneinheit prüfen (freie Luftführung, Eis). |
| Vorlauf über Soll | um wie viel Grad der Vorlauf beim Heizen über seinem Soll liegt (7 Tage). Attribut: Ist- und Soll-Vorlauf je Außentemperatur | Zeigt, wie sich die Heizkurve verhält. Jedes Grad weniger Vorlauf verbessert die Effizienz. Bleiben die Räume warm genug, kann die Kurve schrittweise abgesenkt werden. |
| Spreizung Heizen, Spreizung Warmwasser | Unterschied zwischen Vor- und Rücklauf bei laufendem Verdichter (7 Tage), mit Durchfluss | Eine deutlich zu kleine oder zu große Spreizung deutet auf eine unpassende Pumpeneinstellung hin. Änderungen mit dem Installateur besprechen. |
| PV-Anteil Wärmepumpe heute | Anteil des Wärmepumpenstroms, der nicht aus dem Netz kam (PV oder Batterie). Braucht die Option „Netzbezug-Sensor“. Attribut: 7 Tage | Grundlage, um Ladungen auf PV-Überschuss zu legen. |
| Heizstab Laufzeit heute | Minuten mit aktivem Heizstab (TOP60 oder TOP61). Attribute: zuletzt aktiv, 7 Tage, Betriebsstunden Heizstab Warmwasser (TOP91) | Bei jedem Einschalten des Heizstabs zeigt Home Assistant eine Benachrichtigung. |

Neue Optionen unter „Konfigurieren“:

| Option | Bedeutung |
|---|---|
| Netzbezug-Sensor | Leistung aus dem Netz, positiv = Bezug, negativ = Einspeisung. Nötig für den PV-Anteil |
| Strompreis | Cent je kWh, 0 = keine Kostenberechnung |

## Warmwasser-Auswertung

Immer aktiv, auch im Nur-lesen-Modus. Grundlage sind TOP10 (Speichertemperatur), TOP20 (Dreiwegeventil, 1 = Warmwasser), TOP2 (Zwangsladung) und TOP9 (Sollwert). Beim Start übernimmt die Integration ältere Daten aus dem Verlauf von Home Assistant (meist 10 Tage), danach sammelt sie selbst. Aufbewahrt werden 8 Wochen.

| Entity | Bedeutung |
|---|---|
| Warmwasserladungen 24 h | Anzahl der Ladungen in den letzten 24 Stunden. Attribute: davon erzwungen, gesamt, typische Ladedauer, Daten ab |
| Haltedauer letzte volle Ladung | Stunden vom Ende der letzten vollen Ladung bis zum Start der nächsten regulären Ladung. Attribute: Ladetemperatur, Nachladetemperatur, Zeiten |
| Haltedauer Durchschnitt | Mittel über alle ausgewerteten Zeiträume. Attribute: Median, Anzahl, mittlere Haltedauer je Ladetemperatur, mittlere Nachladetemperatur |
| Nachladetemperatur Warmwasser | Speichertemperatur beim Start der letzten regulären Ladung |
| Optimaler Ladezeitpunkt Montag bis Sonntag | 7 Entities, empfohlener Ladestart je Wochentag |

Begriffe:
- Ladung: Das Dreiwegeventil steht auf Warmwasser. Unterbrechungen unter 10 Minuten (zum Beispiel Abtauen) zählen als eine Ladung.
- Volle Ladung: Die Speichertemperatur erreicht den Sollwert.
- Haltedauer: vom Ende einer vollen Ladung bis zur nächsten regulären Ladung (keine Zwangsladung). Ist die nächste Ladung eine Zwangsladung, wird der Zeitraum nicht gewertet, weil die Wärmepumpe von selbst noch nicht nachgeladen hätte.
- Verbrauch: Abfall der Speichertemperatur außerhalb von Ladungen. Die erste Stunde nach einer Ladung zählt nicht, der Speicher durchmischt sich dann noch.

Optimaler Ladezeitpunkt: Die Ladung soll kurz vor dem Hauptverbrauch des Wochentags fertig sein, unabhängig von der Außentemperatur. Hauptverbrauch sind die zwei aufeinanderfolgenden Stunden mit dem größten durchschnittlichen Verbrauch an diesem Wochentag. Ladestart = Beginn des Hauptverbrauchs minus typische Ladedauer (Median der vollen Ladungen), abgerundet auf 15 Minuten. Nötig sind mindestens 2 ausgewertete Tage dieses Wochentags und 1 K Verbrauch, sonst ist der Wert unbekannt. Das Attribut `verbrauch_k_je_stunde` zeigt den mittleren Verbrauch je Stunde in Kelvin. Die Tagesladung wird dadurch nicht verändert, der Wert dient nur zur Anzeige.

## Prüfung auf Firmware-Updates

Die Entity „Firmware“ (`update.heishamon_<IP>_firmware`) zeigt die installierte HeishaMon-Firmware und die neueste Produktionsversion. Geprüft wird alle 6 Stunden.

- Installiert: gelesen von der Startseite des HeishaMon.
- Neueste: Die HeishaMon-Entwickler markieren alle GitHub-Releases als Vorabversion. Die gültige Produktionsversion wird deshalb aus dem Satz „The latest production release is ...“ in [binaries/README.md](https://github.com/heishamon/HeishaMon/tree/main/binaries) gelesen, den das Projekt bei jeder Veröffentlichung pflegt.
- Nightly-, Alpha- oder selbst gebaute Firmware hat keine vergleichbare Versionsnummer und löst keine Update-Meldung aus.
- Die Integration installiert nichts. Die Firmware ist für die kleine Platine (ESP8266) und die große Platine (ESP32-S3) verschieden, eine falsche Datei macht die Platine unbrauchbar. Aktualisieren über die Weboberfläche von HeishaMon (Menü Firmware) mit der Datei für deine Platine.

## Warmwasser zur wärmsten Tageszeit

Optional. Oft hält das Warmwasser 24 Stunden oder länger, und die Wärmepumpe lädt zu einer kalten Zeit nach, zum Beispiel nachts. Diese Funktion erzwingt die Ladung einmal am Tag zu der Stunde mit der höchsten Außentemperatur. Die Wärmepumpe arbeitet dann mit besserem Wirkungsgrad.

Einrichtung: unter „Konfigurieren“ eine Wetter-Entity mit stündlicher Vorhersage wählen. Die Integration erkennt vorhandene Wetter-Entities mit stündlicher Vorhersage, listet sie im Dialog auf und schlägt eine vor, Met.no bevorzugt. Wird keine gefunden, zuerst eine Wetter-Integration hinzufügen, zum Beispiel „Meteorologisk institutt (Met.no)“, die den Standort von Home Assistant nutzt. Funktioniert nur mit Steuerung (Nur lesen aus).

Ablauf:

1. Alle 30 Minuten wird die stündliche Vorhersage gelesen. Geplant wird die Stunde mit der höchsten Temperatur innerhalb des Zeitfensters (Standard 11 bis 17 Uhr), ab jetzt. So bleibt der Abstand zwischen zwei Ladungen etwa gleich, auch wenn die wärmste Stunde eines Tages spät am Abend liegt. Haben zwei Stunden die gleiche Temperatur, gilt die frühere. Ist die heutige Ladung erledigt oder ist das Zeitfenster für heute vorbei, wird der nächste Tag geplant, sofern die Vorhersage so weit reicht. Auf eine andere Stunde wird nur umgeplant, wenn diese mindestens 0,5 °C wärmer vorhergesagt wird. Ab 60 Minuten vor dem geplanten Start steht der Plan fest.
2. Zur geplanten Stunde wird „Warmwasser erzwingen“ (`SetForceDHW`) eingeschaltet, einmal am Tag. Vorher wird geprüft:
   - Enthält der Betriebsmodus Warmwasser? Laut HeishaMon-Doku wirkt das Erzwingen nur dann. Wenn nicht, wird der Tag übersprungen.
   - Liegt der Speicher unter dem Sollwert? Wenn nicht, wird der Tag übersprungen.
3. Die Wärmepumpe beendet das Erzwingen selbst, sobald der Speicher ihre Abschalttemperatur erreicht. Laut Panasonic-Service-Anleitung ist das ohne Heizstab Sollwert + 1 °C für 20 Sekunden. Die Integration unterbricht die Ladung nicht. Sie schaltet das Erzwingen nur aus, wenn die Höchstdauer abgelaufen ist oder der Schalter ausgeschaltet wird. Als beendet gilt die Ladung erst, wenn die Wärmepumpe das Erzwingen als aus meldet. Bis dahin wird der Aus-Befehl alle 3 Minuten wiederholt.
4. Meldet die Wärmepumpe das Erzwingen nicht innerhalb von 3 Minuten zurück, gilt der Versuch als nicht angenommen.

Entities:

| Entity | Bedeutung |
|---|---|
| Schalter „Warmwasser zur wärmsten Tageszeit“ | schaltet die Funktion ein oder aus. Aus beendet eine laufende Ladung. Bleibt nach einem Neustart erhalten |
| Sensor „Geplante Warmwasserladung“ | geplantes Datum und Uhrzeit, nach der heutigen Ladung schon die von morgen. Attribute: Status, Höchsttemperatur, Tag erledigt, Start, Höchstdauer, Wetter-Entity |
| Sensor „Letzte Warmwasserladung“ | Datum und Uhrzeit des Starts der letzten erzwungenen Ladung. Bleibt nach einem Neustart erhalten |

Werte des Attributs `status`: `geplant`, `laeuft`, `erledigt`, `uebersprungen_speicher_voll`, `uebersprungen_modus_ohne_warmwasser`, `nicht_angenommen`, `beendet_hoechstdauer`, `keine_vorhersage`, `aus`, `fehler_befehl` (Befehl fehlgeschlagen, wird jede Minute wiederholt), `beenden_nicht_bestaetigt` (Wärmepumpe meldet nach dem Aus-Befehl weiter Erzwingen, wird alle 3 Minuten wiederholt).

Hinweis: Die HeishaMon-Doku sagt nicht, ob die Wärmepumpe beim Erzwingen von Warmwasser den Heizstab nutzt. Bitte an der eigenen Anlage prüfen. Deshalb wird das Ende der Ladung überwacht und durch die Höchstdauer begrenzt.

## Bekannte Einschränkungen

- Die Zonen sind als Number und Select abgebildet, es gibt keine Climate-Entity.
- Der OpenTherm-Bereich der Platine wird nicht ausgewertet.
- Die Wertebereiche stammen aus der HeishaMon-Dokumentation und können je nach Wärmepumpenmodell abweichen.
- Die Optional-Platine-Befehle und die SmartGrid-Zuordnung sind nach der HeishaMon-Doku gebaut, aber nicht an einer Wärmepumpe getestet.
- Die Übersetzungen ins Französische und Japanische sind nicht von Muttersprachlern geprüft.
- „Warmwasser zur wärmsten Tageszeit“ ist mit simulierten Daten getestet, noch nicht an einer Wärmepumpe.

## Lizenz

MIT, 2026 Lutarym
