"""Einstellbare Werte."""
from __future__ import annotations

import json

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    NUMBER_COMMANDS,
    OPTIONAL_NUMBERS,
    ZONE_DIREKT,
    ZONE_MODUS_TOPIC,
    ZONE_VERSCHIEBUNG,
)
from .entity import Geraet, HeishamonBefehlEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt einstellbare Werte nur an, wenn Steuerung erlaubt ist."""
    data = hass.data[DOMAIN][entry.entry_id]
    if data["listening_only"]:
        return
    geraet: Geraet = data["geraet"]
    coordinator = data["coordinator"]
    api = data["api"]

    entities: list[NumberEntity] = [
        HeishamonNumber(coordinator, geraet, api, topic_id, info)
        for topic_id, info in NUMBER_COMMANDS.items()
    ]
    if data["optional_pcb"]:
        entities.extend(
            HeishamonOptionalNumber(coordinator, geraet, api, command, info)
            for command, info in OPTIONAL_NUMBERS.items()
        )
    async_add_entities(entities)


def _als_text(wert: float, schritt: float) -> str:
    """Ganze Zahlen ohne Nachkomma senden, die Firmware liest sie mit toInt."""
    if float(schritt).is_integer():
        return str(int(round(wert)))
    return f"{wert:g}"


def _pruefe(wert: float, minimum: float, maximum: float, schritt: float) -> None:
    """Prueft Bereich und Schrittweite.

    Die Platine verwirft ungueltige Werte ohne Rueckmeldung. Deshalb wird
    hier vorher geprueft und ein Fehler in der Oberflaeche angezeigt.
    """
    if wert < minimum or wert > maximum:
        raise ServiceValidationError(
            f"{wert:g} liegt ausserhalb von {minimum:g} bis {maximum:g}"
        )
    abstand = (wert - minimum) / schritt
    if abs(abstand - round(abstand)) > 1e-6:
        raise ServiceValidationError(
            f"{wert:g} passt nicht zur Schrittweite {schritt:g} ab {minimum:g}"
        )


class HeishamonNumber(HeishamonBefehlEntity, NumberEntity):
    """Einstellbarer Wert mit Rueckmeldung aus einem Topic."""

    def __init__(self, coordinator, geraet: Geraet, api, topic_id: str, info: dict) -> None:
        super().__init__(coordinator, geraet, api)
        self._topic_id = topic_id
        self._command = info["command"]
        self._kurve = info.get("kurve")
        self._zone = info.get("zone")
        self._min = info.get("min")
        self._max = info.get("max")
        self._attr_native_step = info.get("step", 1)
        self._attr_native_unit_of_measurement = info.get("unit")
        if info.get("box"):
            self._attr_mode = NumberMode.BOX
        self._ids("number", topic_id.lower(), "_set")
        self._attr_translation_key = topic_id.lower()
        self._attr_icon = "mdi:tune-vertical"

    def _bereich(self) -> tuple[float, float]:
        """Gueltiger Bereich. Bei Zonen abhaengig von Heizkurve oder direkt."""
        if not self._zone:
            return self._min, self._max
        verschiebung = ZONE_VERSCHIEBUNG
        direkt = ZONE_DIREKT[self._zone]
        modus = (self.coordinator.data or {}).get(ZONE_MODUS_TOPIC[self._zone])
        try:
            modus = int(modus)
        except (TypeError, ValueError):
            modus = None
        if modus == 0:
            return verschiebung
        if modus == 1:
            return direkt
        # Modus unbekannt: beide Bereiche zulassen, die Luecke prueft
        # async_set_native_value.
        return min(verschiebung[0], direkt[0]), max(verschiebung[1], direkt[1])

    @property
    def native_min_value(self) -> float:
        return self._bereich()[0]

    @property
    def native_max_value(self) -> float:
        return self._bereich()[1]

    @property
    def native_value(self):
        """Aktueller Wert aus dem Rueckmelde-Topic."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._topic_id)

    @property
    def extra_state_attributes(self):
        if self._zone:
            modus = (self.coordinator.data or {}).get(ZONE_MODUS_TOPIC[self._zone])
            return {"modus_topic": ZONE_MODUS_TOPIC[self._zone], "modus": modus}
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Prueft den Wert und sendet ihn an HeishaMon."""
        minimum, maximum = self._bereich()
        _pruefe(value, minimum, maximum, self._attr_native_step)
        if self._zone:
            verschiebung = ZONE_VERSCHIEBUNG
            direkt = ZONE_DIREKT[self._zone]
            in_verschiebung = verschiebung[0] <= value <= verschiebung[1]
            in_direkt = direkt[0] <= value <= direkt[1]
            if not (in_verschiebung or in_direkt):
                raise ServiceValidationError(
                    f"{value:g} ist weder eine Verschiebung "
                    f"({verschiebung[0]} bis {verschiebung[1]}) noch eine "
                    f"direkte Temperatur ({direkt[0]} bis {direkt[1]})"
                )

        text = _als_text(value, self._attr_native_step)
        if self._kurve:
            # Nur dieser eine Wert, damit die Anfrage in den 128-Byte-Puffer
            # der kleinen Platine passt. Fehlende Werte laesst die Firmware
            # unveraendert.
            zone, art, punkt, hoehe = self._kurve
            inhalt = {zone: {art: {punkt: {hoehe: int(text)}}}}
            await self._sende(self._command, json.dumps(inhalt, separators=(",", ":")))
        else:
            await self._sende(self._command, text)


class HeishamonOptionalNumber(HeishamonBefehlEntity, NumberEntity, RestoreEntity):
    """Wert fuer die emulierte Optional-Platine.

    HeishaMon meldet den gesetzten Wert nicht zurueck. Angezeigt wird der
    zuletzt gesetzte Wert, er bleibt ueber einen Neustart erhalten.
    """

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, geraet: Geraet, api, command: str, info: dict) -> None:
        super().__init__(coordinator, geraet, api)
        self._command = command
        self._attr_native_min_value = info["min"]
        self._attr_native_max_value = info["max"]
        self._attr_native_step = info["step"]
        self._attr_native_unit_of_measurement = info["unit"]
        self._attr_native_value = None
        self._ids("number", command.lower())
        self._attr_translation_key = command.lower()
        self._attr_icon = "mdi:expansion-card"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        letzter = await self.async_get_last_state()
        if letzter is not None:
            try:
                self._attr_native_value = float(letzter.state)
            except (TypeError, ValueError):
                self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        _pruefe(
            value,
            self._attr_native_min_value,
            self._attr_native_max_value,
            self._attr_native_step,
        )
        await self._sende(
            self._command, _als_text(value, self._attr_native_step), aktualisieren=False
        )
        self._attr_native_value = value
        self.async_write_ha_state()
