"""Auswahllisten fuer Betriebsmodi und die Quelle des COP."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, SELECT_COMMANDS, slug_host
from .cop import QUELLE_GEMESSEN, QUELLE_WAERMEPUMPE
from .entity import HeishamonEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt die COP-Quelle an und, wenn Steuerung erlaubt ist, die Modi."""
    data = hass.data[DOMAIN][entry.entry_id]
    host = data["host"]
    entities: list[SelectEntity] = []

    # Die Quelle ist keine Steuerung der Waermepumpe und gibt es daher
    # auch im Nur-Lesen-Betrieb. Ohne Strommesser gibt es nur eine Quelle.
    if data.get("power_entity"):
        entities.append(HeishamonCopQuelle(data["coordinator"], host, data["cop_quelle"]))
    else:
        registry = er.async_get(hass)
        alte_id = registry.async_get_entity_id(
            "select", DOMAIN, f"heishamon_{host}_cop_source"
        )
        if alte_id:
            registry.async_remove(alte_id)

    if not data["listening_only"]:
        entities.extend(
            HeishamonSelect(data["coordinator"], data["api"], host, cmd, info)
            for cmd, info in SELECT_COMMANDS.items()
        )

    async_add_entities(entities)


class HeishamonSelect(HeishamonEntity, SelectEntity):
    """Modusauswahl mit Rueckmeldung.

    Die Optionen sind sprachneutrale Schluessel (mode_0, mode_1, ...).
    Den sichtbaren Text liefert Home Assistant aus
    translations/<sprache>.json unter entity.select.<key>.state.
    """

    def __init__(self, coordinator, api, host: str, command: str, info: dict) -> None:
        super().__init__(coordinator, host)
        self._api = api
        self._command = command
        self._state_topic = info.get("state_topic")

        self._attr_unique_id = f"heishamon_{host}_{command.lower()}"
        self.entity_id = f"select.heishamon_{slug_host(host)}_{command.lower()}"
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
        key = f"mode_{index}"
        return key if key in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        """Setzt den gewaehlten Modus."""
        index = self._attr_options.index(option)
        if await self._api.async_set_value(self._command, index):
            await self.coordinator.async_request_refresh()


class HeishamonCopQuelle(HeishamonEntity, SelectEntity, RestoreEntity):
    """Waehlt, ob der COP aus Waermepumpenwerten oder gemessen angezeigt wird.

    Die Wahl bleibt ueber einen Neustart erhalten.
    """

    _attr_translation_key = "cop_source"
    _attr_icon = "mdi:swap-horizontal"
    _attr_options = [QUELLE_WAERMEPUMPE, QUELLE_GEMESSEN]

    def __init__(self, coordinator, host: str, wahl) -> None:
        super().__init__(coordinator, host)
        self._wahl = wahl
        self._attr_unique_id = f"heishamon_{host}_cop_source"
        self.entity_id = f"select.heishamon_{slug_host(host)}_cop_source"

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
