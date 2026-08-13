"""Sensoren fuer alle HeishaMon-Topics."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HEISHAMON_TOPICS
from .entity import HeishamonEntity
from .names_de import TOPIC_NAMES_DE


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt fuer jedes Topic einen Sensor an."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    host = data["host"]

    async_add_entities(
        HeishamonSensor(coordinator, host, topic_id, info)
        for topic_id, info in HEISHAMON_TOPICS.items()
        if info["type"] == "sensor"
    )


class HeishamonSensor(HeishamonEntity, SensorEntity):
    """Ein einzelnes HeishaMon-Topic."""

    def __init__(self, coordinator, host: str, topic_id: str, info: dict) -> None:
        super().__init__(coordinator, host)
        self._topic_id = topic_id
        self._info = info

        self._attr_unique_id = f"heishamon_{host}_{topic_id.lower()}"
        self.entity_id = f"sensor.heishamon_{topic_id.lower()}"
        self._attr_name = f"{topic_id} {TOPIC_NAMES_DE.get(topic_id, info['name'])}"
        self._attr_icon = info.get("icon")

        if info["numeric"]:
            if info.get("unit"):
                self._attr_native_unit_of_measurement = info["unit"]
            if info.get("device_class"):
                self._attr_device_class = info["device_class"]
            # State-Class nur bei echten Messgroessen, sonst meckert der Recorder.
            if info.get("unit"):
                self._attr_state_class = SensorStateClass.MEASUREMENT

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
