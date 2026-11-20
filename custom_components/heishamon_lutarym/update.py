"""Zeigt an, ob fuer HeishaMon eine neuere Firmware veroeffentlicht ist.

Nur Anzeige, keine Installation: Die Firmware unterscheidet sich je nach
Platine (klein ESP8266, gross ESP32-S3). Eine falsche Datei macht die Platine
unbrauchbar, deshalb wird ueber die Weboberflaeche von HeishaMon aktualisiert.
"""
from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import Geraet, HeishamonEntity
from .firmware import BINARIES_URL, RELEASE_URL, versionsnummer


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HeishamonFirmwareUpdate(data["firmware"], data["geraet"])])


class HeishamonFirmwareUpdate(HeishamonEntity, UpdateEntity):
    """Installierte und neueste HeishaMon-Firmware."""

    _attr_translation_key = "firmware"
    _attr_title = "HeishaMon"

    def __init__(self, coordinator, geraet: Geraet) -> None:
        super().__init__(coordinator, geraet)
        self._ids("update", "firmware")

    @property
    def _daten(self) -> dict:
        return self.coordinator.data or {}

    @property
    def installed_version(self) -> str | None:
        return self._daten.get("installiert")

    @property
    def latest_version(self) -> str | None:
        neueste = self._daten.get("neueste")
        # Ohne bekannte neueste Version gilt die installierte als aktuell
        return neueste or self.installed_version

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Nur echte Versionsnummern vergleichen.

        Nightly-, Alpha- oder selbst gebaute Firmware hat keine vergleichbare
        Nummer und loest deshalb keine Update-Meldung aus.
        """
        neu = versionsnummer(latest_version)
        alt = versionsnummer(installed_version)
        if neu is None or alt is None:
            return False
        return neu > alt

    @property
    def release_url(self) -> str | None:
        neueste = self._daten.get("neueste")
        return RELEASE_URL.format(version=neueste) if neueste else BINARIES_URL
