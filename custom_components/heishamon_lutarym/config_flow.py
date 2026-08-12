"""Config flow for Heishamon by Lutarym."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from .api import HeishamonAPI
from .const import DOMAIN, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_UPDATE_INTERVAL, CONF_LISTENING_ONLY, DEFAULT_UPDATE_INTERVAL, DEFAULT_LISTENING_ONLY

class HeishamonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Heishamon."""
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle user step."""
        errors = {}
        if user_input is not None:
            try:
                api = HeishamonAPI(user_input[CONF_HOST], user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD))
                if not await api.test_connection():
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(user_input[CONF_HOST])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)
            except Exception:
                errors["base"] = "cannot_connect"

        schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_USERNAME): str,
            vol.Optional(CONF_PASSWORD): str,
            vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
            vol.Optional(CONF_LISTENING_ONLY, default=DEFAULT_LISTENING_ONLY): bool,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
