"""Auswahllisten fuer Betriebsmodi und die Quelle des COP."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, OPTIONAL_SELECTS, SELECT_COMMANDS
from .cop import QUELLE_GEMESSEN, QUELLE_WAERMEPUMPE
from .entity import Geraet, HeishamonBefehlEntity, HeishamonEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt die COP-Quelle an und, wenn Steuerung erlaubt ist, die Modi."""
    data = hass.data[DOMAIN][entry.entry_id]
    geraet: Geraet = data["geraet"]
    coordinator = data["coordinator"]
    entities: list[SelectEntity] = []

    # Die Quelle ist keine Steuerung der Waermepumpe und gibt es daher
    # auch im Nur-Lesen-Betrieb. Ohne Strommesser gibt es nur eine Quelle.
    if data.get("power_entity"):
        entities.append(HeishamonCopQuelle(coordinator, geraet, data["cop_quelle"]))
    else:
        registry = er.async_get(hass)
        alte_id = registry.async_get_entity_id(
            "select", DOMAIN, f"heishamon_{geraet.kennung}_cop_source"
        )
        if alte_id:
            registry.async_remove(alte_id)

    if not data["listening_only"]:
        entities.extend(
            HeishamonSelect(coordinator, geraet, data["api"], cmd, info)
            for cmd, info in SELECT_COMMANDS.items()
        )
        if data["optional_pcb"]:
            entities.extend(
                HeishamonOptionalSelect(coordinator, geraet, data["api"], cmd, info)
                for cmd, info in OPTIONAL_SELECTS.items()
            )

    async_add_entities(entities)


class HeishamonSelect(HeishamonBefehlEntity, SelectEntity):
    """Modusauswahl mit Rueckmeldung.

    Die Optionen sind sprachneutrale Schluessel (mode_0, mode_1, ...).
    Den sichtbaren Text liefert Home Assistant aus
    translations/<sprache>.json unter entity.select.<key>.state.
    """

    def __init__(self, coordinator, geraet: Geraet, api, command: str, info: dict) -> None:
        super().__init__(coordinator, geraet, api)
        self._command = command
        self._state_topic = info.get("state_topic")
        self._zuordnung = info.get("zuordnung", {})
        self._ids("select", command.lower())
        self._attr_translation_key = command.lower()
        self._attr_icon = info.get("icon")
        self._attr_options = [f"mode_{i}" for i in range(info["option_count"])]

    @property
    def current_option(self) -> str | None:
        """Aktueller Modus, aus dem Status-Topic abgeleitet."""
        if self._state_topic is None or not self.coordinator.data:
            return None
        try:
            index = int(self.coordinator.data.get(self._state_topic))
        except (TypeError, ValueError):
            return None
        index = self._zuordnung.get(index, index)
        key = f"mode_{index}"
        return key if key in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        """Setzt den gewaehlten Modus."""
        await self._sende(self._command, self._attr_options.index(option))


class HeishamonOptionalSelect(HeishamonBefehlEntity, SelectEntity, RestoreEntity):
    """Auswahl der emulierten Optional-Platine.

    HeishaMon meldet den Wert nicht zurueck. Angezeigt wird der zuletzt
    gesetzte Wert, er bleibt ueber einen Neustart erhalten.
    """

    def __init__(self, coordinator, geraet: Geraet, api, command: str, info: dict) -> None:
        super().__init__(coordinator, geraet, api)
        self._command = command
        self._ids("select", command.lower())
        self._attr_translation_key = command.lower()
        self._attr_icon = info.get("icon")
        self._attr_options = [f"mode_{i}" for i in range(info["option_count"])]
        self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        letzter = await self.async_get_last_state()
        if letzter is not None and letzter.state in self._attr_options:
            self._attr_current_option = letzter.state

    async def async_select_option(self, option: str) -> None:
        await self._sende(
            self._command, self._attr_options.index(option), aktualisieren=False
        )
        self._attr_current_option = option
        self.async_write_ha_state()


class HeishamonCopQuelle(HeishamonEntity, SelectEntity, RestoreEntity):
    """Waehlt, ob der COP aus Waermepumpenwerten oder gemessen angezeigt wird.

    Die Wahl bleibt ueber einen Neustart erhalten.
    """

    _attr_translation_key = "cop_source"
    _attr_icon = "mdi:swap-horizontal"
    _attr_options = [QUELLE_WAERMEPUMPE, QUELLE_GEMESSEN]

    def __init__(self, coordinator, geraet: Geraet, wahl) -> None:
        super().__init__(coordinator, geraet)
        self._wahl = wahl
        self._ids("select", "cop_source")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        letzter = await self.async_get_last_state()
        if letzter is not None and letzter.state in self._attr_options:
            self._wahl.setzen(letzter.state)

    @property
    def available(self) -> bool:
        """Die Wahl ist unabhaengig von der Erreichbarkeit der Platine."""
        return True

    @property
    def current_option(self) -> str:
        return self._wahl.wert

    async def async_select_option(self, option: str) -> None:
        self._wahl.setzen(option)
        self.async_write_ha_state()
