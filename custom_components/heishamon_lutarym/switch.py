"""Schalter fuer HeishaMon-Kommandos."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, OPTIONAL_SWITCHES, STATE_TOPICS, SWITCH_COMMANDS
from .entity import Geraet, HeishamonBefehlEntity, HeishamonEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt Schalter an, wenn Steuerung erlaubt ist."""
    data = hass.data[DOMAIN][entry.entry_id]
    if data["listening_only"]:
        return
    geraet: Geraet = data["geraet"]
    entities: list[SwitchEntity] = [
        HeishamonSwitch(data["coordinator"], geraet, data["api"], cmd, info)
        for cmd, info in SWITCH_COMMANDS.items()
    ]
    if data["optional_pcb"]:
        entities.extend(
            HeishamonOptionalSwitch(data["coordinator"], geraet, data["api"], cmd, info)
            for cmd, info in OPTIONAL_SWITCHES.items()
        )
    if data.get("warmwasser") is not None:
        entities.append(
            HeishamonWarmwasserSchalter(data["coordinator"], geraet, data["warmwasser"])
        )
    async_add_entities(entities)


class HeishamonSwitch(HeishamonBefehlEntity, SwitchEntity):
    """Ein Ein-Aus-Kommando."""

    def __init__(self, coordinator, geraet: Geraet, api, command: str, info: dict) -> None:
        super().__init__(coordinator, geraet, api)
        self._command = command
        self._state_topic = STATE_TOPICS.get(command)
        self._ids("switch", command.lower())
        self._attr_translation_key = command.lower()
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

    async def async_turn_on(self, **kwargs) -> None:
        """Schaltet ein."""
        await self._sende(self._command, 1)

    async def async_turn_off(self, **kwargs) -> None:
        """Schaltet aus."""
        await self._sende(self._command, 0)


class HeishamonOptionalSwitch(HeishamonBefehlEntity, SwitchEntity, RestoreEntity):
    """Schalter der emulierten Optional-Platine.

    HeishaMon meldet den Zustand nicht zurueck. Angezeigt wird der zuletzt
    gesetzte Zustand, er bleibt ueber einen Neustart erhalten.
    """

    def __init__(self, coordinator, geraet: Geraet, api, command: str, info: dict) -> None:
        super().__init__(coordinator, geraet, api)
        self._command = command
        self._attr_is_on = None
        self._ids("switch", command.lower())
        self._attr_translation_key = command.lower()
        self._attr_icon = info.get("icon")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        letzter = await self.async_get_last_state()
        if letzter is not None and letzter.state in ("on", "off"):
            self._attr_is_on = letzter.state == "on"

    async def _setze(self, ein: bool) -> None:
        await self._sende(self._command, 1 if ein else 0, aktualisieren=False)
        self._attr_is_on = ein
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        await self._setze(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._setze(False)


class HeishamonWarmwasserSchalter(HeishamonEntity, SwitchEntity):
    """Schaltet "Warmwasser zur waermsten Tageszeit" ein oder aus.

    Der Zustand wird vom Planer gespeichert und bleibt nach einem Neustart
    erhalten. Ausschalten beendet eine laufende erzwungene Ladung.
    """

    _attr_translation_key = "dhw_warmest_time"
    _attr_icon = "mdi:weather-sunny"

    def __init__(self, coordinator, geraet: Geraet, planer) -> None:
        super().__init__(coordinator, geraet)
        self._planer = planer
        self._ids("switch", "dhw_warmest_time")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._planer.abonnieren(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._planer.aktiv

    async def async_turn_on(self, **kwargs) -> None:
        await self._planer.async_setze_aktiv(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._planer.async_setze_aktiv(False)
