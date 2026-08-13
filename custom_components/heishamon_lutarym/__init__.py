"""Heishamon by Lutarym - Complete Integration."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import Platform

from .api import HeishamonAPI
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_LISTENING_ONLY,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SWITCH, Platform.SELECT, Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heishamon from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    
    _LOGGER.info(f"Setting up Heishamon at {host}")
    
    api = HeishamonAPI(
        host=host,
        username=username if username else None,
        password=password if password else None,
    )

    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    listening_only = entry.data.get(CONF_LISTENING_ONLY, True)

    async def async_update_data():
        """Fetch data from Heishamon."""
        try:
            _LOGGER.info(f"Fetching data from Heishamon {host}")
            data = await api.async_get_data()
            _LOGGER.info(f"Got {len(data) if data else 0} data points from Heishamon")
            if data and isinstance(data, dict):
                sample_keys = list(data.keys())[:3]
                _LOGGER.info(f"Sample data: {sample_keys}")
            return data
        except Exception as err:
            _LOGGER.error(f"Error fetching Heishamon data: {err}")
            raise UpdateFailed(f"Error communicating with Heishamon: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Heishamon",
        update_method=async_update_data,
        update_interval=timedelta(seconds=update_interval),
    )

    _LOGGER.info(f"Starting first refresh for Heishamon {host}")
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info(f"First refresh successful for Heishamon {host}")
    except UpdateFailed as ex:
        _LOGGER.error(f"Failed first refresh: {ex}")
        return False

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "listening_only": listening_only,
        "host": host,
    }

    _LOGGER.info(f"Setting up platforms for Heishamon {host}")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info(f"Heishamon {host} setup complete")
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
