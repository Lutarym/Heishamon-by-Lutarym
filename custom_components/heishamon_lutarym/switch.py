"""Schalter fuer HeishaMon-Kommandos."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SWITCH_COMMANDS
from .entity import HeishamonEntity
from .names_de import COMMAND_NAMES_DE

# Kommando -> Topic, das den Zustand zurueckmeldet.
STATE_TOPICS = {
    "SetHeatpump": "TOP0",
    "SetForceDHW": "TOP2",
    "SetHolidayMode": "TOP19",
    "SetMainSchedule": "TOP13",
    "SetForceDefrost": "TOP26",
    "SetForceSterilization": "TOP69",
    "SetForceHeater": "TOP68",
    "SetAltExternalSensor": "TOP108",
    "SetBuffer": "TOP99",
    "SetExternalControl": "TOP119",
    "SetExternalError": "TOP121",
    "SetExternalCompressorControl": "TOP122",
    "SetBivalentControl": "TOP129",
    "SetDHWHeaterState": "TOP58",
    "SetRoomHeaterState": "TOP59",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt Schalter an, wenn Steuerung erlaubt ist."""
    data = hass.data[DOMAIN][entry.entry_id]
    if data["listening_only"]:
        return

    async_add_entities(
        HeishamonSwitch(data["coordinator"], data["api"], data["host"], cmd, info)
        for cmd, info in SWITCH_COMMANDS.items()
    )


class HeishamonSwitch(HeishamonEntity, SwitchEntity):
    """Ein Ein-Aus-Kommando."""

    def __init__(self, coordinator, api, host: str, command: str, info: dict) -> None:
        super().__init__(coordinator, host)
        self._api = api
        self._command = command
        self._state_topic = STATE_TOPICS.get(command)

        self._attr_unique_id = f"heishamon_{host}_{command.lower()}"
        self.entity_id = f"switch.heishamon_{command.lower()}"
        self._attr_name = COMMAND_NAMES_DE.get(command, command)
        self._attr_icon = info.get("icon")

    @property
    def is_on(self) -> bool | None:
        """Zustand aus dem zugehoerigen Topic, sonst unbekannt."""
        if self._state_topic is None or not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self._state_topic)
        if value is None:
            return None
        try:
            return int(value) > 0
        except (TypeError, ValueError):
            return None

    async def _async_send(self, value: int) -> None:
        if await self._api.async_set_value(self._command, value):
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        """Schaltet ein."""
        await self._async_send(1)

    async def async_turn_off(self, **kwargs) -> None:
        """Schaltet aus."""
        await self._async_send(0)
