"""Auswertung des Warmwasserspeichers.

Grundlage sind vier Werte der Waermepumpe:
TOP10 Speichertemperatur, TOP20 Dreiwegeventil (1 = Warmwasser),
TOP2 Zwangsladung, TOP9 Warmwasser-Sollwert.

Gespeichert wird jede Aenderung eines dieser Werte (Probe). Beim Start
werden aeltere Daten aus dem Verlauf von Home Assistant uebernommen,
danach sammelt die Integration selbst. Aufbewahrt werden 8 Wochen.

Begriffe:
- Ladung: Zeitraum, in dem das Dreiwegeventil auf Warmwasser steht.
- Volle Ladung: Die Speichertemperatur erreicht dabei den Sollwert.
- Haltedauer: Zeit vom Ende einer vollen Ladung bis zum Start der
  naechsten regulaeren Ladung (also keiner Zwangsladung). Endet der
  Zeitraum mit einer Zwangsladung, wird er nicht gewertet, weil die
  Waermepumpe von selbst noch nicht nachgeladen haette.
- Nachladetemperatur: Speichertemperatur beim Start dieser regulaeren
  Ladung.
- Verbrauch: Temperaturabfall des Speichers ausserhalb von Ladungen. Die
  erste Stunde nach einer Ladung zaehlt nicht, weil sich der Speicher dann
  noch durchmischt.
- Optimaler Ladezeitpunkt je Wochentag: Die Ladung soll kurz vor dem
  Hauptverbrauch fertig sein. Hauptverbrauch sind die zwei
  aufeinanderfolgenden Stunden mit dem groessten durchschnittlichen
  Verbrauch an diesem Wochentag. Er beginnt mit der ersten dieser beiden
  Stunden, die mindestens ein Viertel davon ausmacht. Ladestart = Beginn des Hauptverbrauchs
  minus typische Ladedauer (Median der vollen Ladungen).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

AUFBEWAHREN = timedelta(weeks=8)
NEU_RECHNEN = timedelta(minutes=15)
SPEICHER_VERZOEGERUNG = 600  # Sekunden
LADUNGEN_ZUSAMMENFASSEN = 10 * 60  # Unterbrechung kuerzer als 10 min
NACHLAUF_MAXIMUM = 45 * 60  # Temperaturspitze nach Ladungsende
MISCHZEIT = 60 * 60  # nach einer Ladung kein Verbrauch zaehlen
STANDARD_LADEDAUER_MIN = 30
MIN_TAGE = 2
MIN_VERBRAUCH_K = 1.0
TOPICS = ("TOP10", "TOP20", "TOP2", "TOP9")

# Probe: [Zeit (Unix-Sekunden), TOP10, TOP20, TOP2, TOP9]
Probe = list


def _zahl(wert: Any) -> float | None:
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def ladungen_finden(proben: list[Probe]) -> list[dict]:
    """Findet abgeschlossene Ladungen (Dreiwegeventil auf Warmwasser)."""
    roh: list[dict] = []
    aktiv: dict | None = None
    vorher_t10: float | None = None
    for zeit, t10, t20, t2, t9 in proben:
        if t20 == 1:
            if aktiv is None:
                aktiv = {
                    "start": zeit,
                    # Beim Umschalten ist der Speicher noch nicht erwaermt
                    "t_start": t10 if t10 is not None else vorher_t10,
                    "erzwungen": t2 == 1,
                }
            elif t2 == 1:
                aktiv["erzwungen"] = True
        elif t20 is not None and aktiv is not None:
            aktiv["ende"] = zeit
            aktiv["soll"] = t9
            roh.append(aktiv)
            aktiv = None
        if t10 is not None:
            vorher_t10 = t10

    # Kurze Unterbrechungen (etwa Abtauen) gehoeren zur selben Ladung
    ladungen: list[dict] = []
    for ladung in roh:
        if ladungen and ladung["start"] - ladungen[-1]["ende"] < LADUNGEN_ZUSAMMENFASSEN:
            vorige = ladungen[-1]
            vorige["ende"] = ladung["ende"]
            vorige["erzwungen"] = vorige["erzwungen"] or ladung["erzwungen"]
            vorige["soll"] = ladung["soll"] if ladung["soll"] is not None else vorige["soll"]
        else:
            ladungen.append(dict(ladung))

    # Hoechste Temperatur waehrend der Ladung und kurz danach
    i = 0
    for ladung in ladungen:
        while i < len(proben) and proben[i][0] < ladung["start"]:
            i += 1
        j = i
        t_max = None
        while j < len(proben) and proben[j][0] <= ladung["ende"] + NACHLAUF_MAXIMUM:
            t10 = proben[j][1]
            if t10 is not None and (t_max is None or t10 > t_max):
                t_max = t10
            j += 1
        ladung["t_max"] = t_max
        ladung["voll"] = (
            t_max is not None and ladung["soll"] is not None and t_max >= ladung["soll"]
        )
        ladung["dauer_min"] = (ladung["ende"] - ladung["start"]) / 60
    return ladungen


def haltedauern(ladungen: list[dict]) -> list[dict]:
    """Haltedauer von voller Ladung bis zur naechsten regulaeren Ladung."""
    ergebnis = []
    for a, b in zip(ladungen, ladungen[1:]):
        if not a["voll"] or b["erzwungen"]:
            continue
        ergebnis.append(
            {
                "ende_ladung": a["ende"],
                "start_naechste": b["start"],
                "stunden": (b["start"] - a["ende"]) / 3600,
                "ladetemperatur": a["t_max"],
                "nachladetemperatur": b["t_start"],
            }
        )
    return ergebnis


def verbrauch_je_tag(proben: list[Probe], ladungen: list[dict]) -> dict[str, list[float]]:
    """Temperaturabfall ausserhalb von Ladungen je Ortsdatum und Stunde."""
    sperren = [(l["start"], l["ende"] + MISCHZEIT) for l in ladungen]
    tage: dict[str, list[float]] = {}
    k = 0
    vorher = None
    for probe in proben:
        zeit, t10, t20 = probe[0], probe[1], probe[2]
        if t10 is None:
            continue
        if vorher is not None and t10 < vorher[1] and t20 != 1:
            while k < len(sperren) and sperren[k][1] < zeit:
                k += 1
            gesperrt = k < len(sperren) and sperren[k][0] <= zeit <= sperren[k][1]
            if not gesperrt:
                ort = dt_util.as_local(dt_util.utc_from_timestamp(zeit))
                tag = tage.setdefault(ort.date().isoformat(), [0.0] * 24)
                tag[ort.hour] += vorher[1] - t10
        vorher = (zeit, t10)
    return tage


def vollstaendige_tage(proben: list[Probe]) -> set[str]:
    """Ortsdaten, die vollstaendig im Datenbereich liegen."""
    if len(proben) < 2:
        return set()
    erste = dt_util.as_local(dt_util.utc_from_timestamp(proben[0][0]))
    letzte = dt_util.as_local(dt_util.utc_from_timestamp(proben[-1][0]))
    tage = set()
    tag = erste.date() + timedelta(days=1)
    while tag < letzte.date():
        tage.add(tag.isoformat())
        tag += timedelta(days=1)
    return tage


def optimale_zeiten(
    tage_verbrauch: dict[str, list[float]], gueltig: set[str], ladedauer_min: float
) -> dict[int, dict]:
    """Optimaler Ladestart je Wochentag (0 = Montag)."""
    from datetime import date

    je_wochentag: dict[int, list[list[float]]] = {w: [] for w in range(7)}
    for tag in gueltig:
        werte = tage_verbrauch.get(tag, [0.0] * 24)
        je_wochentag[date.fromisoformat(tag).weekday()].append(werte)

    ergebnis: dict[int, dict] = {}
    for wochentag, liste in je_wochentag.items():
        eintrag: dict[str, Any] = {"tage": len(liste), "zeit": None}
        if liste:
            schnitt = [round(mean(t[h] for t in liste), 2) for h in range(24)]
            eintrag["verbrauch"] = schnitt
            if len(liste) >= MIN_TAGE:
                summen = [schnitt[h] + schnitt[h + 1] for h in range(23)]
                beste = max(range(23), key=lambda h: summen[h])
                if summen[beste] >= MIN_VERBRAUCH_K:
                    # Faellt in der ersten Stunde des Fensters kaum etwas an,
                    # beginnt der Hauptverbrauch erst in der zweiten.
                    if schnitt[beste] < 0.25 * summen[beste]:
                        beste += 1
                    start = (beste * 60 - int(ladedauer_min)) % 1440
                    start -= start % 15
                    eintrag["zeit"] = f"{start // 60:02d}:{start % 60:02d}"
                    eintrag["hauptverbrauch_ab"] = f"{beste:02d}:00"
                    eintrag["verbrauch_hauptzeit_k"] = round(summen[beste], 2)
        ergebnis[wochentag] = eintrag
    return ergebnis


def auswerten(proben: list[Probe], jetzt: datetime) -> dict:
    """Berechnet alle Kennzahlen aus den Proben."""
    ladungen = ladungen_finden(proben)
    jetzt_ts = jetzt.timestamp()
    letzte_24h = [l for l in ladungen if l["ende"] >= jetzt_ts - 86400]
    volle = [l for l in ladungen if l["voll"]]
    ladedauer = (
        median(l["dauer_min"] for l in volle) if volle else STANDARD_LADEDAUER_MIN
    )

    halten = haltedauern(ladungen)
    je_temp: dict[str, list[float]] = {}
    for h in halten:
        if h["ladetemperatur"] is not None:
            je_temp.setdefault(f"{h['ladetemperatur']:g}", []).append(h["stunden"])
    nachlade = [h["nachladetemperatur"] for h in halten if h["nachladetemperatur"] is not None]

    def zeit(ts: float) -> str:
        return dt_util.as_local(dt_util.utc_from_timestamp(ts)).isoformat(timespec="minutes")

    letzte_halte = halten[-1] if halten else None
    return {
        "ladungen_24h": len(letzte_24h),
        "erzwungen_24h": sum(1 for l in letzte_24h if l["erzwungen"]),
        "ladungen_gesamt": len(ladungen),
        "ladedauer_min": round(ladedauer),
        "letzte_haltedauer": None
        if letzte_halte is None
        else {
            "stunden": round(letzte_halte["stunden"], 1),
            "ladetemperatur": letzte_halte["ladetemperatur"],
            "nachladetemperatur": letzte_halte["nachladetemperatur"],
            "ende_ladung": zeit(letzte_halte["ende_ladung"]),
            "start_naechste": zeit(letzte_halte["start_naechste"]),
        },
        "haltedauer_mittel": round(mean(h["stunden"] for h in halten), 1) if halten else None,
        "haltedauer_median": round(median(h["stunden"] for h in halten), 1) if halten else None,
        "haltedauer_anzahl": len(halten),
        "haltedauer_je_ladetemperatur": {
            f"{k} °C": round(mean(v), 1) for k, v in sorted(je_temp.items())
        },
        "nachladetemperatur_letzte": nachlade[-1] if nachlade else None,
        "nachladetemperatur_mittel": round(mean(nachlade), 1) if nachlade else None,
        "optimal": optimale_zeiten(
            verbrauch_je_tag(proben, ladungen), vollstaendige_tage(proben), ladedauer
        ),
        "daten_ab": zeit(proben[0][0]) if proben else None,
    }


class Warmwasserstatistik:
    """Sammelt die Proben, speichert sie und haelt die Auswertung aktuell."""

    def __init__(self, hass: HomeAssistant, entry_id: str, coordinator, kennung: str) -> None:
        self.hass = hass
        self._coordinator = coordinator
        self._kennung = kennung
        self._store: Store = Store(hass, 1, f"{DOMAIN}.statistik.{entry_id}")
        self.proben: list[Probe] = []
        self.ergebnis: dict = auswerten([], dt_util.now())
        self._hoerer: list[Callable[[], None]] = []
        self._abmelden: list[Callable[[], None]] = []
        self._zuletzt_gerechnet: datetime | None = None

    async def async_start(self) -> None:
        gespeichert = await self._store.async_load() or {}
        self.proben = [list(p) for p in gespeichert.get("proben", [])]
        self._abmelden.append(self._coordinator.async_add_listener(self._neue_daten))
        self._abmelden.append(
            async_track_time_interval(self.hass, self._takt, NEU_RECHNEN)
        )
        self._neu_rechnen()
        # Verlauf aus Home Assistant im Hintergrund uebernehmen
        self.hass.async_create_background_task(
            self._verlauf_uebernehmen(), f"heishamon_statistik_{self._kennung}"
        )

    async def async_stop(self) -> None:
        for abmelden in self._abmelden:
            abmelden()
        self._abmelden.clear()
        await self._store.async_save(self._daten_zum_speichern())

    def abonnieren(self, hoerer: Callable[[], None]) -> Callable[[], None]:
        self._hoerer.append(hoerer)
        return lambda: self._hoerer.remove(hoerer)

    def _daten_zum_speichern(self) -> dict:
        return {"proben": self.proben}

    @callback
    def _neue_daten(self) -> None:
        data = self._coordinator.data or {}
        probe = [dt_util.utcnow().timestamp()] + [_zahl(data.get(t)) for t in TOPICS]
        if self.proben and self.proben[-1][1:] == probe[1:]:
            return
        if all(wert is None for wert in probe[1:]):
            return
        self.proben.append(probe)
        self._store.async_delay_save(self._daten_zum_speichern, SPEICHER_VERZOEGERUNG)
        # Ladungsbeginn und Ladungsende sofort auswerten, sonst hoechstens
        # alle 5 Minuten
        wechsel = len(self.proben) > 1 and self.proben[-2][2] != probe[2]
        if (
            wechsel
            or self._zuletzt_gerechnet is None
            or dt_util.utcnow() - self._zuletzt_gerechnet > timedelta(minutes=5)
        ):
            self._neu_rechnen()

    @callback
    def _takt(self, _jetzt=None) -> None:
        self._neu_rechnen()

    @callback
    def _neu_rechnen(self) -> None:
        grenze = (dt_util.utcnow() - AUFBEWAHREN).timestamp()
        if self.proben and self.proben[0][0] < grenze:
            self.proben = [p for p in self.proben if p[0] >= grenze]
        self.ergebnis = auswerten(self.proben, dt_util.now())
        self._zuletzt_gerechnet = dt_util.utcnow()
        for hoerer in list(self._hoerer):
            hoerer()

    def _entity_ids(self) -> dict[str, str]:
        register = er.async_get(self.hass)
        gesucht = {
            "TOP10": [("sensor", "top10")],
            "TOP20": [("sensor", "top20")],
            "TOP2": [("sensor", "top2")],
            "TOP9": [("number", "top9_set"), ("sensor", "top9")],
        }
        gefunden = {}
        for topic, kandidaten in gesucht.items():
            for plattform, schluessel in kandidaten:
                entity_id = register.async_get_entity_id(
                    plattform, DOMAIN, f"heishamon_{self._kennung}_{schluessel}"
                )
                if entity_id:
                    gefunden[topic] = entity_id
                    break
        return gefunden

    async def _verlauf_uebernehmen(self) -> None:
        """Ergaenzt aeltere Proben aus dem Verlauf von Home Assistant."""
        if "recorder" not in self.hass.config.components:
            return
        entity_ids = self._entity_ids()
        if "TOP10" not in entity_ids or "TOP20" not in entity_ids:
            return
        try:
            from homeassistant.components.recorder import get_instance, history

            bis = (
                dt_util.utc_from_timestamp(self.proben[0][0])
                if self.proben
                else dt_util.utcnow()
            )
            von = dt_util.utcnow() - AUFBEWAHREN
            if bis <= von:
                return
            verlauf = await get_instance(self.hass).async_add_executor_job(
                lambda: history.get_significant_states(
                    self.hass,
                    von,
                    bis,
                    list(entity_ids.values()),
                    significant_changes_only=False,
                    no_attributes=True,
                )
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Verlauf fuer die Warmwasser-Auswertung nicht lesbar: %s", err)
            return

        topic_von = {eid: topic for topic, eid in entity_ids.items()}
        aenderungen = []
        for entity_id, zustaende in verlauf.items():
            topic = topic_von.get(entity_id)
            if topic is None:
                continue
            for zustand in zustaende:
                state = getattr(zustand, "state", None)
                zeit = getattr(zustand, "last_changed", None)
                if zeit is None:
                    continue
                aenderungen.append((zeit.timestamp(), topic, _zahl(state)))
        aenderungen.sort()
        werte = dict.fromkeys(TOPICS)
        alt: list[Probe] = []
        for zeit, topic, wert in aenderungen:
            werte[topic] = wert
            probe = [zeit] + [werte[t] for t in TOPICS]
            if alt and alt[-1][0] == zeit:
                alt[-1] = probe
            else:
                alt.append(probe)
        if self.proben:
            alt = [p for p in alt if p[0] < self.proben[0][0]]
        if not alt:
            return
        self.proben = alt + self.proben
        _LOGGER.debug("Warmwasser-Auswertung: %d Proben aus dem Verlauf uebernommen", len(alt))
        self._store.async_delay_save(self._daten_zum_speichern, SPEICHER_VERZOEGERUNG)
        self._neu_rechnen()
