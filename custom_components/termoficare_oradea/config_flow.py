"""Config flow for Termoficare Oradea integration."""
import logging
import voluptuous as vol
import aiohttp
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import TermoficareApiClient
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
})

class TermoficareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Termoficare Oradea."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            # Test authentication
            cookie_jar = aiohttp.CookieJar(unsafe=True)
            session = async_create_clientsession(self.hass, verify_ssl=False, cookie_jar=cookie_jar)
            api = TermoficareApiClient(username, password, session)

            try:
                success = await api.authenticate()
                if success:
                    return self.async_create_entry(
                        title=f"Termoficare ({username})",
                        data=user_input,
                    )
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError):
                _LOGGER.exception("Nem sikerült kapcsolódni a Termoficare Oradea portálhoz")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Váratlan hiba a belépés során")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Handle re-authentication."""
        return await self.async_step_user()
