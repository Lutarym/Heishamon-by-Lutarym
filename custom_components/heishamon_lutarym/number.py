"""Einstellbare Temperaturen."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HEISHAMON_TOPICS
from .entity import HeishamonEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt nur Number-Entities an, wenn Steuerung erlaubt ist."""
    data = hass.data[DOMAIN][entry.entry_id]
    if data["listening_only"]:
        return

    async_add_entities(
        HeishamonNumber(data["coordinator"], data["api"], data["host"], topic_id, info)
        for topic_id, info in HEISHAMON_TOPICS.items()
        if info["type"] == "number"
    )


class HeishamonNumber(HeishamonEntity, NumberEntity):
    """Schreibbarer Sollwert."""

    def __init__(self, coordinator, api, host: str, topic_id: str, info: dict) -> None:
        super().__init__(coordinator, host)
        self._api = api
        self._topic_id = topic_id
        self._set_command = info["set_command"]

        self._attr_unique_id = f"heishamon_{host}_{topic_id.lower()}_set"
        self.entity_id = f"number.heishamon_{topic_id.lower()}"
        self._attr_translation_key = topic_id.lower()
        self._attr_icon = info.get("icon")
        self._attr_native_unit_of_measurement = info.get("unit")
        self._attr_native_min_value = info["min"]
        self._attr_native_max_value = info["max"]
        self._attr_native_step = 1

    @property
    def native_value(self):
        """Aktueller Sollwert."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._topic_id)

    async def async_set_native_value(self, value: float) -> None:
        """Sendet den neuen Sollwert an HeishaMon."""
        if await self._api.async_set_value(self._set_command, int(value)):
            await self.coordinator.async_request_refresh()
