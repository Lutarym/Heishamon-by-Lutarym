"""Switch platform for Heishamon by Lutarym."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .api import HeishamonAPI

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    listening_only = entry.data.get("listening_only", True)
    
    if not listening_only:
        switches = [
            HeishamonSwitch(coordinator, api, "SetHeatpump", "Heatpump Power", "TOP0"),
            HeishamonSwitch(coordinator, api, "SetForceDefrost", "Force Defrost", "TOP26"),
            HeishamonSwitch(coordinator, api, "SetForceSterilization", "Force Sterilization", "TOP69"),
            HeishamonSwitch(coordinator, api, "SetForceDHW", "Force DHW", "TOP2"),
            HeishamonSwitch(coordinator, api, "SetForceHeater", "Force Heater", "TOP68"),
        ]
        async_add_entities(switches)


class HeishamonSwitch(SwitchEntity):
    """Heishamon switch entity."""

    def __init__(self, coordinator: DataUpdateCoordinator, api: HeishamonAPI, set_command: str, name: str, topic_id: str):
        """Initialize switch."""
        self.coordinator = coordinator
        self.api = api
        self.set_command = set_command
        self.topic_id = topic_id
        self._attr_unique_id = f"heishamon_{set_command.lower()}"
        self._attr_name = name
        self._attr_icon = "mdi:power"

    @property
    def available(self) -> bool:
        """Return availability."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return switch state."""
        if self.coordinator.data:
            return bool(self.coordinator.data.get(self.topic_id, {}).get("value"))
        return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on."""
        success = await self.api.async_set_value(self.set_command, 1)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off."""
        success = await self.api.async_set_value(self.set_command, 0)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
