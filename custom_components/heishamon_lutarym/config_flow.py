"""Einrichtungsdialog."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import HeishamonAPI
from .const import (
    CONF_HOST,
    CONF_LISTENING_ONLY,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_LISTENING_ONLY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)


class HeishamonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Fragt Host und Optionen ab und prueft die Verbindung."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Erster und einziger Schritt."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = HeishamonAPI(
                self.hass,
                host=user_input[CONF_HOST],
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
            )
            if await api.test_connection():
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Heishamon {user_input[CONF_HOST]}", data=user_input
                )
            errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
                vol.Optional(CONF_LISTENING_ONLY, default=DEFAULT_LISTENING_ONLY): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
