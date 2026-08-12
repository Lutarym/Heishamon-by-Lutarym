"""Select platform for Heishamon."""
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from .const import DOMAIN, SET_COMMANDS
from .api import HeishamonAPI

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up selects."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    device = hass.data[DOMAIN][entry.entry_id]["device"]
    listening_only = hass.data[DOMAIN][entry.entry_id]["listening_only"]
    
    if not listening_only:
        selects = [HeishamonSelect(coordinator, api, device, cmd, info) for cmd, info in SET_COMMANDS.items() if info["type"] == "select"]
        async_add_entities(selects)

class HeishamonSelect(CoordinatorEntity, SelectEntity):
    """Heishamon select entity."""
    
    def __init__(self, coordinator: DataUpdateCoordinator, api: HeishamonAPI, device, set_command: str, info: dict):
        """Initialize."""
        super().__init__(coordinator)
        self.api = api
        self.set_command = set_command
        
        self._attr_unique_id = f"{coordinator.data.get('model', 'heishamon')}_{set_command.lower()}"
        self._attr_name = f"SET-{set_command}"
        self._attr_device_name = device.name
        self._attr_device_info = {"identifiers": {(device.domain, device.id)} if device else None}
        self._attr_icon = info.get("icon")
        self._attr_options = info.get("options", [])

    @property
    def current_option(self) -> str:
        """Return current option."""
        return None

    async def async_select_option(self, option: str) -> None:
        """Select option."""
        value = self._attr_options.index(option)
        if await self.api.async_set_value(self.set_command, value):
            await self.coordinator.async_request_refresh()
