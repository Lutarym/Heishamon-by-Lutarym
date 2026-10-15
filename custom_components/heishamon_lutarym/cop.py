"""Berechnung der Leistungszahl (COP), getrennt fuer Heizen und Warmwasser.

Der COP ist die Waermemenge geteilt durch die Strommenge eines Laufs. Ein
Lauf beginnt, wenn der Verdichter startet, und endet, wenn er stoppt oder
das Dreiwegeventil die Betriebsart wechselt. Abtauen gehoert zum Lauf,
weil es Strom verbraucht und dem Wasser Waerme entzieht.

Energie wird bei jeder Abfrage aufsummiert: Leistung mal Zeit seit der
letzten Abfrage.

Zwei Quellen:

1. Waermepumpe
   Erzeugte und aufgenommene Leistung, wie die Waermepumpe sie selbst
   meldet. Geraete der K/L-Serie und neuer liefern genaue Werte (XTOP0
   bis XTOP5). Aeltere Geraete liefern nur TOP15/16 und TOP40/41, und die
   nur im Raster von 200 W.

2. Gemessen (nur mit externem Strommesser, etwa Shelly)
   Waermeleistung aus Durchfluss und Temperaturdifferenz:

       P_th = V * rho(T) * cp(T) * (T_vorlauf - T_ruecklauf)

   V Volumenstrom in m3/s, rho Dichte, cp spezifische Waermekapazitaet,
   beides bei der mittleren Wassertemperatur. Strom vom Strommesser.
   Bei Glykol im Kreislauf sind rho und cp anders, der Wert stimmt dann
   nicht.

Ob gerade geheizt oder Warmwasser bereitet wird, zeigt das Dreiwegeventil
(TOP20, 0 = Raum, 1 = Warmwasser). Kuehlen wird nicht erfasst.
"""
from __future__ import annotations

# Betriebsarten
HEIZEN = "heizen"
WARMWASSER = "warmwasser"

# Quellen
QUELLE_WAERMEPUMPE = "heat_pump"
QUELLE_GEMESSEN = "measured"

# Je Betriebsart: (erzeugt, aufgenommen), genaue und alte Werte
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
TOPIC_AUSSEN = "TOP14"

# Unter diesem Schluessel legt der Coordinator Vor- und Ruecklauf ohne
# Beruhigung ab.
ROH_SCHLUESSEL = "_roh"
ROH_TOPICS = (TOPIC_VORLAUF, TOPIC_RUECKLAUF)

# Dichte von Wasser in kg/m3 bei 1 atm.
# Quelle: Appendix F, Water Properties, Tabelle F.1
# (ecampusontario.pressbooks.pub/genchemforgeegees)
DICHTE_WASSER = (
    (10.0, 999.7027),
    (20.0, 998.2067),
    (25.0, 997.0470),
    (30.0, 995.6488),
    (40.0, 992.2152),
    (60.0, 983.20),
    (80.0, 971.79),
)

# Spezifische isobare Waermekapazitaet von Wasser in J/(kg*K).
# Quelle: Wikipedia, Water (data page)
WAERMEKAPAZITAET_WASSER = (
    (20.0, 4181.8),
    (30.0, 4178.4),
    (40.0, 4178.5),
    (50.0, 4180.6),
    (60.0, 4184.3),
    (70.0, 4189.5),
)


def _zahl(wert) -> float | None:
    """Wandelt einen Topic-Wert in eine Zahl, sonst None."""
    if wert is None or isinstance(wert, bool):
        return None
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def _tabelle(tabelle: tuple[tuple[float, float], ...], t: float) -> float:
    """Linear zwischen Tabellenwerten, ausserhalb der Wert am Rand."""
    if t <= tabelle[0][0]:
        return tabelle[0][1]
    if t >= tabelle[-1][0]:
        return tabelle[-1][1]
    for (t1, w1), (t2, w2) in zip(tabelle, tabelle[1:]):
        if t1 <= t <= t2:
            return w1 + (w2 - w1) * (t - t1) / (t2 - t1)
    return tabelle[-1][1]


def dichte(t: float) -> float:
    """Dichte von Wasser in kg/m3."""
    return _tabelle(DICHTE_WASSER, t)


def waermekapazitaet(t: float) -> float:
    """Spezifische Waermekapazitaet von Wasser in J/(kg*K)."""
    return _tabelle(WAERMEKAPAZITAET_WASSER, t)


def _leistung(data: dict, topic: str) -> float | None:
    """Leistungswert in W.

    Fehlt der Wert oder ist er negativ (HeishaMon meldet ungueltige
    Leistung etwa als -200), gilt er als ungueltig.
    """
    wert = _zahl(data.get(topic))
    if wert is None or wert < 0:
        return None
    return wert


def abtauen(data: dict) -> bool:
    """True, wenn die Waermepumpe abtaut."""
    wert = _zahl(data.get(TOPIC_ABTAUEN))
    return wert is not None and wert > 0


def verdichter_laeuft(data: dict) -> bool:
    """True, wenn der Verdichter laeuft. Abtauen zaehlt als Laufen."""
    frequenz = _zahl(data.get(TOPIC_VERDICHTER))
    return (frequenz is not None and frequenz > 0) or abtauen(data)


def betriebsart_aktiv(data: dict, betriebsart: str) -> bool:
    """True, wenn das Dreiwegeventil auf die Betriebsart gestellt ist."""
    stellung = _zahl(data.get(TOPIC_VENTIL))
    return stellung is not None and stellung == VENTIL_STELLUNG[betriebsart]


def leistung_waermepumpe(
    data: dict, betriebsart: str
) -> tuple[float | None, float | None, str | None]:
    """Erzeugte und aufgenommene Leistung laut Waermepumpe in W.

    Liefert (erzeugt, aufgenommen, art). Die genauen XTOP-Werte haben
    Vorrang, wenn das Geraet sie sendet.
    """
    for art in ("XTOP", "TOP"):
        erzeugt_topic, aufgenommen_topic = LEISTUNG_TOPICS[betriebsart][art]
        if erzeugt_topic not in data or aufgenommen_topic not in data:
            continue
        erzeugt = _leistung(data, erzeugt_topic)
        aufgenommen = _leistung(data, aufgenommen_topic)
        if erzeugt is not None and aufgenommen is not None:
            return erzeugt, aufgenommen, art
    return None, None, None


def thermische_leistung(data: dict, roh: dict | None = None) -> float | None:
    """Waermeleistung aus Durchfluss und Temperaturdifferenz in W.

    roh enthaelt Vor- und Ruecklauf ohne Beruhigung, die Beruhigung wuerde
    die Differenz verfaelschen. Beim Abtauen ist der Wert negativ, weil
    dem Wasser Waerme entzogen wird. Sonst wird eine negative Differenz
    als 0 gezaehlt, es wird dann keine Heizwaerme geliefert.
    """
    quelle = roh or data
    durchfluss = _zahl(data.get(TOPIC_DURCHFLUSS))
    vorlauf = _zahl(quelle.get(TOPIC_VORLAUF))
    ruecklauf = _zahl(quelle.get(TOPIC_RUECKLAUF))
    if durchfluss is None or vorlauf is None or ruecklauf is None:
        return None
    if durchfluss <= 0:
        return 0.0
    mittel = (vorlauf + ruecklauf) / 2
    volumenstrom = durchfluss / 60000  # l/min in m3/s
    leistung = (
        volumenstrom * dichte(mittel) * waermekapazitaet(mittel) * (vorlauf - ruecklauf)
    )
    if leistung < 0 and not abtauen(data):
        return 0.0
    return leistung


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


def carnot_grenze(data: dict, roh: dict | None = None) -> float | None:
    """Theoretisch hoechstmoeglicher COP zwischen Aussenluft und Vorlauf.

    COP_carnot = T_vorlauf / (T_vorlauf - T_aussen), Temperaturen in Kelvin.
    Ein hoeherer COP ist physikalisch nicht moeglich. Ist der Vorlauf nicht
    waermer als die Aussenluft, gibt es keine Grenze, dann None.
    """
    quelle = roh or data
    vorlauf = _zahl(quelle.get(TOPIC_VORLAUF))
    aussen = _zahl(data.get(TOPIC_AUSSEN))
    if vorlauf is None or aussen is None or vorlauf <= aussen:
        return None
    return (vorlauf + 273.15) / (vorlauf - aussen)


class LaufEnergie:
    """Waerme- und Strommenge eines Laufs."""

    def __init__(self) -> None:
        self.zuruecksetzen()

    def zuruecksetzen(self) -> None:
        """Beginnt einen neuen Lauf."""
        self.waerme_j = 0.0
        self.strom_j = 0.0
        self.sekunden = 0.0

    def hinzufuegen(self, thermisch_w: float, elektrisch_w: float, sekunden: float) -> None:
        """Addiert Leistung mal Zeit."""
        self.waerme_j += thermisch_w * sekunden
        self.strom_j += elektrisch_w * sekunden
        self.sekunden += sekunden

    def cop(self, grenze: float | None) -> float | None:
        """COP des Laufs. None, wenn nicht sinnvoll oder ueber der Carnot-Grenze."""
        wert = cop(self.waerme_j, self.strom_j)
        if wert is not None and grenze is not None and wert > grenze:
            return None
        return wert


class QuellenWahl:
    """Gewaehlte Quelle fuer den angezeigten COP, gemeinsam fuer alle Sensoren."""

    def __init__(self, wert: str) -> None:
        self.wert = wert
        self._hoerer: list = []

    def setzen(self, wert: str) -> None:
        """Setzt die Quelle und benachrichtigt die Sensoren."""
        self.wert = wert
        for hoerer in list(self._hoerer):
            hoerer()

    def abonnieren(self, hoerer):
        """Registriert eine Rueckmeldung, liefert die Abmeldung."""
        self._hoerer.append(hoerer)

        def abmelden() -> None:
            if hoerer in self._hoerer:
                self._hoerer.remove(hoerer)

        return abmelden
