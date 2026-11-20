"""Constants for the Termoficare Oradea integration."""
import logging
from homeassistant.const import Platform

DOMAIN = "termoficare_oradea"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 240  # 4 hours in minutes

BASE_URL = "https://termoficare-oradea.ro"
LOGIN_URL = f"{BASE_URL}/index.php?action=login"
FACTURI_URL = f"{BASE_URL}/index.php?action=facturi"
FISA_URL = f"{BASE_URL}/index.php?action=fisa"
CITIRI_URL = f"{BASE_URL}/index.php?action=citiri"

ATTRIBUTION = "Adatok: Termoficare Oradea S.A."

_LOGGER = logging.getLogger(__package__)
