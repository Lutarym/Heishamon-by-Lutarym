"""Sensoren fuer alle HeishaMon-Topics und den COP."""
from __future__ import annotations

import time

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    EINWIRE_PRAEFIX,
    EXTRA_TOPICS,
    HEISHAMON_TOPICS,
    OPT_TOPICS,
    S0_PRAEFIX,
)
from .cop import (
    HEIZEN,
    QUELLE_GEMESSEN,
    ROH_SCHLUESSEL,
    WARMWASSER,
    LaufEnergie,
    betriebsart_aktiv,
    carnot_grenze,
    leistung_in_watt,
    leistung_waermepumpe,
    thermische_leistung,
    verdichter_laeuft,
)
from .entity import Geraet, HeishamonEntity


# Betriebsart -> Kennung in unique_id, entity_id und Uebersetzung
COP_KENNUNG = {HEIZEN: "cop_heating", WARMWASSER: "cop_dhw"}


def _entferne(registry, unique_id: str) -> None:
    """Entfernt eine Entity aus der Registry, falls vorhanden."""
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    if entity_id:
        registry.async_remove(entity_id)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt fuer jedes Topic einen Sensor an.

    Jedes Topic bekommt einen Sensor, auch wenn es zusaetzlich einstellbar
    ist. So sind alle Werte auch im Nur-Lesen-Betrieb sichtbar.
    XTOP, OPT, 1-Wire und S0 nur, wenn die Platine sie beim Einrichten
    liefert. Kommen sie spaeter dazu, muss die Integration neu geladen werden.
    """
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    geraet: Geraet = data["geraet"]
    power_entity = data.get("power_entity")
    werte = coordinator.data or {}

    entities: list[SensorEntity] = [
        HeishamonSensor(coordinator, geraet, topic_id, info)
        for topic_id, info in HEISHAMON_TOPICS.items()
    ]
    entities.extend(
        HeishamonSensor(coordinator, geraet, topic_id, {**info, "numeric": True})
        for topic_id, info in EXTRA_TOPICS.items()
        if topic_id in werte
    )
    entities.extend(
        HeishamonSensor(coordinator, geraet, topic_id, {"numeric": True, "icon": "mdi:expansion-card"})
        for topic_id in OPT_TOPICS
        if topic_id in werte
    )
    for schluessel in werte:
        if (
            schluessel.startswith(EINWIRE_PRAEFIX)
            and not schluessel.endswith(("_alias", "_present"))
        ):
            entities.append(
                HeishamonEinwireSensor(
                    coordinator, geraet, schluessel[len(EINWIRE_PRAEFIX):]
                )
            )
        elif schluessel.startswith(S0_PRAEFIX) and schluessel.endswith("_watt"):
            port = schluessel[len(S0_PRAEFIX):-len("_watt")]
            entities.append(HeishamonS0Sensor(coordinator, geraet, port, energie=False))
            entities.append(HeishamonS0Sensor(coordinator, geraet, port, energie=True))

    if data.get("analyse") is not None:
        entities.extend(
            HeishamonAnalyseSensor(coordinator, geraet, data["analyse"], schluessel)
            for schluessel in ANALYSE_SENSOREN
        )

    if data.get("statistik") is not None:
        statistik = data["statistik"]
        entities.extend(
            HeishamonStatistikSensor(coordinator, geraet, statistik, schluessel)
            for schluessel in STATISTIK_SENSOREN
        )
        entities.extend(
            HeishamonOptimalSensor(coordinator, geraet, statistik, wochentag)
            for wochentag in range(7)
        )

    if data.get("warmwasser") is not None:
        entities.append(HeishamonWarmwasserSensor(coordinator, geraet, data["warmwasser"]))
        entities.append(
            HeishamonWarmwasserLetzteSensor(coordinator, geraet, data["warmwasser"])
        )

    for betriebsart, kennung in COP_KENNUNG.items():
        entities.append(
            HeishamonCopSensor(
                coordinator, geraet, betriebsart, kennung, power_entity, data["cop_quelle"]
            )
        )

    # COP-Sensoren aus Vorversionen entfernen. Die Quelle wird jetzt ueber
    # die Auswahl "COP Quelle" gewaehlt statt ueber eigene Sensoren.
    registry = er.async_get(hass)
    for alt in ("cop", "cop_measured", "cop_heating_measured", "cop_dhw_measured"):
        _entferne(registry, f"heishamon_{geraet.kennung}_{alt}")

    async_add_entities(entities)


class HeishamonSensor(HeishamonEntity, SensorEntity):
    """Ein einzelnes HeishaMon-Topic."""

    def __init__(self, coordinator, geraet: Geraet, topic_id: str, info: dict) -> None:
        super().__init__(coordinator, geraet)
        self._topic_id = topic_id
        self._ids("sensor", topic_id.lower())
        # Der Name kommt aus translations/<sprache>.json unter entity.sensor.<key>
        self._attr_translation_key = topic_id.lower()
        self._attr_icon = info.get("icon")

        if info.get("numeric"):
            if info.get("unit"):
                self._attr_native_unit_of_measurement = info["unit"]
            # Standard ist "measurement". Stetig steigende Zaehler
            # (Betriebsstunden, Startzahl) sind in const.py als
            # "total_increasing" markiert, damit die Langzeitstatistik
            # den Verbrauch bildet und nicht den Mittelwert.
            state_class = info.get("state_class")
            if state_class is None and info.get("unit"):
                state_class = "measurement"
            if state_class == "measurement":
                self._attr_state_class = SensorStateClass.MEASUREMENT
            elif state_class == "total_increasing":
                self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            if info.get("device_class"):
                self._attr_device_class = info["device_class"]

    @property
    def native_value(self):
        """Aktueller Wert des Topics."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._topic_id)

    @property
    def extra_state_attributes(self):
        """Klartext-Beschreibung, die HeishaMon mitliefert."""
        if not self.coordinator.data:
            return None
        description = self.coordinator.data.get(f"{self._topic_id}_desc")
        if description is None:
            return None
        return {"beschreibung": description, "topic": self._topic_id}

    @property
    def available(self) -> bool:
        """Nicht verfuegbar, wenn das Topic fehlt."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._topic_id in self.coordinator.data
        )


class HeishamonEinwireSensor(HeishamonEntity, SensorEntity):
    """1-Wire-Temperaturfuehler an der HeishaMon-Platine."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator, geraet: Geraet, kennung: str) -> None:
        super().__init__(coordinator, geraet)
        self._schluessel = f"{EINWIRE_PRAEFIX}{kennung}"
        self._ids("sensor", f"1wire_{kennung.lower()}")
        alias = (coordinator.data or {}).get(f"{self._schluessel}_alias") or ""
        # Der Name ist der Alias aus HeishaMon, sonst die Sensor-ID
        self._attr_name = f"1-Wire {alias or kennung}"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self._schluessel)

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        return (
            super().available
            and self._schluessel in data
            and data.get(f"{self._schluessel}_present") is not False
        )


class HeishamonS0Sensor(HeishamonEntity, SensorEntity):
    """S0-Zaehler an der HeishaMon-Platine: Leistung oder Zaehlerstand."""

    def __init__(self, coordinator, geraet: Geraet, port: str, energie: bool) -> None:
        super().__init__(coordinator, geraet)
        art = "energy" if energie else "power"
        self._schluessel = f"{S0_PRAEFIX}{port}_{'wh_total' if energie else 'watt'}"
        self._ids("sensor", f"s0_{port}_{art}")
        self._attr_translation_key = f"s0_{art}"
        self._attr_translation_placeholders = {"port": str(port)}
        if energie:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_native_unit_of_measurement = "Wh"
        else:
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "W"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self._schluessel)

    @property
    def available(self) -> bool:
        return super().available and self._schluessel in (self.coordinator.data or {})


class HeishamonCopSensor(HeishamonEntity, SensorEntity):
    """COP des laufenden Laufs fuer Heizen oder Warmwasser.

    Bei jeder Abfrage werden Waerme- und Strommenge fuer beide Quellen
    aufsummiert. Angezeigt wird die Quelle, die in "COP Quelle" gewaehlt
    ist. Das Umschalten wirkt dadurch sofort.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:heat-pump"

    def __init__(
        self,
        coordinator,
        geraet: Geraet,
        betriebsart: str,
        kennung: str,
        power_entity: str | None,
        wahl,
    ) -> None:
        super().__init__(coordinator, geraet)
        self._betriebsart = betriebsart
        self._power_entity = power_entity
        self._wahl = wahl
        self._waermepumpe = LaufEnergie()
        self._gemessen = LaufEnergie()
        self._art: str | None = None
        self._letzte_abfrage: float | None = None
        self._attr_translation_key = kennung
        self._ids("sensor", kennung)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._wahl.abonnieren(self.async_write_ha_state))

    def _elektrisch(self) -> float | None:
        if not self._power_entity or self.hass is None:
            return None
        zustand = self.hass.states.get(self._power_entity)
        if zustand is None:
            return None
        return leistung_in_watt(
            zustand.state, zustand.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        )

    def _sekunden_seit_letzter_abfrage(self) -> float:
        """Zeit seit der letzten Abfrage, begrenzt auf den dreifachen Takt.

        Nach einer laengeren Pause (Neustart, Ausfall) waere die Luecke
        sonst mit dem gerade gemessenen Wert gefuellt.
        """
        jetzt = time.monotonic()
        vorher = self._letzte_abfrage
        self._letzte_abfrage = jetzt
        takt = self.coordinator.update_interval.total_seconds()
        if vorher is None:
            return takt
        return min(jetzt - vorher, 3 * takt)

    def _erfasse(self) -> None:
        sekunden = self._sekunden_seit_letzter_abfrage()
        data = self.coordinator.data or {}
        if not verdichter_laeuft(data) or not betriebsart_aktiv(data, self._betriebsart):
            # Lauf beendet oder andere Betriebsart: neu beginnen
            self._waermepumpe.zuruecksetzen()
            self._gemessen.zuruecksetzen()
            return

        erzeugt, aufgenommen, art = leistung_waermepumpe(data, self._betriebsart)
        if erzeugt is not None and aufgenommen is not None:
            self._waermepumpe.hinzufuegen(erzeugt, aufgenommen, sekunden)
            self._art = art

        thermisch = thermische_leistung(data, data.get(ROH_SCHLUESSEL))
        elektrisch = self._elektrisch()
        if thermisch is not None and elektrisch is not None:
            self._gemessen.hinzufuegen(thermisch, elektrisch, sekunden)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._erfasse()
        super()._handle_coordinator_update()

    def _gewaehlt(self) -> tuple[str, LaufEnergie]:
        if self._power_entity and self._wahl.wert == QUELLE_GEMESSEN:
            return QUELLE_GEMESSEN, self._gemessen
        return "heat_pump", self._waermepumpe

    @property
    def native_value(self):
        _, lauf = self._gewaehlt()
        data = self.coordinator.data or {}
        return lauf.cop(carnot_grenze(data, data.get(ROH_SCHLUESSEL)))

    @property
    def extra_state_attributes(self):
        quelle, lauf = self._gewaehlt()
        attribute = {
            "quelle": quelle,
            "waermemenge_kwh": round(lauf.waerme_j / 3_600_000, 3),
            "strommenge_kwh": round(lauf.strom_j / 3_600_000, 3),
            "laufzeit_min": round(lauf.sekunden / 60, 1),
        }
        if quelle == QUELLE_GEMESSEN:
            attribute["strommesser"] = self._power_entity
        else:
            attribute["werte"] = self._art
        return attribute


class HeishamonWarmwasserSensor(HeishamonEntity, SensorEntity):
    """Geplanter Start der Warmwasserladung zur waermsten Tageszeit."""

    _attr_translation_key = "dhw_planned"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:water-boiler-auto"

    def __init__(self, coordinator, geraet: Geraet, planer) -> None:
        super().__init__(coordinator, geraet)
        self._planer = planer
        self._ids("sensor", "dhw_planned")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._planer.abonnieren(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        return self._planer.geplant

    @property
    def extra_state_attributes(self):
        p = self._planer
        return {
            "status": p.status,
            "hoechsttemperatur": p.hoechsttemperatur,
            "tag_erledigt": p.letzte_ladung.isoformat() if p.letzte_ladung else None,
            "gestartet": p.gestartet.isoformat() if p.gestartet else None,
            "hoechstdauer_min": int(p.hoechstdauer.total_seconds() // 60),
            "wetter_entity": p.wetter_entity,
        }


class HeishamonWarmwasserLetzteSensor(HeishamonEntity, SensorEntity):
    """Start der letzten erzwungenen Warmwasserladung."""

    _attr_translation_key = "dhw_last_charge"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator, geraet: Geraet, planer) -> None:
        super().__init__(coordinator, geraet)
        self._planer = planer
        self._ids("sensor", "dhw_last_charge")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._planer.abonnieren(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        return self._planer.letzter_start


# Schluessel: (Wert, Einheit, Geraeteklasse, Symbol, Attribute)
STATISTIK_SENSOREN = {
    "dhw_charges_24h": (
        lambda e: e["ladungen_24h"],
        None,
        None,
        "mdi:counter",
        lambda e: {
            "erzwungen_24h": e["erzwungen_24h"],
            "ladungen_gesamt": e["ladungen_gesamt"],
            "typische_ladedauer_min": e["ladedauer_min"],
            "daten_ab": e["daten_ab"],
        },
    ),
    "dhw_hold_last": (
        lambda e: (e["letzte_haltedauer"] or {}).get("stunden"),
        "h",
        SensorDeviceClass.DURATION,
        "mdi:timer-sand",
        lambda e: {
            k: v for k, v in (e["letzte_haltedauer"] or {}).items() if k != "stunden"
        },
    ),
    "dhw_hold_avg": (
        lambda e: e["haltedauer_mittel"],
        "h",
        SensorDeviceClass.DURATION,
        "mdi:timer-sand-complete",
        lambda e: {
            "median_h": e["haltedauer_median"],
            "anzahl": e["haltedauer_anzahl"],
            "je_ladetemperatur_h": e["haltedauer_je_ladetemperatur"],
            "nachladetemperatur_mittel": e["nachladetemperatur_mittel"],
            "daten_ab": e["daten_ab"],
        },
    ),
    "dhw_reheat_temp": (
        lambda e: e["nachladetemperatur_letzte"],
        "°C",
        SensorDeviceClass.TEMPERATURE,
        "mdi:thermometer-chevron-down",
        lambda e: {"mittel": e["nachladetemperatur_mittel"]},
    ),
}

WOCHENTAGE = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class _StatistikBasis(HeishamonEntity, SensorEntity):
    """Gemeinsame Basis: aktualisiert sich mit der Auswertung."""

    def __init__(self, coordinator, geraet: Geraet, statistik) -> None:
        super().__init__(coordinator, geraet)
        self._statistik = statistik

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._statistik.abonnieren(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return True


class HeishamonStatistikSensor(_StatistikBasis):
    """Kennzahl der Warmwasser-Auswertung."""

    def __init__(self, coordinator, geraet: Geraet, statistik, schluessel: str) -> None:
        super().__init__(coordinator, geraet, statistik)
        wert, einheit, klasse, symbol, attribute = STATISTIK_SENSOREN[schluessel]
        self._wert = wert
        self._attribute = attribute
        self._attr_translation_key = schluessel
        self._attr_native_unit_of_measurement = einheit
        self._attr_device_class = klasse
        self._attr_icon = symbol
        if klasse is not None or einheit is None:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._ids("sensor", schluessel)

    @property
    def native_value(self):
        return self._wert(self._statistik.ergebnis)

    @property
    def extra_state_attributes(self):
        return self._attribute(self._statistik.ergebnis)


class HeishamonOptimalSensor(_StatistikBasis):
    """Optimaler Ladestart fuer einen Wochentag (0 = Montag)."""

    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator, geraet: Geraet, statistik, wochentag: int) -> None:
        super().__init__(coordinator, geraet, statistik)
        self._wochentag = wochentag
        schluessel = f"dhw_optimal_{WOCHENTAGE[wochentag]}"
        self._attr_translation_key = schluessel
        self._ids("sensor", schluessel)

    @property
    def _eintrag(self) -> dict:
        return self._statistik.ergebnis["optimal"].get(self._wochentag, {})

    @property
    def native_value(self):
        return self._eintrag.get("zeit")

    @property
    def extra_state_attributes(self):
        e = self._eintrag
        return {
            "hauptverbrauch_ab": e.get("hauptverbrauch_ab"),
            "verbrauch_hauptzeit_k": e.get("verbrauch_hauptzeit_k"),
            "ausgewertete_tage": e.get("tage", 0),
            "typische_ladedauer_min": self._statistik.ergebnis["ladedauer_min"],
            "verbrauch_k_je_stunde": e.get("verbrauch"),
        }


def _ww(e: dict) -> dict:
    return e["warmwasser"]["letzte"] or {}


# Schluessel: (Wert, Einheit, Geraeteklasse, Symbol, Attribute, Messgroesse)
ANALYSE_SENSOREN = {
    # Takten
    "compressor_starts_24h": (
        lambda e: e["takten"]["starts_24h"], None, None, "mdi:restart",
        lambda e: {k: v for k, v in e["takten"].items() if k != "starts_24h"}, True,
    ),
    "compressor_runtime_avg": (
        lambda e: e["takten"]["mittlere_laufzeit_min"], "min", SensorDeviceClass.DURATION,
        "mdi:timer-outline", lambda e: {}, True,
    ),
    "compressor_short_runs_24h": (
        lambda e: e["takten"]["kurze_laeufe_24h"], None, None, "mdi:timer-alert-outline",
        lambda e: {"grenze_min": 10}, True,
    ),
    # Warmwasser-Effizienz
    "dhw_cop_last": (
        lambda e: _ww(e).get("cop"), None, None, "mdi:water-boiler",
        lambda e: {k: v for k, v in _ww(e).items() if k not in ("cop", "kosten_eur")}, True,
    ),
    "dhw_best_hour": (
        lambda e: e["warmwasser"]["beste_stunde"], None, None, "mdi:clock-star-four-points-outline",
        lambda e: {
            k: e["warmwasser"][k]
            for k in ("cop_je_startstunde", "ladungen_je_startstunde", "cop_je_aussentemperatur", "ladungen_ausgewertet")
        }, False,
    ),
    # Kosten
    "dhw_cost_last": (
        lambda e: _ww(e).get("kosten_eur"), "EUR", SensorDeviceClass.MONETARY, "mdi:cash",
        lambda e: {"strom_kwh": _ww(e).get("strom_kwh"), "preis_ct_kwh": e["preis_ct"]}, False,
    ),
    "dhw_cost_per_day": (
        lambda e: e["warmwasser"]["kosten_je_tag_7d"], "EUR", SensorDeviceClass.MONETARY, "mdi:cash-multiple",
        lambda e: {"kwh_je_tag": e["warmwasser"]["kwh_je_tag_7d"], "preis_ct_kwh": e["preis_ct"]}, False,
    ),
    # Abtauen
    "defrost_24h": (
        lambda e: e["abtauen"]["anzahl_24h"], None, None, "mdi:snowflake-melt",
        lambda e: {k: v for k, v in e["abtauen"].items() if k != "anzahl_24h"}, True,
    ),
    # Heizkurve
    "flow_over_target": (
        lambda e: e["heizkreis"]["vorlauf_ueber_soll"], "K", None, "mdi:chart-bell-curve",
        lambda e: {
            "heizstunden_7d": e["heizkreis"]["heizstunden_7d"],
            "vorlauf_je_aussentemperatur": e["heizkreis"]["vorlauf_je_aussentemperatur"],
        }, True,
    ),
    # Durchfluss und Spreizung
    "spread_heating": (
        lambda e: e["heizkreis"]["spreizung_heizen"], "K", None, "mdi:arrow-expand-vertical",
        lambda e: {"durchfluss_l_min": e["heizkreis"]["durchfluss_heizen"]}, True,
    ),
    "spread_dhw": (
        lambda e: e["heizkreis"]["spreizung_warmwasser"], "K", None, "mdi:arrow-expand-vertical",
        lambda e: {"durchfluss_l_min": e["heizkreis"]["durchfluss_warmwasser"]}, True,
    ),
    # PV-Anteil
    "pv_share_today": (
        lambda e: e["pv"]["heute"], "%", None, "mdi:solar-power",
        lambda e: {
            "pv_anteil_7_tage": e["pv"]["7d"],
            "strom_kwh_heute": e["pv"]["strom_kwh_heute"],
            "netz_kwh_heute": e["pv"]["netz_kwh_heute"],
        }, True,
    ),
    # Heizstab
    "heater_runtime_today": (
        lambda e: e["heizstab"]["heute_min"], "min", SensorDeviceClass.DURATION, "mdi:heating-coil",
        lambda e: {k: v for k, v in e["heizstab"].items() if k != "heute_min"}, True,
    ),
}


class HeishamonAnalyseSensor(HeishamonEntity, SensorEntity):
    """Kennzahl der Betriebsanalyse."""

    def __init__(self, coordinator, geraet: Geraet, analyse, schluessel: str) -> None:
        super().__init__(coordinator, geraet)
        self._analyse = analyse
        wert, einheit, klasse, symbol, attribute, messgroesse = ANALYSE_SENSOREN[schluessel]
        self._wert = wert
        self._attribute = attribute
        self._attr_translation_key = schluessel
        self._attr_native_unit_of_measurement = einheit
        self._attr_device_class = klasse
        self._attr_icon = symbol
        if messgroesse:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._ids("sensor", schluessel)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._analyse.abonnieren(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        if not self._analyse.ergebnis:
            return None
        return self._wert(self._analyse.ergebnis)

    @property
    def extra_state_attributes(self):
        if not self._analyse.ergebnis:
            return None
        return self._attribute(self._analyse.ergebnis)
