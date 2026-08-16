"""Einrichtung und spaetere Aenderung.

Fassung 0.4.1
Die Neukonfiguration fragt fuenf Angaben ab:
Adresse, Benutzer, Passwort, Aktualisierungstakt und Nur-Lesen.
In 0.4.0 waren es nur die ersten drei.
"""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
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
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)

INTERVAL = vol.All(
    vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)
)


def einstellung(entry: config_entries.ConfigEntry, schluessel: str, standard):
    """Liefert die gueltige Einstellung, Optionen haben Vorrang."""
    return entry.options.get(schluessel, entry.data.get(schluessel, standard))


class HeishamonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Fragt Host und Optionen ab und prueft die Verbindung."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry):
        """Erlaubt spaeteres Aendern ueber Konfigurieren."""
        return HeishamonOptionsFlow()

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Erstmalige Einrichtung."""
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
                vol.Optional(
                    CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): INTERVAL,
                vol.Optional(CONF_LISTENING_ONLY, default=DEFAULT_LISTENING_ONLY): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Aendert die Adresse eines bestehenden Eintrags."""
        entry = self._get_reconfigure_entry()
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
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                # Verbindungsdaten gehoeren zum Eintrag, Takt und
                # Steuerbarkeit zu den Optionen. Beides wird hier
                # gemeinsam gespeichert und der Eintrag neu geladen.
                daten = {
                    **entry.data,
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input.get(CONF_USERNAME, ""),
                    CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                }
                optionen = {
                    **entry.options,
                    CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                    CONF_LISTENING_ONLY: user_input[CONF_LISTENING_ONLY],
                }
                self.hass.config_entries.async_update_entry(
                    entry, data=daten, options=optionen
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
                vol.Optional(
                    CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")
                ): str,
                vol.Optional(
                    CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD, "")
                ): str,
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=einstellung(
                        entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                ): INTERVAL,
                vol.Optional(
                    CONF_LISTENING_ONLY,
                    default=einstellung(
                        entry, CONF_LISTENING_ONLY, DEFAULT_LISTENING_ONLY
                    ),
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )


class HeishamonOptionsFlow(config_entries.OptionsFlow):
    """Takt und Steuerbarkeit nachtraeglich aendern."""

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Einziger Schritt."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entry = self.config_entry
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=einstellung(
                        entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                ): INTERVAL,
                vol.Optional(
                    CONF_LISTENING_ONLY,
                    default=einstellung(
                        entry, CONF_LISTENING_ONLY, DEFAULT_LISTENING_ONLY
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
