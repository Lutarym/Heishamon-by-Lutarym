"""Betriebsanalyse der Waermepumpe.

Wird bei jeder Abfrage fortgeschrieben (Leistung mal Zeit seit der letzten
Abfrage, wie beim COP). Gespeichert werden nur Ereignisse und
Tagessummen, keine Rohdaten. Aufbewahrt werden 8 Wochen.

Ereignisse:
- Verdichterlauf: Verdichterfrequenz (TOP8) ueber 0 oder Abtauen (TOP26).
- Warmwasserladung: Dreiwegeventil (TOP20) auf Warmwasser.
- Abtauen: TOP26 = 1.

Tagessummen (Ortsdatum):
- Strom gesamt und Strom aus dem Netz (nur mit Netzbezugs-Sensor).
- Heizstab-Laufzeit (TOP60 intern, TOP61 extern).
- Beim Heizen mit laufendem Verdichter, ohne Abtauen: Vorlauf (TOP6) minus
  Soll (TOP7), Spreizung Vorlauf minus Ruecklauf (TOP5), Durchfluss (TOP1)
  und je 2 Grad Aussentemperatur (TOP14) mittlerer Vorlauf und Soll.
- Bei Warmwasser mit laufendem Verdichter: Spreizung und Durchfluss.

Strom: externer Strommesser, wenn eingestellt, sonst die Werte der
Waermepumpe. Waerme: nach der Quellenwahl des COP.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from statistics import mean
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .cop import (
    HEIZEN,
    QUELLE_GEMESSEN,
    ROH_SCHLUESSEL,
    WARMWASSER,
    abtauen,
    leistung_in_watt,
    leistung_waermepumpe,
    thermische_leistung,
    verdichter_laeuft,
    _zahl,
)

_LOGGER = logging.getLogger(__name__)

AUFBEWAHREN_TAGE = 56
KURZER_LAUF_MIN = 10
MIN_LADUNGEN_JE_GRUPPE = 2
SPEICHER_VERZOEGERUNG = 600


def _tag(ts: float) -> str:
    return dt_util.as_local(dt_util.utc_from_timestamp(ts)).date().isoformat()


def _zeit(ts: float | None) -> str | None:
    if ts is None:
        return None
    return dt_util.as_local(dt_util.utc_from_timestamp(ts)).isoformat(timespec="minutes")


def _stufe(aussen: float) -> int:
    """Aussentemperatur auf 2 Grad gerundet (gerade Zahl)."""
    return int(round(aussen / 2.0) * 2)


def _neuer_tag() -> dict:
    return {
        "strom_wh": 0.0,
        "netz_wh": 0.0,
        "strom_netz_bekannt": False,
        "heizstab_s": 0.0,
        "vl_diff": [0.0, 0.0],  # Summe (K*s), Sekunden
        "spr_h": [0.0, 0.0],
        "fluss_h": [0.0, 0.0],
        "spr_w": [0.0, 0.0],
        "fluss_w": [0.0, 0.0],
        "kurve": {},  # Stufe -> [Sekunden, Vorlauf*s, Soll*s]
    }


def _mittel(paar: list[float]) -> float | None:
    return paar[0] / paar[1] if paar[1] > 0 else None


class Betriebsanalyse:
    """Sammelt Ereignisse und Tagessummen und berechnet die Kennzahlen."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        coordinator,
        cop_quelle,
        strommesser: str | None,
        netzbezug: str | None,
        preis_ct: float,
        melden: Callable[[str], None] | None = None,
    ) -> None:
        self.hass = hass
        self._coordinator = coordinator
        self._cop_quelle = cop_quelle
        self.strommesser = strommesser
        self.netzbezug = netzbezug
        self.preis_ct = preis_ct or 0.0
        self._melden = melden
        self._store: Store = Store(hass, 1, f"{DOMAIN}.analyse.{entry_id}")
        self._hoerer: list[Callable[[], None]] = []
        self._abmelden: list[Callable[[], None]] = []
        self._letzte_abfrage: float | None = None

        self.laeufe: list[dict] = []
        self.ladungen: list[dict] = []
        self.abtauungen: list[dict] = []
        self.tage: dict[str, dict] = {}
        self.offen: dict[str, dict | None] = {"lauf": None, "ladung": None, "abtauen": None}
        self.heizstab_zuletzt: float | None = None
        self._heizstab_an = False
        self.top12: float | None = None
        self.top91: float | None = None
        self.ergebnis: dict = {}

    # ------------------------------------------------------------------
    async def async_start(self) -> None:
        gespeichert = await self._store.async_load() or {}
        self.laeufe = gespeichert.get("laeufe", [])
        self.ladungen = gespeichert.get("ladungen", [])
        self.abtauungen = gespeichert.get("abtauungen", [])
        self.tage = gespeichert.get("tage", {})
        self.heizstab_zuletzt = gespeichert.get("heizstab_zuletzt")
        self._abmelden.append(self._coordinator.async_add_listener(self._neue_daten))
        self._rechnen()

    async def async_stop(self) -> None:
        for abmelden in self._abmelden:
            abmelden()
        self._abmelden.clear()
        await self._store.async_save(self._speicherdaten())

    def abonnieren(self, hoerer: Callable[[], None]) -> Callable[[], None]:
        self._hoerer.append(hoerer)
        return lambda: self._hoerer.remove(hoerer)

    def _speicherdaten(self) -> dict:
        return {
            "laeufe": self.laeufe,
            "ladungen": self.ladungen,
            "abtauungen": self.abtauungen,
            "tage": self.tage,
            "heizstab_zuletzt": self.heizstab_zuletzt,
        }

    # ------------------------------------------------------------------
    def _sekunden(self, jetzt: float) -> float:
        takt = self._coordinator.update_interval.total_seconds()
        vorher = self._letzte_abfrage
        self._letzte_abfrage = jetzt
        if vorher is None:
            return 0.0
        return max(0.0, min(jetzt - vorher, 3 * takt))

    def _fremdleistung(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        zustand = self.hass.states.get(entity_id)
        if zustand is None:
            return None
        return leistung_in_watt(
            zustand.state, zustand.attributes.get("unit_of_measurement")
        )

    @callback
    def _neue_daten(self) -> None:
        data = self._coordinator.data or {}
        jetzt = dt_util.utcnow().timestamp()
        self.schritt(data, jetzt)
        self._store.async_delay_save(self._speicherdaten, SPEICHER_VERZOEGERUNG)
        self._rechnen()

    def schritt(self, data: dict, jetzt: float) -> None:
        """Verarbeitet eine Abfrage."""
        dt = self._sekunden(jetzt)
        tag = self.tage.setdefault(_tag(jetzt), _neuer_tag())

        ventil = _zahl(data.get("TOP20"))
        art = WARMWASSER if ventil == 1 else HEIZEN
        laeuft = verdichter_laeuft(data)
        taut = abtauen(data)
        aussen = _zahl(data.get("TOP14"))
        self.top12 = _zahl(data.get("TOP12")) if data.get("TOP12") is not None else self.top12
        self.top91 = _zahl(data.get("TOP91")) if data.get("TOP91") is not None else self.top91

        # Leistung in W
        erzeugt, aufgenommen, _ = leistung_waermepumpe(data, art)
        strom = self._fremdleistung(self.strommesser)
        if strom is None:
            strom = aufgenommen if laeuft else (aufgenommen or 0.0)
        waerme = erzeugt
        if self.strommesser and self._cop_quelle.wert == QUELLE_GEMESSEN:
            waerme = thermische_leistung(data, data.get(ROH_SCHLUESSEL))
        netz = self._fremdleistung(self.netzbezug)
        aus_netz = None
        if netz is not None and strom is not None:
            aus_netz = min(strom, max(0.0, netz))

        # Tagessummen
        if strom is not None:
            tag["strom_wh"] += strom * dt / 3600
        if aus_netz is not None:
            tag["netz_wh"] += aus_netz * dt / 3600
            tag["strom_netz_bekannt"] = True

        heizstab = any(_zahl(data.get(t)) == 1 for t in ("TOP60", "TOP61"))
        if heizstab:
            tag["heizstab_s"] += dt
            self.heizstab_zuletzt = jetzt
            if not self._heizstab_an and self._melden is not None:
                self._melden(_zeit(jetzt) or "")
        self._heizstab_an = heizstab

        vorlauf = _zahl(data.get("TOP6"))
        ruecklauf = _zahl(data.get("TOP5"))
        soll = _zahl(data.get("TOP7"))
        fluss = _zahl(data.get("TOP1"))
        if laeuft and not taut and dt > 0:
            if art == HEIZEN:
                if vorlauf is not None and soll is not None:
                    tag["vl_diff"][0] += (vorlauf - soll) * dt
                    tag["vl_diff"][1] += dt
                    if aussen is not None:
                        stufe = tag["kurve"].setdefault(str(_stufe(aussen)), [0.0, 0.0, 0.0])
                        stufe[0] += dt
                        stufe[1] += vorlauf * dt
                        stufe[2] += soll * dt
                if vorlauf is not None and ruecklauf is not None:
                    tag["spr_h"][0] += (vorlauf - ruecklauf) * dt
                    tag["spr_h"][1] += dt
                if fluss is not None:
                    tag["fluss_h"][0] += fluss * dt
                    tag["fluss_h"][1] += dt
            else:
                if vorlauf is not None and ruecklauf is not None:
                    tag["spr_w"][0] += (vorlauf - ruecklauf) * dt
                    tag["spr_w"][1] += dt
                if fluss is not None:
                    tag["fluss_w"][0] += fluss * dt
                    tag["fluss_w"][1] += dt

        # Verdichterlauf
        lauf = self.offen["lauf"]
        if laeuft and lauf is None:
            self.offen["lauf"] = {"s": jetzt, "art": art}
        elif not laeuft and lauf is not None:
            lauf["e"] = jetzt
            self.laeufe.append(lauf)
            self.offen["lauf"] = None

        # Warmwasserladung
        ladung = self.offen["ladung"]
        if ventil == 1:
            if ladung is None:
                ladung = self.offen["ladung"] = {
                    "s": jetzt,
                    "strom_wh": 0.0,
                    "waerme_wh": 0.0,
                    "netz_wh": 0.0,
                    "netz_bekannt": False,
                    "aussen": [0.0, 0.0],
                }
            if strom is not None:
                ladung["strom_wh"] += strom * dt / 3600
            if waerme is not None:
                ladung["waerme_wh"] += waerme * dt / 3600
            if aus_netz is not None:
                ladung["netz_wh"] += aus_netz * dt / 3600
                ladung["netz_bekannt"] = True
            if aussen is not None:
                ladung["aussen"][0] += aussen
                ladung["aussen"][1] += 1
        elif ventil is not None and ladung is not None:
            ladung["e"] = jetzt
            self.ladungen.append(ladung)
            self.offen["ladung"] = None

        # Abtauen
        abt = self.offen["abtauen"]
        if taut:
            if abt is None:
                abt = self.offen["abtauen"] = {"s": jetzt, "aussen": aussen, "strom_wh": 0.0}
            if strom is not None:
                abt["strom_wh"] += strom * dt / 3600
        elif abt is not None:
            abt["e"] = jetzt
            self.abtauungen.append(abt)
            self.offen["abtauen"] = None

        self._aufraeumen(jetzt)

    def _aufraeumen(self, jetzt: float) -> None:
        grenze = jetzt - AUFBEWAHREN_TAGE * 86400
        for liste in (self.laeufe, self.ladungen, self.abtauungen):
            while liste and liste[0].get("e", jetzt) < grenze:
                liste.pop(0)
        grenz_tag = _tag(grenze)
        for alt in [t for t in self.tage if t < grenz_tag]:
            del self.tage[alt]

    # ------------------------------------------------------------------
    @callback
    def _rechnen(self) -> None:
        self.ergebnis = self.auswerten(dt_util.utcnow().timestamp())
        for hoerer in list(self._hoerer):
            hoerer()

    def _kosten(self, strom_wh: float, netz_wh: float | None) -> float | None:
        if not self.preis_ct:
            return None
        kwh = (netz_wh if netz_wh is not None else strom_wh) / 1000
        return round(kwh * self.preis_ct / 100, 2)

    def auswerten(self, jetzt: float) -> dict:
        tag_24 = jetzt - 86400
        heute = _tag(jetzt)
        sieben = sorted(self.tage)[-7:]

        # Takten
        laeufe_24 = [l for l in self.laeufe if l["s"] >= tag_24]
        dauern = [(l["e"] - l["s"]) / 60 for l in laeufe_24]
        laeufe_7 = [l for l in self.laeufe if l["s"] >= jetzt - 7 * 86400]
        takten = {
            "starts_24h": len(laeufe_24),
            "mittlere_laufzeit_min": round(mean(dauern), 1) if dauern else None,
            "kurze_laeufe_24h": sum(1 for d in dauern if d < KURZER_LAUF_MIN),
            "laengster_lauf_min": round(max(dauern), 1) if dauern else None,
            "starts_je_tag_7d": round(len(laeufe_7) / 7, 1) if laeufe_7 else 0,
            "starts_warmwasser_24h": sum(1 for l in laeufe_24 if l["art"] == WARMWASSER),
            "zaehler_waermepumpe": self.top12,
        }

        # Warmwasserladungen
        def cop_ladung(l: dict) -> float | None:
            if l["strom_wh"] <= 0 or l["waerme_wh"] <= 0:
                return None
            return round(l["waerme_wh"] / l["strom_wh"], 2)

        def aussen_ladung(l: dict) -> float | None:
            return l["aussen"][0] / l["aussen"][1] if l["aussen"][1] else None

        letzte = self.ladungen[-1] if self.ladungen else None
        ww_letzte = None
        if letzte is not None:
            pv = None
            if letzte["netz_bekannt"] and letzte["strom_wh"] > 0:
                pv = round(100 * (1 - letzte["netz_wh"] / letzte["strom_wh"]))
            a = aussen_ladung(letzte)
            ww_letzte = {
                "cop": cop_ladung(letzte),
                "start": _zeit(letzte["s"]),
                "dauer_min": round((letzte["e"] - letzte["s"]) / 60),
                "aussentemperatur": round(a, 1) if a is not None else None,
                "strom_kwh": round(letzte["strom_wh"] / 1000, 2),
                "waerme_kwh": round(letzte["waerme_wh"] / 1000, 2),
                "pv_anteil_prozent": pv,
                "kosten_eur": self._kosten(
                    letzte["strom_wh"], letzte["netz_wh"] if letzte["netz_bekannt"] else None
                ),
            }

        je_stunde: dict[int, list[float]] = {}
        je_aussen: dict[int, list[float]] = {}
        for l in self.ladungen:
            wert = cop_ladung(l)
            if wert is None:
                continue
            stunde = dt_util.as_local(dt_util.utc_from_timestamp(l["s"])).hour
            je_stunde.setdefault(stunde, []).append(wert)
            a = aussen_ladung(l)
            if a is not None:
                je_aussen.setdefault(_stufe(a), []).append(wert)
        gueltig = {h: mean(v) for h, v in je_stunde.items() if len(v) >= MIN_LADUNGEN_JE_GRUPPE}
        beste_stunde = max(gueltig, key=lambda h: gueltig[h]) if gueltig else None

        tage_7 = [self.tage[t] for t in sieben]
        ww_strom_7 = [
            l for l in self.ladungen if l.get("e", 0) >= jetzt - 7 * 86400
        ]
        ww_kwh_tag = sum(l["strom_wh"] for l in ww_strom_7) / 1000 / 7 if ww_strom_7 else None
        ww_netz_bekannt = bool(ww_strom_7) and all(l["netz_bekannt"] for l in ww_strom_7)
        ww_netz_tag = (
            sum(l["netz_wh"] for l in ww_strom_7) / 1000 / 7 if ww_netz_bekannt else None
        )
        warmwasser = {
            "letzte": ww_letzte,
            "beste_stunde": f"{beste_stunde:02d}:00" if beste_stunde is not None else None,
            "cop_je_startstunde": {
                f"{h:02d}:00": round(mean(v), 2) for h, v in sorted(je_stunde.items())
            },
            "ladungen_je_startstunde": {f"{h:02d}:00": len(v) for h, v in sorted(je_stunde.items())},
            "cop_je_aussentemperatur": {
                f"{k} °C": round(mean(v), 2) for k, v in sorted(je_aussen.items())
            },
            "ladungen_ausgewertet": sum(len(v) for v in je_stunde.values()),
            "kwh_je_tag_7d": round(ww_kwh_tag, 2) if ww_kwh_tag is not None else None,
            "kosten_je_tag_7d": self._kosten(ww_kwh_tag * 1000, ww_netz_tag * 1000 if ww_netz_tag is not None else None)
            if ww_kwh_tag is not None
            else None,
        }

        # Abtauen
        abt_24 = [a for a in self.abtauungen if a["s"] >= tag_24]
        abt_7 = [a for a in self.abtauungen if a["s"] >= jetzt - 7 * 86400]
        je_stufe: dict[int, int] = {}
        for a in abt_7:
            if a.get("aussen") is not None:
                je_stufe[_stufe(a["aussen"])] = je_stufe.get(_stufe(a["aussen"]), 0) + 1
        abt_dauern = [(a["e"] - a["s"]) / 60 for a in abt_24]
        abtauen_e = {
            "anzahl_24h": len(abt_24),
            "dauer_gesamt_min": round(sum(abt_dauern), 1),
            "mittlere_dauer_min": round(mean(abt_dauern), 1) if abt_dauern else None,
            "strom_kwh_24h": round(sum(a["strom_wh"] for a in abt_24) / 1000, 2),
            "je_tag_7d": round(len(abt_7) / 7, 1),
            "anzahl_7d_je_aussentemperatur": {f"{k} °C": v for k, v in sorted(je_stufe.items())},
        }

        # Heizkurve, Spreizung, Durchfluss (letzte 7 Tage)
        def summe(schluessel: str) -> list[float]:
            return [sum(t[schluessel][0] for t in tage_7), sum(t[schluessel][1] for t in tage_7)]

        kurve: dict[int, list[float]] = {}
        for t in tage_7:
            for stufe, (s, vl, so) in t["kurve"].items():
                k = kurve.setdefault(int(stufe), [0.0, 0.0, 0.0])
                k[0] += s
                k[1] += vl
                k[2] += so

        def runden(wert: float | None, stellen: int = 1) -> float | None:
            return round(wert, stellen) if wert is not None else None

        heizkreis = {
            "vorlauf_ueber_soll": runden(_mittel(summe("vl_diff"))),
            "heizstunden_7d": round(summe("vl_diff")[1] / 3600, 1),
            "vorlauf_je_aussentemperatur": {
                f"{k} °C": {"ist": round(v[1] / v[0], 1), "soll": round(v[2] / v[0], 1), "stunden": round(v[0] / 3600, 1)}
                for k, v in sorted(kurve.items())
                if v[0] >= 600
            },
            "spreizung_heizen": runden(_mittel(summe("spr_h"))),
            "durchfluss_heizen": runden(_mittel(summe("fluss_h"))),
            "spreizung_warmwasser": runden(_mittel(summe("spr_w"))),
            "durchfluss_warmwasser": runden(_mittel(summe("fluss_w"))),
        }

        # PV-Anteil
        t_heute = self.tage.get(heute)
        pv = {"heute": None, "7d": None, "strom_kwh_heute": None, "netz_kwh_heute": None}
        if t_heute and t_heute["strom_netz_bekannt"] and t_heute["strom_wh"] > 0:
            pv["heute"] = round(100 * (1 - t_heute["netz_wh"] / t_heute["strom_wh"]))
            pv["strom_kwh_heute"] = round(t_heute["strom_wh"] / 1000, 2)
            pv["netz_kwh_heute"] = round(t_heute["netz_wh"] / 1000, 2)
        bekannt = [t for t in tage_7 if t["strom_netz_bekannt"]]
        strom_7 = sum(t["strom_wh"] for t in bekannt)
        if strom_7 > 0:
            pv["7d"] = round(100 * (1 - sum(t["netz_wh"] for t in bekannt) / strom_7))

        # Heizstab
        heizstab = {
            "heute_min": round((t_heute or _neuer_tag())["heizstab_s"] / 60, 1),
            "7d_min": round(sum(t["heizstab_s"] for t in tage_7) / 60, 1),
            "zuletzt_aktiv": _zeit(self.heizstab_zuletzt),
            "betriebsstunden_heizstab_warmwasser": self.top91,
        }

        return {
            "takten": takten,
            "warmwasser": warmwasser,
            "abtauen": abtauen_e,
            "heizkreis": heizkreis,
            "pv": pv,
            "heizstab": heizstab,
            "preis_ct": self.preis_ct or None,
            "daten_ab": min(self.tage) if self.tage else None,
        }
