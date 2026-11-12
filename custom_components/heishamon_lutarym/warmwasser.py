"""Warmwasser zur waermsten Tageszeit laden.

Einmal am Tag wird die Warmwasserladung zu der Stunde erzwungen, fuer die
die Wettervorhersage die hoechste Aussentemperatur des Tages erwartet. Die
Waermepumpe arbeitet dann mit dem besten Wirkungsgrad.

Ablauf:
1. Die stuendliche Vorhersage der gewaehlten Wetter-Entity wird alle
   30 Minuten neu gelesen. Geplant wird die Stunde mit der hoechsten
   Temperatur von jetzt bis Tagesende. Ist heute schon erledigt oder
   bleibt heute keine Stunde mehr, wird der naechste Tag geplant, sofern
   die Vorhersage so weit reicht.
2. Ist diese Stunde erreicht und heute noch nicht geladen, wird
   SetForceDHW=1 gesendet. Vorher wird geprueft, ob der Betriebsmodus
   Warmwasser enthaelt (laut HeishaMon-Doku Voraussetzung) und ob der
   Speicher den Sollwert noch nicht erreicht hat.
3. Beendet wird die Ladung, sobald der Speicher den Sollwert erreicht,
   die Waermepumpe das Erzwingen selbst beendet oder die eingestellte
   Hoechstdauer abgelaufen ist. Dann wird SetForceDHW=0 gesendet, falls
   die Waermepumpe es noch meldet.

Die HeishaMon-Doku beschreibt nicht, ob die Waermepumpe beim Erzwingen
den Heizstab nutzt und ob sie selbst beim Sollwert aufhoert. Deshalb wird
das Ende hier ueberwacht und eine Hoechstdauer erzwungen.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import HeishamonBefehlFehler

_LOGGER = logging.getLogger(__name__)

PRUEF_TAKT = timedelta(minutes=1)
VORHERSAGE_TAKT = timedelta(minutes=30)
# So lange darf die Waermepumpe brauchen, bis sie das Erzwingen in TOP2
# zurueckmeldet. Danach gilt der Befehl als nicht angenommen.
ANNAHME_FRIST = timedelta(minutes=3)
# Ab so viel vor dem geplanten Start wird der Plan nicht mehr verschoben
FESTGELEGT_VOR = timedelta(minutes=60)
# Erst wenn eine andere Stunde um so viel waermer vorhergesagt wird, wird
# umgeplant. Verhindert das Hin und Her bei Zehntelgrad-Aenderungen.
UMPLANEN_AB_KELVIN = 0.5

# Betriebsmodi mit Warmwasser laut TOP4 (MQTT-Topics.md):
# 3 Warmwasser, 4 Heizen + WW, 5 Kuehlen + WW, 6 Auto + WW, 8 Auto (Kuehlen) + WW
MODI_MIT_WARMWASSER = {3, 4, 5, 6, 8}

# Statuswerte (Attribut "status" am Sensor)
GEPLANT = "geplant"
LAEUFT = "laeuft"
ERLEDIGT = "erledigt"
UEBERSPRUNGEN_VOLL = "uebersprungen_speicher_voll"
UEBERSPRUNGEN_MODUS = "uebersprungen_modus_ohne_warmwasser"
NICHT_ANGENOMMEN = "nicht_angenommen"
ABGEBROCHEN_DAUER = "beendet_hoechstdauer"
KEINE_VORHERSAGE = "keine_vorhersage"
AUS = "aus"
FEHLER = "fehler_befehl"
BEENDEN_FEHLT = "beenden_nicht_bestaetigt"


def _zahl(wert) -> float | None:
    if wert is None or isinstance(wert, bool):
        return None
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def _eintraege(vorhersage: list[dict[str, Any]]):
    """Liefert (Ortszeit, Temperatur) fuer alle lesbaren Eintraege."""
    for eintrag in vorhersage:
        zeit = eintrag.get("datetime")
        if isinstance(zeit, str):
            zeit = dt_util.parse_datetime(zeit)
        temperatur = _zahl(eintrag.get("temperature"))
        if zeit is None or temperatur is None:
            continue
        yield dt_util.as_local(zeit), temperatur


def temperatur_um(vorhersage: list[dict[str, Any]], zeit: datetime) -> float | None:
    """Vorhergesagte Temperatur fuer genau diese Stunde, sonst None."""
    for eintrag_zeit, temperatur in _eintraege(vorhersage):
        if eintrag_zeit == zeit:
            return temperatur
    return None


def waermste_stunde(
    vorhersage: list[dict[str, Any]], jetzt: datetime, tag: date | None = None
) -> tuple[datetime, float] | None:
    """Stunde mit der hoechsten Temperatur am angegebenen Tag (Standard heute).

    Fuer heute zaehlen nur Stunden ab der aktuellen Stunde. Bei gleicher
    Temperatur gilt die fruehere Stunde. Liefert Ortszeit.
    """
    heute = tag or dt_util.as_local(jetzt).date()
    stundenbeginn = dt_util.as_local(jetzt).replace(minute=0, second=0, microsecond=0)
    beste: tuple[datetime, float] | None = None
    for zeit, temperatur in _eintraege(vorhersage):
        if zeit.date() != heute or zeit < stundenbeginn:
            continue
        if beste is None or temperatur > beste[1]:
            beste = (zeit, temperatur)
    return beste


class WarmwasserPlaner:
    """Plant und steuert die taegliche Warmwasserladung."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        api,
        coordinator,
        wetter_entity: str,
        hoechstdauer_minuten: int,
    ) -> None:
        self.hass = hass
        self._api = api
        self._coordinator = coordinator
        self.wetter_entity = wetter_entity
        self.hoechstdauer = timedelta(minutes=hoechstdauer_minuten)
        self._store: Store = Store(hass, 1, f"heishamon_lutarym.warmwasser.{entry_id}")
        self._hoerer: list = []
        self._abmelden: list = []
        self._letzte_vorhersage: datetime | None = None
        self._beschaeftigt = False
        self._nochmal = False

        # Zustand
        self.aktiv = True
        self.geplant: datetime | None = None
        self.hoechsttemperatur: float | None = None
        self.status = AUS
        # Tag, an dem die Ladung erledigt wurde (auch uebersprungen)
        self.letzte_ladung: date | None = None
        # Start der letzten tatsaechlich erzwungenen Ladung
        self.letzter_start: datetime | None = None
        self.gestartet: datetime | None = None
        self.bestaetigt = False
        # Waehrend des Beendens: Zielstatus und Zeit des letzten Aus-Befehls
        self.ende_status: str | None = None
        self.ende_gesendet: datetime | None = None

    # ------------------------------------------------------------ Ablauf

    async def async_start(self) -> None:
        """Laedt den gespeicherten Zustand und startet die Zeitsteuerung."""
        gespeichert = await self._store.async_load() or {}
        self.aktiv = gespeichert.get("aktiv", True)
        if gespeichert.get("letzte_ladung"):
            self.letzte_ladung = date.fromisoformat(gespeichert["letzte_ladung"])
        if gespeichert.get("letzter_start"):
            self.letzter_start = dt_util.parse_datetime(gespeichert["letzter_start"])
        if gespeichert.get("geplant"):
            # Plan ueber einen Neustart retten. Sonst fehlt nach einem
            # Neustart in der geplanten Stunde diese Stunde in der Vorhersage.
            self.geplant = dt_util.parse_datetime(gespeichert["geplant"])
            self.hoechsttemperatur = gespeichert.get("hoechsttemperatur")
            if self.geplant is not None:
                self.geplant = dt_util.as_local(self.geplant)
                self.status = GEPLANT
        if gespeichert.get("gestartet"):
            # Home Assistant wurde waehrend einer Ladung neu gestartet:
            # weiter ueberwachen, damit sie sauber beendet wird.
            self.gestartet = dt_util.parse_datetime(gespeichert["gestartet"])
            self.bestaetigt = gespeichert.get("bestaetigt", False)
            self.status = LAEUFT
            if gespeichert.get("ende_status"):
                # Neustart waehrend des Beendens: Aus-Befehl sofort erneut senden
                self.ende_status = gespeichert["ende_status"]
        self._abmelden.append(
            async_track_time_interval(self.hass, self._takt, PRUEF_TAKT)
        )
        self._abmelden.append(self._coordinator.async_add_listener(self._neue_daten))
        await self.async_pruefen()

    async def async_stop(self) -> None:
        for abmelden in self._abmelden:
            abmelden()
        self._abmelden.clear()

    def abonnieren(self, hoerer):
        self._hoerer.append(hoerer)

        def abmelden() -> None:
            if hoerer in self._hoerer:
                self._hoerer.remove(hoerer)

        return abmelden

    def _melden(self) -> None:
        for hoerer in list(self._hoerer):
            hoerer()

    async def _speichern(self) -> None:
        await self._store.async_save(
            {
                "aktiv": self.aktiv,
                "letzte_ladung": self.letzte_ladung.isoformat() if self.letzte_ladung else None,
                "gestartet": self.gestartet.isoformat() if self.gestartet else None,
                "letzter_start": (
                    self.letzter_start.isoformat() if self.letzter_start else None
                ),
                "bestaetigt": self.bestaetigt,
                "ende_status": self.ende_status,
                "geplant": self.geplant.isoformat() if self.geplant else None,
                "hoechsttemperatur": self.hoechsttemperatur,
            }
        )

    async def async_setze_aktiv(self, aktiv: bool) -> None:
        """Schaltet die Funktion ein oder aus. Eine laufende Ladung wird beendet."""
        self.aktiv = aktiv
        if not aktiv and self.gestartet is not None:
            await self._beenden(AUS)
        await self._speichern()
        await self.async_pruefen()

    async def _takt(self, _jetzt) -> None:
        await self.async_pruefen()

    @callback
    def _neue_daten(self) -> None:
        # Das Ende einer Ladung schnell erkennen, nicht erst im Minutentakt
        if self.gestartet is not None:
            self.hass.async_create_task(self.async_pruefen())

    async def async_pruefen(self) -> None:
        """Ein Pruefschritt: Vorhersage, Start oder Ende einer Ladung."""
        if self._beschaeftigt:
            # Waehrend einer Pruefung eingetroffene Daten nicht verlieren
            self._nochmal = True
            return
        self._beschaeftigt = True
        try:
            while True:
                self._nochmal = False
                await self._schritt()
                if not self._nochmal:
                    break
        finally:
            self._beschaeftigt = False
        self._melden()

    async def _schritt(self) -> None:
        jetzt = dt_util.now()
        if self.gestartet is not None:
            await self._ueberwachen(jetzt)
            return
        if not self.aktiv:
            self.status = AUS
            return

        # Zuerst pruefen, ob die geplante Stunde erreicht ist. Erst danach
        # die Vorhersage lesen: Manche Wetterdienste (etwa Open-Meteo in Home
        # Assistant) lassen die laufende Stunde aus der Vorhersage fallen,
        # sobald sie begonnen hat. Ein Neulesen genau dann wuerde die
        # Ladung auf die naechste Stunde verschieben.
        if await self._faellig_starten(jetzt):
            return

        if (
            self._letzte_vorhersage is None
            or jetzt - self._letzte_vorhersage >= VORHERSAGE_TAKT
            or (self.geplant is not None and self.geplant.date() < jetzt.date())
            # Nach der heutigen Ladung sofort auf morgen umplanen
            or (
                self.letzte_ladung == jetzt.date()
                and self.geplant is not None
                and self.geplant.date() == jetzt.date()
            )
        ):
            await self._vorhersage_lesen(jetzt)

        await self._faellig_starten(jetzt)

    async def _faellig_starten(self, jetzt: datetime) -> bool:
        """Startet die Ladung, wenn die geplante Zeit heute erreicht ist."""
        if (
            self.geplant is None
            or self.letzte_ladung == jetzt.date()
            or self.geplant.date() != jetzt.date()
            or jetzt < self.geplant
        ):
            return False
        await self._starten(jetzt)
        return True

    async def _vorhersage_lesen(self, jetzt: datetime) -> None:
        self._letzte_vorhersage = jetzt
        try:
            antwort = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": self.wetter_entity, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
            vorhersage = antwort[self.wetter_entity]["forecast"]
        except (HomeAssistantError, KeyError, TypeError) as err:
            _LOGGER.warning(
                "Stuendliche Vorhersage von %s nicht lesbar: %s", self.wetter_entity, err
            )
            # Einen gueltigen Plan wegen eines Aussetzers nicht verwerfen
            if self.geplant is None or self.geplant.date() < jetzt.date():
                self.geplant = None
                self.hoechsttemperatur = None
                if self.letzte_ladung != jetzt.date():
                    self.status = KEINE_VORHERSAGE
            return
        heute = jetzt.date()
        beste = None
        if self.letzte_ladung != heute:
            beste = waermste_stunde(vorhersage, jetzt)
        if beste is None:
            # Heute erledigt oder keine Stunde mehr uebrig: morgen planen
            beste = waermste_stunde(vorhersage, jetzt, heute + timedelta(days=1))
        if beste is None:
            # Vorhersage reicht nicht bis morgen
            self.geplant = None
            self.hoechsttemperatur = None
            await self._speichern()
            return
        alt = self.geplant
        if alt is not None and alt.date() == beste[0].date() and alt >= jetzt:
            if alt - jetzt <= FESTGELEGT_VOR:
                # Kurz vor dem Start: Plan bleibt fest
                return
            alt_temperatur = temperatur_um(vorhersage, alt)
            if (
                alt_temperatur is not None
                and beste[1] < alt_temperatur + UMPLANEN_AB_KELVIN
            ):
                # Neue Stunde nicht deutlich waermer: Plan behalten
                self.hoechsttemperatur = alt_temperatur
                return
        self.geplant, self.hoechsttemperatur = beste
        await self._speichern()
        if self.letzte_ladung != heute:
            self.status = GEPLANT

    async def _starten(self, jetzt: datetime) -> None:
        data = self._coordinator.data or {}
        heute = jetzt.date()
        modus = _zahl(data.get("TOP4"))
        if modus is None or int(modus) not in MODI_MIT_WARMWASSER:
            # Laut HeishaMon-Doku wirkt SetForceDHW nur mit Warmwasser im Modus
            self.status = UEBERSPRUNGEN_MODUS
            self.letzte_ladung = heute
            await self._speichern()
            return
        ist = _zahl(data.get("TOP10"))
        soll = _zahl(data.get("TOP9"))
        if ist is not None and soll is not None and ist >= soll:
            self.status = UEBERSPRUNGEN_VOLL
            self.letzte_ladung = heute
            await self._speichern()
            return
        try:
            await self._api.async_set_value("SetForceDHW", 1)
        except HeishamonBefehlFehler as err:
            _LOGGER.warning("Warmwasser erzwingen fehlgeschlagen: %s", err)
            self.status = FEHLER
            return  # naechster Versuch im naechsten Takt
        self.gestartet = jetzt
        self.letzter_start = jetzt
        self.bestaetigt = False
        self.letzte_ladung = heute
        self.status = LAEUFT
        await self._speichern()
        await self._coordinator.async_request_refresh()

    async def _ueberwachen(self, jetzt: datetime) -> None:
        if self.ende_status is not None:
            await self._beenden_pruefen(jetzt)
            return
        data = self._coordinator.data or {}
        erzwungen = _zahl(data.get("TOP2"))
        ist = _zahl(data.get("TOP10"))
        soll = _zahl(data.get("TOP9"))

        if erzwungen is not None and erzwungen > 0:
            self.bestaetigt = True

        if not self.bestaetigt:
            if jetzt - self.gestartet >= ANNAHME_FRIST:
                await self._beenden(NICHT_ANGENOMMEN)
            return
        if erzwungen is not None and erzwungen == 0:
            # Die Waermepumpe hat das Erzwingen selbst beendet
            await self._beenden(ERLEDIGT)
            return
        if ist is not None and soll is not None and ist >= soll:
            await self._beenden(ERLEDIGT)
            return
        if jetzt - self.gestartet >= self.hoechstdauer:
            await self._beenden(ABGEBROCHEN_DAUER)

    async def _beenden(self, status: str) -> None:
        """Beendet das Erzwingen und prueft danach, ob es wirklich aus ist.

        HeishaMon bestaetigt jeden Befehl, auch wenn die Waermepumpe ihn
        nicht umsetzt. Deshalb gilt die Ladung erst als beendet, wenn TOP2
        wieder 0 meldet. Bis dahin wird der Aus-Befehl wiederholt.
        """
        self.ende_status = status
        self.ende_gesendet = None
        await self._beenden_pruefen(dt_util.now())

    async def _beenden_pruefen(self, jetzt: datetime) -> None:
        erzwungen = _zahl((self._coordinator.data or {}).get("TOP2"))
        if erzwungen is not None and erzwungen == 0:
            self.gestartet = None
            self.bestaetigt = False
            self.status = self.ende_status
            self.ende_status = None
            self.ende_gesendet = None
            await self._speichern()
            return
        if self.ende_gesendet is not None and jetzt - self.ende_gesendet < ANNAHME_FRIST:
            return  # Rueckmeldung abwarten
        if self.ende_gesendet is not None:
            # Aus-Befehl wurde nicht umgesetzt: sichtbar machen und wiederholen
            _LOGGER.warning(
                "Waermepumpe meldet nach SetForceDHW=0 weiter erzwungenes Warmwasser, "
                "sende erneut"
            )
            self.status = BEENDEN_FEHLT
        try:
            await self._api.async_set_value("SetForceDHW", 0)
        except HeishamonBefehlFehler as err:
            _LOGGER.warning("Erzwungenes Warmwasser nicht beendbar: %s", err)
            self.status = BEENDEN_FEHLT
            return  # naechster Versuch im naechsten Takt
        self.ende_gesendet = jetzt
        await self._speichern()
        await self._coordinator.async_request_refresh()
