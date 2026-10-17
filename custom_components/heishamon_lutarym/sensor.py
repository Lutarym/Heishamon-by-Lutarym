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
