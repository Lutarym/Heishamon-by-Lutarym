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
from .const import (
    CONF_HOST,
    CONF_LISTENING_ONLY,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_LISTENING_ONLY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

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

    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    listening_only = entry.data.get(CONF_LISTENING_ONLY, DEFAULT_LISTENING_ONLY)

    async def _async_update_data():
        try:
            data = await api.async_get_data()
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Heishamon {host}: {err}") from err
        if not data:
            raise UpdateFailed(f"Heishamon {host} lieferte keine Topics")
        return data

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
        "Heishamon %s eingerichtet, %d Topics gelesen", host, len(coordinator.data)
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
