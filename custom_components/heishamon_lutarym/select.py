"""Select platform for Heishamon by Lutarym."""

from homeassistant.components.select import SelectEntity
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
    """Set up select entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    listening_only = entry.data.get("listening_only", True)
    
    if not listening_only:
        selects = [
            HeishamonSelect(
                coordinator, api, "SetOperationMode", "Operating Mode", "TOP4",
                ["Heat only", "Cool only", "Auto", "DHW only", "Heat+DHW", "Cool+DHW", "Auto+DHW", "Auto(Cool)", "Auto(Cool)+DHW"]
            ),
            HeishamonSelect(
                coordinator, api, "SetQuietMode", "Quiet Mode", "TOP18",
                ["Off", "Less Power", "Even Less Power", "Least Power"]
            ),
            HeishamonSelect(
                coordinator, api, "SetPowerfulMode", "Powerful Mode", "TOP17",
                ["Off", "30 min", "60 min", "90 min"]
            ),
        ]
        async_add_entities(selects)


class HeishamonSelect(SelectEntity):
    """Heishamon select entity."""

    def __init__(self, coordinator: DataUpdateCoordinator, api: HeishamonAPI, set_command: str, name: str, topic_id: str, options: list):
        """Initialize select."""
        self.coordinator = coordinator
        self.api = api
        self.set_command = set_command
        self.topic_id = topic_id
        self._attr_unique_id = f"heishamon_{set_command.lower()}"
        self._attr_name = name
        self._attr_options = options
        self._attr_icon = "mdi:cog"

    @property
    def available(self) -> bool:
        """Return availability."""
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str:
        """Return current option."""
        if self.coordinator.data:
            value = self.coordinator.data.get(self.topic_id, {}).get("value")
            if value is not None and value < len(self._attr_options):
                return self._attr_options[int(value)]
        return None

    async def async_select_option(self, option: str) -> None:
        """Select option."""
        value = self._attr_options.index(option)
        success = await self.api.async_set_value(self.set_command, value)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
