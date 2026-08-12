"""Sensor platform for Heishamon - all 143 topics."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, HEISHAMON_TOPICS

# Deutsche Übersetzungen
TOPIC_NAMES_DE = {
    "TOP0": "Wärmepumpe Status",
    "TOP1": "Pumpen Durchfluss",
    "TOP2": "Warmwasser erzwingen Status",
    "TOP3": "Ruhe Modus Plan",
    "TOP4": "Betriebsmodus Status",
    "TOP5": "Rücklauftemperatur Wärmeerzeuger",
    "TOP6": "Vorlauftemperatur Wärmeerzeuger",
    "TOP7": "Soll Temperatur Wärmeerzeuger",
    "TOP8": "Verdichter Frequenz",
    "TOP9": "Warmwasser Solltemperatur",
    "TOP10": "Warmwasser Ist Temperatur",
    "TOP14": "Außentemperatur",
    "TOP15": "Heiz Leistung Wärmeerzeuger",
    "TOP16": "Heiz Stromverbrauch",
    "TOP27": "Zone 1 Heiz Solltemperatur",
    "TOP28": "Zone 1 Kühl Solltemperatur",
    "TOP34": "Zone 2 Heiz Solltemperatur",
    "TOP35": "Zone 2 Kühl Solltemperatur",
    "TOP36": "Zone 1 Wasser Temperatur",
    "TOP37": "Zone 2 Wasser Temperatur",
    "TOP40": "Warmwasser Leistung Wärmeerzeuger",
    "TOP41": "Warmwasser Stromverbrauch",
    "TOP42": "Zone 1 Wasser Solltemperatur",
    "TOP43": "Zone 2 Wasser Solltemperatur",
    "TOP46": "Pufferspeicher Temperatur",
    "TOP47": "Solarkollektor Temperatur",
    "TOP48": "Pool Temperatur",
    "TOP50": "Verdichter Ausgangstemperatur",
    "TOP56": "Zone 1 Temperatur",
    "TOP57": "Zone 2 Temperatur",
    "TOP58": "Warmwasser Heizer Status",
    "TOP77": "Heizung Aus Außentemp",
    "TOP78": "Heizer Ein Außentemp",
}


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
        
        # Nutze deutsche Namen wenn verfügbar
        name_de = TOPIC_NAMES_DE.get(topic_id, topic_info['name'])
        self._attr_name = f"{topic_id} {name_de}"
        
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
