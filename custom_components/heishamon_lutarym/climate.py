"""Climate platform for Heishamon."""
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from .const import DOMAIN
from .api import HeishamonAPI

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up climate."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    device = hass.data[DOMAIN][entry.entry_id]["device"]
    listening_only = hass.data[DOMAIN][entry.entry_id]["listening_only"]
    
    climates = [
        HeishamonClimate(coordinator, api, device, "Z1", listening_only),
        HeishamonClimate(coordinator, api, device, "Z2", listening_only),
    ]
    async_add_entities(climates)

class HeishamonClimate(CoordinatorEntity, ClimateEntity):
    """Heishamon climate entity."""
    
    def __init__(self, coordinator: DataUpdateCoordinator, api: HeishamonAPI, device, zone: str, listening_only: bool):
        """Initialize."""
        super().__init__(coordinator)
        self.api = api
        self.zone = zone
        self.listening_only = listening_only
        
        self._attr_unique_id = f"{coordinator.data.get('model', 'heishamon')}_climate_{zone.lower()}"
        self._attr_name = f"{zone}-Climate"
        self._attr_device_name = device.name
        self._attr_device_info = {"identifiers": {(device.domain, device.id)} if device else None}
        self._attr_temperature_unit = "°C"
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        if not listening_only:
            self._attr_supported_features |= ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        topic = f"TOP{56 if self.zone == 'Z1' else 57}"
        if self.coordinator.data:
            return self.coordinator.data.get(topic)
        return None

    @property
    def target_temperature(self) -> float:
        """Return target temperature."""
        topic = f"TOP{27 if self.zone == 'Z1' else 34}"
        if self.coordinator.data:
            return self.coordinator.data.get(topic)
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HVAC mode."""
        return HVACMode.HEAT

    async def async_set_temperature(self, **kwargs) -> None:
        """Set temperature."""
        temperature = kwargs.get("temperature")
        if temperature and not self.listening_only:
            await self.api.async_set_value(f"SetZ{self.zone[-1]}HeatRequestTemperature", int(temperature))
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if not self.listening_only:
            await self.api.async_set_value("SetOperationMode", 0)
            await self.coordinator.async_request_refresh()
