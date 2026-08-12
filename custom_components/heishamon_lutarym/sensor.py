"""Sensor platform for Heishamon by Lutarym."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, HEISHAMON_TOPICS

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    sensors = []
    for topic_id, topic_info in HEISHAMON_TOPICS.items():
        if topic_info["type"] == "sensor":
            sensors.append(HeishamonSensor(coordinator, topic_id, topic_info))
    
    async_add_entities(sensors)


class HeishamonSensor(SensorEntity):
    """Heishamon sensor entity."""

    def __init__(self, coordinator: DataUpdateCoordinator, topic_id: str, topic_info: dict):
        """Initialize sensor."""
        self.coordinator = coordinator
        self.topic_id = topic_id
        self.topic_info = topic_info
        self._attr_unique_id = f"heishamon_{topic_id.lower()}"
        self._attr_name = topic_info["name"]
        if topic_info["unit"]:
            self._attr_native_unit_of_measurement = topic_info["unit"]
        if "device_class" in topic_info:
            self._attr_device_class = topic_info["device_class"]
        self._attr_icon = topic_info.get("icon", "mdi:gauge")
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self) -> bool:
        """Return availability."""
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        """Return sensor value."""
        if self.coordinator.data:
            return self.coordinator.data.get(self.topic_id, {}).get("value")
        return None

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
