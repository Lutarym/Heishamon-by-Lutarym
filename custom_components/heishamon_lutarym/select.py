"""Auswahllisten fuer Betriebsmodi."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SELECT_COMMANDS
from .entity import HeishamonEntity
from .names_de import COMMAND_NAMES_DE


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt Auswahllisten an, wenn Steuerung erlaubt ist."""
    data = hass.data[DOMAIN][entry.entry_id]
    if data["listening_only"]:
        return

    async_add_entities(
        HeishamonSelect(data["coordinator"], data["api"], data["host"], cmd, info)
        for cmd, info in SELECT_COMMANDS.items()
    )


class HeishamonSelect(HeishamonEntity, SelectEntity):
    """Modusauswahl mit Rueckmeldung."""

    def __init__(self, coordinator, api, host: str, command: str, info: dict) -> None:
        super().__init__(coordinator, host)
        self._api = api
        self._command = command
        self._state_topic = info.get("state_topic")

        self._attr_unique_id = f"heishamon_{host}_{command.lower()}"
        self.entity_id = f"select.heishamon_{command.lower()}"
        self._attr_name = COMMAND_NAMES_DE.get(command, command)
        self._attr_icon = info.get("icon")
        self._attr_options = list(info["options"])

    @property
    def current_option(self) -> str | None:
        """Aktueller Modus, aus dem Status-Topic abgeleitet."""
        if self._state_topic is None or not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self._state_topic)
        try:
            index = int(value)
        except (TypeError, ValueError):
            return None
        if 0 <= index < len(self._attr_options):
            return self._attr_options[index]
        return None

    async def async_select_option(self, option: str) -> None:
        """Setzt den gewaehlten Modus."""
        index = self._attr_options.index(option)
        if await self._api.async_set_value(self._command, index):
            await self.coordinator.async_request_refresh()
