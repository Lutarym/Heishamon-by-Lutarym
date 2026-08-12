"""Number platform for Heishamon by Lutarym."""

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, HEISHAMON_TOPICS
from .api import HeishamonAPI

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    
    numbers = []
    for topic_id, topic_info in HEISHAMON_TOPICS.items():
        if topic_info["type"] == "number":
            numbers.append(HeishamonNumber(coordinator, api, topic_id, topic_info))
    
    async_add_entities(numbers)


class HeishamonNumber(NumberEntity):
    """Heishamon number entity."""

    def __init__(self, coordinator: DataUpdateCoordinator, api: HeishamonAPI, topic_id: str, topic_info: dict):
        """Initialize number."""
        self.coordinator = coordinator
        self.api = api
        self.topic_id = topic_id
        self.topic_info = topic_info
        self._attr_unique_id = f"heishamon_{topic_id.lower()}_set"
        self._attr_name = f"Set {topic_info['name']}"
        self._attr_icon = topic_info.get("icon", "mdi:numeric")
        
        if topic_info["unit"]:
            self._attr_native_unit_of_measurement = topic_info["unit"]
        
        self._attr_native_min_value = -999
        self._attr_native_max_value = 999

    @property
    def available(self) -> bool:
        """Return availability."""
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        """Return number value."""
        if self.coordinator.data:
            return self.coordinator.data.get(self.topic_id, {}).get("value")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set value via API."""
        set_key = self._get_set_command()
        if set_key:
            success = await self.api.async_set_value(set_key, int(value))
            if success:
                await self.coordinator.async_request_refresh()

    def _get_set_command(self) -> str:
        """Get SET command for this topic."""
        topic_to_set = {
            "TOP9": "SetDHWTemp",
            "TOP25": "SetDHWHolidayShiftTemp",
            "TOP27": "SetZ1HeatRequestTemperature",
            "TOP28": "SetZ1CoolRequestTemperature",
            "TOP34": "SetZ2HeatRequestTemperature",
            "TOP35": "SetZ2CoolRequestTemperature",
            "TOP45": "SetRoomHolidayShiftTemp",
            "TOP77": "SetHeatingOffOutdoorTemp",
            "TOP78": "SetHeaterOnOutdoorTemp",
            "TOP79": "SetHeatToCoolTemp",
            "TOP80": "SetCoolToHeatTemp",
        }
        return topic_to_set.get(self.topic_id)

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
