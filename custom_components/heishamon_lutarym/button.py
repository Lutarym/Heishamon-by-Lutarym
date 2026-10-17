"""Taster fuer einmalige Befehle."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import Geraet, HeishamonBefehlEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt Taster an, wenn Steuerung erlaubt ist."""
    data = hass.data[DOMAIN][entry.entry_id]
    if data["listening_only"]:
        return
    async_add_entities([HeishamonFehlerReset(data["coordinator"], data["geraet"], data["api"])])


class HeishamonFehlerReset(HeishamonBefehlEntity, ButtonEntity):
    """Quittiert einen anstehenden Fehler der Waermepumpe (etwa H72).

    Entspricht der Reset-Taste an der Fernbedienung CZ-TAW1 bzw. am
    Innengeraet (SetReset=1 laut HeishaMon MQTT-Topics.md, SET48).
    """

    _attr_translation_key = "setreset"
    _attr_icon = "mdi:alert-remove"

    def __init__(self, coordinator, geraet: Geraet, api) -> None:
        super().__init__(coordinator, geraet, api)
        self._ids("button", "setreset")

    async def async_press(self) -> None:
        await self._sende("SetReset", 1)
