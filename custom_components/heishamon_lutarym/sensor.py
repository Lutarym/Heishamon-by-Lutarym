"""Sensor platform for Heishamon - all 143 topics."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.helpers.device_registry import async_get as dr_async_get
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, HEISHAMON_TOPICS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensor entities for all 143 topics."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    
    sensors = []
    for topic_id, topic_info in HEISHAMON_TOPICS.items():
        if topic_info["type"] == "sensor":
            sensors.append(HeishamonSensor(coordinator, host, topic_id, topic_info))
    
    async_add_entities(sensors)


class HeishamonSensor(CoordinatorEntity, SensorEntity):
    """Heishamon sensor entity."""
    
    def __init__(self, coordinator: DataUpdateCoordinator, host: str, topic_id: str, topic_info: dict):
        """Initialize."""
        super().__init__(coordinator)
        self.topic_id = topic_id
        self.topic_info = topic_info
        self._host = host
        
        self._attr_unique_id = f"heishamon_{host}_{topic_id.lower()}"
        self._attr_name = f"{topic_id}-{topic_info['name']}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=f"Heishamon {host}",
            manufacturer="Panasonic",
            model="Aquarea Heat Pump",
        )
        
        if topic_info["unit"]:
            self._attr_native_unit_of_measurement = topic_info["unit"]
        if topic_info.get("device_class"):
            self._attr_device_class = topic_info["device_class"]
        self._attr_icon = topic_info.get("icon")
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return sensor value."""
        if self.coordinator.data:
            return self.coordinator.data.get(self.topic_id)
        return None
