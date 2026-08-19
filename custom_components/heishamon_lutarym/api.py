"""Heishamon HTTP API Client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

# Der Webserver auf dem ESP bearbeitet nur eine Anfrage gleichzeitig und
# antwortet gelegentlich nicht. Ein einzelner Fehlschlag darf deshalb nicht
# gleich alle Entitaeten unverfuegbar machen.
VERSUCHE = 3
PAUSE_SEKUNDEN = 1.5
ZEITLIMIT_SEKUNDEN = 15


class HeishamonAPI:
    """Liest /json und schreibt ueber /command."""

    def __init__(self, hass, host: str, username: str | None = None,
                 password: str | None = None) -> None:
        self._hass = hass
        self.host = host
        self.username = username or None
        self.password = password or None
        self.base_url = f"http://{host}"

    @property
    def _auth(self) -> aiohttp.BasicAuth | None:
        if self.username and self.password:
            return aiohttp.BasicAuth(self.username, self.password)
        return None

    async def async_get_data(self) -> dict[str, Any]:
        """Holt /json und wandelt es in ein flaches Dict um.

        HeishaMon liefert:
        {"heatpump":[{"Topic":"TOP0","Name":"...","Value":1,"Description":"On"}, ...],
         "heatpump extra":[{"Topic":"XTOP0",...}], "1wire":[...], "s0":[...]}

        Ergebnis: {"TOP0": 1, "TOP0_desc": "On", "XTOP0": ...}
        """
        session = async_get_clientsession(self._hass)
        url = f"{self.base_url}/json"
        letzter_fehler: Exception | None = None

        for versuch in range(1, VERSUCHE + 1):
            try:
                async with session.get(
                    url,
                    auth=self._auth,
                    timeout=aiohttp.ClientTimeout(total=ZEITLIMIT_SEKUNDEN),
                ) as response:
                    response.raise_for_status()
                    # HeishaMon sendet application/json, wir erzwingen das
                    # Parsen unabhaengig vom Content-Type, damit aeltere
                    # Firmware nicht scheitert.
                    raw = await response.json(content_type=None)
                if versuch > 1:
                    _LOGGER.debug(
                        "Heishamon %s antwortete erst im %d. Versuch",
                        self.host,
                        versuch,
                    )
                return self._flatten(raw)
            except ValueError as err:
                # Ungueltiges JSON deutet auf eine abgeschnittene Antwort hin.
                letzter_fehler = err
                _LOGGER.warning(
                    "Heishamon %s: Antwort nicht lesbar (Versuch %d): %s",
                    self.host,
                    versuch,
                    err,
                )
                if versuch < VERSUCHE:
                    await asyncio.sleep(PAUSE_SEKUNDEN)
                continue
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                letzter_fehler = err
                if versuch < VERSUCHE:
                    await asyncio.sleep(PAUSE_SEKUNDEN)

        raise letzter_fehler if letzter_fehler else RuntimeError("Abfrage fehlgeschlagen")

    @staticmethod
    def _flatten(raw: Any) -> dict[str, Any]:
        """Baut aus den Listen ein Dict Topic -> Wert."""
        result: dict[str, Any] = {}
        fehlende: list[str] = []

        if not isinstance(raw, dict):
            _LOGGER.error("Unerwartetes JSON-Format von HeishaMon: %s", type(raw))
            return result

        for section, entries in raw.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                topic = entry.get("Topic")
                if not topic:
                    continue
                wert = entry.get("Value")
                if wert is None:
                    # Laut Firmware liefert jedes Topic immer eine Zahl.
                    # Fehlt sie, stimmt etwas mit der Antwort nicht. Das
                    # wird festgehalten, damit die Ursache belegbar wird.
                    fehlende.append(topic)
                result[topic] = wert
                description = entry.get("Description")
                if description is not None:
                    result[f"{topic}_desc"] = description

        if fehlende:
            _LOGGER.warning(
                "HeishaMon lieferte %d Topics ohne Wert: %s (von %d insgesamt)",
                len(fehlende),
                ", ".join(fehlende[:15]),
                len(result),
            )

        if not result:
            _LOGGER.warning(
                "HeishaMon lieferte keine Topics. Bekannte Sektionen: %s",
                list(raw.keys()),
            )
        return result

    async def async_set_value(self, command: str, value: Any) -> bool:
        """Sendet /command?Kommando=Wert."""
        session = async_get_clientsession(self._hass)
        url = f"{self.base_url}/command"
        try:
            async with session.get(
                url, params={command: value}, auth=self._auth,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                if response.status != 200:
                    _LOGGER.error("%s=%s fehlgeschlagen: HTTP %s",
                                  command, value, response.status)
                    return False
                return True
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Fehler beim Senden von %s=%s: %s", command, value, err)
            return False

    async def test_connection(self) -> bool:
        """Prueft, ob /json erreichbar ist und Topics liefert."""
        try:
            data = await self.async_get_data()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Verbindungstest zu %s fehlgeschlagen: %s", self.base_url, err)
            return False
        return bool(data)
