"""Sensoren fuer alle HeishaMon-Topics und den COP."""
from __future__ import annotations

import time

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HEISHAMON_TOPICS, slug_host
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
from .entity import HeishamonEntity


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
    """Legt fuer jedes Topic einen Sensor an."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    host = data["host"]
    power_entity = data.get("power_entity")

    entities: list[SensorEntity] = [
        HeishamonSensor(coordinator, host, topic_id, info)
        for topic_id, info in HEISHAMON_TOPICS.items()
        if info["type"] == "sensor"
    ]
    for betriebsart, kennung in COP_KENNUNG.items():
        entities.append(
            HeishamonCopSensor(
                coordinator, host, betriebsart, kennung, power_entity, data["cop_quelle"]
            )
        )

    # COP-Sensoren aus Vorversionen entfernen. Die Quelle wird jetzt ueber
    # die Auswahl "COP Quelle" gewaehlt statt ueber eigene Sensoren.
    registry = er.async_get(hass)
    for alt in ("cop", "cop_measured", "cop_heating_measured", "cop_dhw_measured"):
        _entferne(registry, f"heishamon_{host}_{alt}")

    async_add_entities(entities)


class HeishamonSensor(HeishamonEntity, SensorEntity):
    """Ein einzelnes HeishaMon-Topic."""

    def __init__(self, coordinator, host: str, topic_id: str, info: dict) -> None:
        super().__init__(coordinator, host)
        self._topic_id = topic_id

        self._attr_unique_id = f"heishamon_{host}_{topic_id.lower()}"
        self.entity_id = f"sensor.heishamon_{slug_host(host)}_{topic_id.lower()}"
        # Der Name kommt aus translations/<sprache>.json unter entity.sensor.<key>
        self._attr_translation_key = topic_id.lower()
        self._attr_icon = info.get("icon")

        if info["numeric"]:
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
        host: str,
        betriebsart: str,
        kennung: str,
        power_entity: str | None,
        wahl,
    ) -> None:
        super().__init__(coordinator, host)
        self._betriebsart = betriebsart
        self._power_entity = power_entity
        self._wahl = wahl
        self._waermepumpe = LaufEnergie()
        self._gemessen = LaufEnergie()
        self._art: str | None = None
        self._letzte_abfrage: float | None = None
        self._attr_translation_key = kennung
        self._attr_unique_id = f"heishamon_{host}_{kennung}"
        self.entity_id = f"sensor.heishamon_{slug_host(host)}_{kennung}"

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
