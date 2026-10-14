"""Berechnung der Leistungszahl (COP), getrennt fuer Heizen und Warmwasser.

Zwei Wege, beide liefern nur dann einen Wert, wenn der Verdichter laeuft
und die Waermepumpe nicht abtaut:

1. COP laut Waermepumpe
   Erzeugte durch aufgenommene Leistung, beides wie es die Waermepumpe
   selbst meldet. Sie meldet Heizen und Warmwasser getrennt. Geraete der
   K/L-Serie und neuer liefern genaue Werte (XTOP0 bis XTOP5). Aeltere
   Geraete liefern nur TOP15/16 und TOP40/41, und die nur im Raster von
   200 W. Der COP ist dort entsprechend grob.

2. COP gemessen (nur mit externem Strommesser, etwa Shelly PM)
   Thermische Leistung aus Durchfluss und Temperaturdifferenz zwischen
   Vor- und Ruecklauf, geteilt durch die vom Strommesser gemessene
   elektrische Leistung:

       P_th [W] = Durchfluss [l/min] / 60 * 4180 * (Vorlauf - Ruecklauf)

   Ob gerade geheizt oder Warmwasser bereitet wird, zeigt das
   Dreiwegeventil (TOP20, 0 = Raum, 1 = Warmwasser). Kuehlen wird nicht
   erfasst, dort ist der Vorlauf kaelter als der Ruecklauf.

   4180 J/(kg*K) ist die spezifische Waermekapazitaet von Wasser, ein
   Liter wird als ein Kilogramm gerechnet. Bei Glykol im Kreislauf ist
   die Waermekapazitaet kleiner, der Wert faellt dann zu hoch aus.
"""
from __future__ import annotations

# Spezifische Waermekapazitaet von Wasser in J/(kg*K)
WAERMEKAPAZITAET_WASSER = 4180

# Betriebsarten
HEIZEN = "heizen"
WARMWASSER = "warmwasser"

# Je Betriebsart: (erzeugt, aufgenommen) genau und alt
LEISTUNG_TOPICS = {
    HEIZEN: {"XTOP": ("XTOP3", "XTOP0"), "TOP": ("TOP15", "TOP16")},
    WARMWASSER: {"XTOP": ("XTOP5", "XTOP2"), "TOP": ("TOP40", "TOP41")},
}

# Dreiwegeventil laut HeishaMon-Firmware: 0 = Raum, 1 = Warmwasser
TOPIC_VENTIL = "TOP20"
VENTIL_STELLUNG = {HEIZEN: 0, WARMWASSER: 1}

TOPIC_DURCHFLUSS = "TOP1"
TOPIC_RUECKLAUF = "TOP5"
TOPIC_VORLAUF = "TOP6"
TOPIC_VERDICHTER = "TOP8"
TOPIC_ABTAUEN = "TOP26"

# Unter diesem Schluessel legt der Coordinator Vor- und Ruecklauf ohne
# Beruhigung ab.
ROH_SCHLUESSEL = "_roh"
ROH_TOPICS = (TOPIC_VORLAUF, TOPIC_RUECKLAUF)


def _zahl(wert) -> float | None:
    """Wandelt einen Topic-Wert in eine Zahl, sonst None."""
    if wert is None or isinstance(wert, bool):
        return None
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def _leistung(data: dict, topic: str) -> float | None:
    """Leistungswert in W.

    Fehlt der Wert oder ist er negativ (HeishaMon meldet ungueltige
    Leistung etwa als -200), gilt er als ungueltig.
    """
    wert = _zahl(data.get(topic))
    if wert is None or wert < 0:
        return None
    return wert


def verdichter_laeuft(data: dict) -> bool:
    """True, wenn der Verdichter laeuft und nicht abgetaut wird."""
    frequenz = _zahl(data.get(TOPIC_VERDICHTER))
    abtauen = _zahl(data.get(TOPIC_ABTAUEN))
    if frequenz is None or frequenz <= 0:
        return False
    if abtauen is not None and abtauen > 0:
        return False
    return True


def leistung_waermepumpe(
    data: dict, betriebsart: str
) -> tuple[float | None, float | None, str | None]:
    """Erzeugte und aufgenommene Leistung laut Waermepumpe.

    Liefert (erzeugt_w, aufgenommen_w, quelle) fuer Heizen oder
    Warmwasser. Die genauen XTOP-Werte haben Vorrang, wenn das Geraet
    sie sendet.
    """
    for quelle in ("XTOP", "TOP"):
        erzeugt_topic, aufgenommen_topic = LEISTUNG_TOPICS[betriebsart][quelle]
        if erzeugt_topic not in data or aufgenommen_topic not in data:
            continue
        erzeugt = _leistung(data, erzeugt_topic)
        aufgenommen = _leistung(data, aufgenommen_topic)
        if erzeugt is not None and aufgenommen is not None:
            return erzeugt, aufgenommen, quelle
    return None, None, None


def betriebsart_aktiv(data: dict, betriebsart: str) -> bool:
    """True, wenn das Dreiwegeventil auf die Betriebsart gestellt ist."""
    stellung = _zahl(data.get(TOPIC_VENTIL))
    return stellung is not None and stellung == VENTIL_STELLUNG[betriebsart]


def thermische_leistung(data: dict, roh: dict | None = None) -> float | None:
    """Thermische Leistung aus Durchfluss und Temperaturdifferenz in W.

    roh enthaelt Vor- und Ruecklauf ohne Beruhigung. Die Beruhigung
    verzoegert Temperaturaenderungen und wuerde die Differenz verfaelschen.
    """
    quelle = roh or data
    durchfluss = _zahl(data.get(TOPIC_DURCHFLUSS))
    vorlauf = _zahl(quelle.get(TOPIC_VORLAUF))
    ruecklauf = _zahl(quelle.get(TOPIC_RUECKLAUF))
    if durchfluss is None or vorlauf is None or ruecklauf is None:
        return None
    if durchfluss <= 0 or vorlauf <= ruecklauf:
        # Kein Durchfluss, Kuehlen oder Uebergang: keine Heizleistung
        return None
    return durchfluss / 60 * WAERMEKAPAZITAET_WASSER * (vorlauf - ruecklauf)


def cop(erzeugt: float | None, aufgenommen: float | None) -> float | None:
    """Verhaeltnis erzeugt zu aufgenommen, None wenn nicht sinnvoll."""
    if erzeugt is None or aufgenommen is None:
        return None
    if erzeugt <= 0 or aufgenommen <= 0:
        return None
    return round(erzeugt / aufgenommen, 2)


def leistung_in_watt(zustand: str | None, einheit: str | None) -> float | None:
    """Liest den Zustand eines Leistungssensors in Watt.

    Unterstuetzt werden mW, W, kW und MW. Andere oder fehlende Einheiten
    werden nicht geraten, sondern verworfen.
    """
    wert = _zahl(zustand)
    if wert is None:
        return None
    faktor = {"mW": 0.001, "W": 1, "kW": 1000, "MW": 1_000_000}.get(
        (einheit or "").strip()
    )
    if faktor is None:
        return None
    return wert * faktor
