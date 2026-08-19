"""Heishamon by Lutarym."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HeishamonAPI
from .config_flow import einstellung
from .const import (
    CONF_HOST,
    CONF_LISTENING_ONLY,
    CONF_PASSWORD,
    CONF_STABILIZE,
    CONF_STABILIZE_COUNT,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_LISTENING_ONLY,
    DEFAULT_STABILIZE,
    DEFAULT_STABILIZE_COUNT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    HEISHAMON_TOPICS,
)

_LOGGER = logging.getLogger(__name__)

# So viele Abfragen in Folge duerfen fehlschlagen, bevor die Entitaeten
# als nicht verfuegbar gelten. Bei fuenf Sekunden Takt sind das 15 Sekunden.
TOLERIERTE_FEHLER = 3

PLATFORMS = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet einen Heishamon-Eintrag ein."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    api = HeishamonAPI(
        hass,
        host=host,
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )

    # Nachtraeglich geaenderte Optionen haben Vorrang vor der Ersteinrichtung.
    update_interval = einstellung(entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    listening_only = einstellung(entry, CONF_LISTENING_ONLY, DEFAULT_LISTENING_ONLY)

    stabilisieren = einstellung(entry, CONF_STABILIZE, DEFAULT_STABILIZE)
    noetige_wiederholungen = einstellung(
        entry, CONF_STABILIZE_COUNT, DEFAULT_STABILIZE_COUNT
    )
    # Merkt sich je Topic den zuletzt gemeldeten Wert und den Anwaerter.
    verlauf: dict[str, dict] = {}

    def _beruhige(data: dict) -> dict:
        """Uebernimmt einen geaenderten Temperaturwert erst nach Bestaetigung.

        Die Waermepumpe liefert Temperaturen nur in ganzen Grad. Liegt der
        echte Wert dazwischen, wechselt die Meldung staendig zwischen zwei
        Schritten. Ein neuer Wert gilt daher erst, wenn er mehrfach
        hintereinander gemeldet wurde. Gemittelt wird nichts.
        """
        if not stabilisieren:
            return data
        for topic, wert in list(data.items()):
            beschreibung = HEISHAMON_TOPICS.get(topic)
            if not beschreibung or beschreibung.get("device_class") != "temperature":
                continue
            eintrag = verlauf.get(topic)
            if eintrag is None:
                verlauf[topic] = {"gemeldet": wert, "anwaerter": wert, "zaehler": 0}
                continue
            # Ein Sprung ueber ein Grad ist eine echte Aenderung und gilt
            # sofort. Das Zappeln betraegt genau einen Schritt, alles
            # Groessere darf nicht verzoegert werden.
            try:
                gross = abs(float(wert) - float(eintrag["gemeldet"])) > 1
            except (TypeError, ValueError):
                gross = False

            if gross:
                eintrag["gemeldet"] = wert
                eintrag["anwaerter"] = wert
                eintrag["zaehler"] = 0
            elif wert == eintrag["gemeldet"]:
                eintrag["anwaerter"] = wert
                eintrag["zaehler"] = 0
            elif wert == eintrag["anwaerter"]:
                eintrag["zaehler"] += 1
                if eintrag["zaehler"] >= noetige_wiederholungen:
                    eintrag["gemeldet"] = wert
                    eintrag["zaehler"] = 0
            else:
                eintrag["anwaerter"] = wert
                eintrag["zaehler"] = 1
            data[topic] = eintrag["gemeldet"]
        return data

    # Zaehlt aufeinanderfolgende Fehlschlaege. Kurze Aussetzer werden
    # ueberbrueckt, damit der Verlauf keine Luecken bekommt. Erst wenn die
    # Platine laenger nicht antwortet, gelten die Werte als ungueltig.
    fehler = {"anzahl": 0}
    letzte_daten: dict = {}

    async def _async_update_data():
        try:
            data = await api.async_get_data()
        except Exception as err:  # noqa: BLE001
            fehler["anzahl"] += 1
            if fehler["anzahl"] <= TOLERIERTE_FEHLER and letzte_daten:
                _LOGGER.warning(
                    "Heishamon %s antwortete nicht (%d von %d toleriert): %s",
                    host,
                    fehler["anzahl"],
                    TOLERIERTE_FEHLER,
                    err,
                )
                return letzte_daten
            raise UpdateFailed(f"Heishamon {host}: {err}") from err

        if not data:
            fehler["anzahl"] += 1
            if fehler["anzahl"] <= TOLERIERTE_FEHLER and letzte_daten:
                _LOGGER.warning(
                    "Heishamon %s lieferte keine Topics (%d von %d toleriert)",
                    host,
                    fehler["anzahl"],
                    TOLERIERTE_FEHLER,
                )
                return letzte_daten
            raise UpdateFailed(f"Heishamon {host} lieferte keine Topics")

        fehler["anzahl"] = 0
        beruhigt = _beruhige(data)
        letzte_daten.clear()
        letzte_daten.update(beruhigt)
        return beruhigt

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"Heishamon {host}",
        update_method=_async_update_data,
        update_interval=timedelta(seconds=update_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    _LOGGER.info(
        "Heishamon %s eingerichtet, %d Topics gelesen, Takt %d s, %s",
        host,
        len(coordinator.data),
        update_interval,
        "nur lesen" if listening_only else "mit Steuerung",
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "listening_only": listening_only,
        "host": host,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entlaedt einen Eintrag."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Laedt den Eintrag nach Optionsaenderung neu."""
    await hass.config_entries.async_reload(entry.entry_id)
