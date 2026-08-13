"""Gemeinsame Basisklasse fuer alle Heishamon-Entities."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class HeishamonEntity(CoordinatorEntity):
    """Bindet jede Entity an dasselbe Geraet.

    has_entity_name muss True sein, damit Home Assistant die Namen
    aus translations/<sprache>.json uebernimmt.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, host: str) -> None:
        super().__init__(coordinator)
        self._host = host
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=f"Heishamon {host}",
            manufacturer="Panasonic",
            model="Aquarea",
            configuration_url=f"http://{host}",
        )
