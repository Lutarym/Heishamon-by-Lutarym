"""Heishamon by Lutarym - Home Assistant Integration for Panasonic Aquarea Heat Pumps."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HeishamonAPI
from .const import DOMAIN, CONF_HOST, CONF_UPDATE_INTERVAL, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number", "select", "switch", "climate"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heishamon from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = HeishamonAPI(
        host=entry.data[CONF_HOST],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )

    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, 30)

    async def async_update_data():
        """Fetch data from Heishamon."""
        try:
            return await api.async_get_data()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Heishamon: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Heishamon",
        update_method=async_update_data,
        update_interval=timedelta(seconds=update_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
