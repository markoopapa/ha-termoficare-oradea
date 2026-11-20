"""Termoficare Oradea Home Assistant Integration."""
import logging
import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import TermoficareApiClient
from .coordinator import TermoficareDataUpdateCoordinator
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, PLATFORMS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Termoficare Oradea from a config entry."""
    # Use dedicated session with cookie jar so GDPR=1 and PHPSESSID persist
    cookie_jar = aiohttp.CookieJar(unsafe=True)
    session = async_create_clientsession(hass, verify_ssl=False, cookie_jar=cookie_jar)

    api = TermoficareApiClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    coordinator = TermoficareDataUpdateCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
