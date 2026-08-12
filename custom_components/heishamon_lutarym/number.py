"""Number platform for Heishamon - all number entities."""
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from .const import DOMAIN, HEISHAMON_TOPICS
from .api import HeishamonAPI

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up number entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    device = hass.data[DOMAIN][entry.entry_id]["device"]
    listening_only = hass.data[DOMAIN][entry.entry_id]["listening_only"]
    
    numbers = []
    for topic_id, topic_info in HEISHAMON_TOPICS.items():
        if topic_info["type"] == "number":
            numbers.append(HeishamonNumber(coordinator, api, device, topic_id, topic_info, listening_only))
    
    async_add_entities(numbers)

class HeishamonNumber(CoordinatorEntity, NumberEntity):
    """Heishamon number entity."""
    
    def __init__(self, coordinator: DataUpdateCoordinator, api: HeishamonAPI, device, topic_id: str, topic_info: dict, listening_only: bool):
        """Initialize."""
        super().__init__(coordinator)
        self.api = api
        self.topic_id = topic_id
        self.topic_info = topic_info
        self.listening_only = listening_only
        
        self._attr_unique_id = f"{coordinator.data.get('model', 'heishamon')}_{topic_id.lower()}_set"
        self._attr_name = f"{topic_id}-{topic_info['name']}"
        self._attr_device_name = device.name
        self._attr_device_info = {"identifiers": {(device.domain, device.id)} if device else None}
        
        if topic_info["unit"]:
            self._attr_native_unit_of_measurement = topic_info["unit"]
        self._attr_icon = topic_info.get("icon")
        
        self._attr_native_min_value = topic_info.get("min", -999)
        self._attr_native_max_value = topic_info.get("max", 999)

    @property
    def native_value(self):
        """Return value."""
        if self.coordinator.data:
            return self.coordinator.data.get(self.topic_id)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set value."""
        if self.listening_only:
            return
        set_cmd = self._get_set_command()
        if set_cmd and await self.api.async_set_value(set_cmd, int(value)):
            await self.coordinator.async_request_refresh()

    def _get_set_command(self) -> str:
        """Get SET command."""
        mapping = {
            "TOP9": "SetDHWTemp", "TOP25": "SetDHWHolidayShiftTemp",
            "TOP27": "SetZ1HeatRequestTemperature", "TOP28": "SetZ1CoolRequestTemperature",
            "TOP34": "SetZ2HeatRequestTemperature", "TOP35": "SetZ2CoolRequestTemperature",
            "TOP45": "SetRoomHolidayShiftTemp", "TOP77": "SetHeatingOffOutdoorTemp",
            "TOP78": "SetHeaterOnOutdoorTemp", "TOP79": "SetHeatToCoolTemp", "TOP80": "SetCoolToHeatTemp",
        }
        return mapping.get(self.topic_id)
