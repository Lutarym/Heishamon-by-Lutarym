"""Gemeinsame Basisklasse fuer alle Heishamon-Entities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import HeishamonBefehlFehler
from .const import DOMAIN, slug_host


@dataclass(frozen=True)
class Geraet:
    """Adresse und dauerhafte Kennung eines HeishaMon.

    kennung ist die Adresse bei der Ersteinrichtung und bleibt gleich,
    auch wenn die Adresse spaeter geaendert wird. Darauf beruhen
    unique_id und Geraet in Home Assistant, damit Verlauf und Namen beim
    Adresswechsel erhalten bleiben.
    """

    host: str
    kennung: str

    @property
    def slug(self) -> str:
        return slug_host(self.kennung)


class HeishamonEntity(CoordinatorEntity):
    """Bindet jede Entity an dasselbe Geraet.

    has_entity_name muss True sein, damit Home Assistant die Namen
    aus translations/<sprache>.json uebernimmt.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, geraet: Geraet) -> None:
        super().__init__(coordinator)
        self._geraet = geraet
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, geraet.kennung)},
            name=f"Heishamon {geraet.kennung}",
            manufacturer="Panasonic",
            model="Aquarea",
            configuration_url=f"http://{geraet.host}",
        )

    def _ids(self, plattform: str, schluessel: str, unique_suffix: str = "") -> None:
        """Setzt unique_id und entity_id einheitlich."""
        self._attr_unique_id = f"heishamon_{self._geraet.kennung}_{schluessel}{unique_suffix}"
        self.entity_id = f"{plattform}.heishamon_{self._geraet.slug}_{schluessel}"


class HeishamonBefehlEntity(HeishamonEntity):
    """Basis fuer alle Entities, die Befehle senden."""

    def __init__(self, coordinator, geraet: Geraet, api) -> None:
        super().__init__(coordinator, geraet)
        self._api = api

    async def _sende(self, command: str, value: Any, aktualisieren: bool = True) -> None:
        """Sendet einen Befehl und zeigt Fehler in der Oberflaeche an."""
        try:
            await self._api.async_set_value(command, value)
        except HeishamonBefehlFehler as err:
            raise HomeAssistantError(
                f"HeishaMon {self._geraet.host} hat {command} nicht angenommen: {err}"
            ) from err
        if aktualisieren:
            await self.coordinator.async_request_refresh()
