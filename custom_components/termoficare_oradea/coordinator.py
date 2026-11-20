"""DataUpdateCoordinator for Termoficare Oradea integration."""
from datetime import timedelta
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TermoficareApiClient
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

class TermoficareDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Termoficare Oradea data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: TermoficareApiClient):
        """Initialize the coordinator."""
        self.entry = entry
        self.api = api
        scan_interval = timedelta(minutes=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        super().__init__(
            hass,
            _LOGGER,
            name=f"Termoficare Oradea ({entry.title})",
            update_interval=scan_interval,
        )

    async def _async_update_data(self):
        """Fetch data from Termoficare Oradea portal."""
        try:
            return await self.api.get_data()
        except Exception as err:
            _LOGGER.error("Hiba a Termoficare adatok lekérésekor: %s", err)
            raise UpdateFailed(f"Lekérdezési hiba: {err}") from err
