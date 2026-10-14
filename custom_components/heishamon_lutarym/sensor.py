"""Sensoren fuer alle HeishaMon-Topics."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HEISHAMON_TOPICS, slug_host
from .cop import (
    HEIZEN,
    ROH_SCHLUESSEL,
    WARMWASSER,
    betriebsart_aktiv,
    cop,
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
    registry = er.async_get(hass)
    for betriebsart, kennung in COP_KENNUNG.items():
        entities.append(HeishamonCopSensor(coordinator, host, betriebsart, kennung))
        if power_entity:
            entities.append(
                HeishamonCopGemessenSensor(
                    coordinator, host, betriebsart, kennung, power_entity
                )
            )
        else:
            # Wurde der Strommesser entfernt, verschwindet auch der Sensor,
            # statt als "nicht mehr bereitgestellt" stehen zu bleiben.
            _entferne(registry, f"heishamon_{host}_{kennung}_measured")

    # Gemeinsame COP-Sensoren aus der Vorversion entfernen
    for alt in ("cop", "cop_measured"):
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
    """COP aus den Leistungswerten, die die Waermepumpe selbst meldet."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:heat-pump-outline"

    def __init__(self, coordinator, host: str, betriebsart: str, kennung: str) -> None:
        super().__init__(coordinator, host)
        self._betriebsart = betriebsart
        self._attr_translation_key = kennung
        self._attr_unique_id = f"heishamon_{host}_{kennung}"
        self.entity_id = f"sensor.heishamon_{slug_host(host)}_{kennung}"

    def _werte(self):
        data = self.coordinator.data or {}
        if not verdichter_laeuft(data):
            return None, None, None
        return leistung_waermepumpe(data, self._betriebsart)

    @property
    def native_value(self):
        erzeugt, aufgenommen, _ = self._werte()
        return cop(erzeugt, aufgenommen)

    @property
    def extra_state_attributes(self):
        erzeugt, aufgenommen, quelle = self._werte()
        return {
            "thermische_leistung_w": erzeugt,
            "elektrische_leistung_w": aufgenommen,
            "quelle": quelle,
        }


class HeishamonCopGemessenSensor(HeishamonEntity, SensorEntity):
    """COP aus berechneter Waermeleistung und externem Strommesser."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:heat-pump"

    def __init__(
        self, coordinator, host: str, betriebsart: str, kennung: str, power_entity: str
    ) -> None:
        super().__init__(coordinator, host)
        self._betriebsart = betriebsart
        self._power_entity = power_entity
        self._attr_translation_key = f"{kennung}_measured"
        self._attr_unique_id = f"heishamon_{host}_{kennung}_measured"
        self.entity_id = f"sensor.heishamon_{slug_host(host)}_{kennung}_measured"

    def _elektrisch(self) -> float | None:
        zustand = self.hass.states.get(self._power_entity) if self.hass else None
        if zustand is None:
            return None
        return leistung_in_watt(
            zustand.state, zustand.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        )

    def _werte(self):
        data = self.coordinator.data or {}
        if not verdichter_laeuft(data) or not betriebsart_aktiv(data, self._betriebsart):
            return None, None
        thermisch = thermische_leistung(data, data.get(ROH_SCHLUESSEL))
        return thermisch, self._elektrisch()

    @property
    def native_value(self):
        thermisch, elektrisch = self._werte()
        return cop(thermisch, elektrisch)

    @property
    def extra_state_attributes(self):
        thermisch, elektrisch = self._werte()
        return {
            "thermische_leistung_w": round(thermisch) if thermisch is not None else None,
            "elektrische_leistung_w": elektrisch,
            "strommesser": self._power_entity,
        }
