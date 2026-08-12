"""Heishamon by Lutarym - Complete Integration."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry, DeviceEntry
from homeassistant.helpers.entity_registry import EntityRegistry
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
    HEISHAMON_TOPICS,
    SET_COMMANDS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SWITCH, Platform.SELECT, Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heishamon from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    api = HeishamonAPI(
        host=host,
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )

    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    listening_only = entry.data.get(CONF_LISTENING_ONLY, True)

    async def async_update_data():
        """Fetch data from Heishamon."""
        try:
            data = await api.async_get_data()
            return data
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

    # Device Registry erstellen
    device_registry = DeviceRegistry(hass)
    device = device_registry.get_or_create_device(
        config_entry_id=entry.entry_id,
        connections={("network", host)},
        name=f"Heishamon {host}",
        manufacturer="Panasonic",
        model="Aquarea Heat Pump",
        identifiers={(DOMAIN, host)},
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "device": device,
        "listening_only": listening_only,
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
