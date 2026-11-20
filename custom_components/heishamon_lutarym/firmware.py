"""Prueft, ob fuer HeishaMon eine neuere Firmware veroeffentlicht ist.

Installiert: aus der Startseite der Platine (api.async_get_firmware_version).

Neueste: Die HeishaMon-Entwickler markieren alle GitHub-Releases als
Vorabversion. Die gueltige Produktionsversion steht deshalb nicht in der
GitHub-Releaseliste, sondern in binaries/README.md im Satz
"The latest production release is vX.Y.Z." Diesen Satz pflegt der
Release-Ablauf des Projekts bei jeder Veroeffentlichung.
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PRUEF_TAKT = timedelta(hours=6)
QUELLE_NEUESTE = (
    "https://raw.githubusercontent.com/heishamon/HeishaMon/main/binaries/README.md"
)
RELEASE_URL = "https://github.com/heishamon/HeishaMon/releases/tag/{version}"
BINARIES_URL = "https://github.com/heishamon/HeishaMon/tree/main/binaries"
_NEUESTE_MUSTER = re.compile(r"latest production release is (v?\d+\.\d+\.\d+)")
_VERSION_MUSTER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def versionsnummer(version: str | None) -> tuple[int, int, int] | None:
    """v4.2.3 -> (4, 2, 3). Nightly, Alpha oder Local build -> None."""
    if not version:
        return None
    treffer = _VERSION_MUSTER.match(version.strip())
    if not treffer:
        return None
    return tuple(int(teil) for teil in treffer.groups())


class FirmwareCoordinator(DataUpdateCoordinator):
    """Liest alle 6 Stunden die installierte und die neueste Version."""

    def __init__(self, hass, api, entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"Heishamon {api.host} Firmware",
            update_interval=PRUEF_TAKT,
        )
        self._api = api
        self._daten: dict[str, str | None] = {"installiert": None, "neueste": None}

    async def _async_update_data(self) -> dict[str, str | None]:
        # Ein Fehler bei einer der beiden Quellen behaelt den letzten Wert
        try:
            installiert = await self._api.async_get_firmware_version()
            if installiert:
                self._daten["installiert"] = installiert
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Firmware-Version von %s nicht lesbar: %s", self._api.host, err)
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                QUELLE_NEUESTE, timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                response.raise_for_status()
                text = await response.text()
            treffer = _NEUESTE_MUSTER.search(text)
            if treffer:
                neueste = treffer.group(1)
                self._daten["neueste"] = neueste if neueste.startswith("v") else f"v{neueste}"
            else:
                _LOGGER.warning("Neueste HeishaMon-Version nicht in %s gefunden", QUELLE_NEUESTE)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Neueste HeishaMon-Version nicht abrufbar: %s", err)
        return dict(self._daten)
