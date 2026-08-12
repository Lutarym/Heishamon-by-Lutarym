"""Climate platform for Heishamon by Lutarym."""

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
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
    """Set up climate entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    listening_only = entry.data.get("listening_only", True)
    
    climates = [
        HeishamonClimate(coordinator, api, "Z1", listening_only),
        HeishamonClimate(coordinator, api, "Z2", listening_only),
    ]
    async_add_entities(climates)


class HeishamonClimate(ClimateEntity):
    """Heishamon climate entity."""

    def __init__(self, coordinator: DataUpdateCoordinator, api: HeishamonAPI, zone: str, listening_only: bool):
        """Initialize climate."""
        self.coordinator = coordinator
        self.api = api
        self.zone = zone
        self.listening_only = listening_only
        self._attr_unique_id = f"heishamon_climate_{zone.lower()}"
        self._attr_name = f"Heishamon {zone}"
        self._attr_temperature_unit = "°C"
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        if not listening_only:
            self._attr_supported_features |= ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF

    @property
    def available(self) -> bool:
        """Return availability."""
        return self.coordinator.last_update_success

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        topic = f"TOP{56 if self.zone == 'Z1' else 57}"
        if self.coordinator.data:
            return self.coordinator.data.get(topic, {}).get("value")
        return None

    @property
    def target_temperature(self) -> float:
        """Return target temperature."""
        topic = f"TOP{27 if self.zone == 'Z1' else 34}"
        if self.coordinator.data:
            return self.coordinator.data.get(topic, {}).get("value")
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HVAC mode."""
        if self.coordinator.data:
            value = self.coordinator.data.get("TOP4", {}).get("value")
            if value == 0:
                return HVACMode.HEAT
            elif value == 1:
                return HVACMode.COOL
            elif value in [2, 6, 7, 8]:
                return HVACMode.AUTO
        return HVACMode.AUTO

    async def async_set_temperature(self, **kwargs) -> None:
        """Set temperature."""
        temperature = kwargs.get("temperature")
        if temperature is not None and not self.listening_only:
            set_cmd = f"SetZ{self.zone[-1]}HeatRequestTemperature" if self.hvac_mode == HVACMode.HEAT else f"SetZ{self.zone[-1]}CoolRequestTemperature"
            success = await self.api.async_set_value(set_cmd, int(temperature))
            if success:
                await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if not self.listening_only:
            mode_map = {
                HVACMode.HEAT: 0,
                HVACMode.COOL: 1,
                HVACMode.AUTO: 2,
            }
            success = await self.api.async_set_value("SetOperationMode", mode_map.get(hvac_mode, 2))
            if success:
                await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
