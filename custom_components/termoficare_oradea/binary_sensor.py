"""Binary sensor platform for Termoficare Oradea integration."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ATTRIBUTION, BASE_URL
from .coordinator import TermoficareDataUpdateCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up Termoficare Oradea binary sensors."""
    coordinator: TermoficareDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        TermoficareOverdueBinarySensor(coordinator, entry),
    ])

class TermoficareOverdueBinarySensor(CoordinatorEntity[TermoficareDataUpdateCoordinator], BinarySensorEntity):
    """Binary sensor for overdue / unpaid balance."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = "Factură restantă"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: TermoficareDataUpdateCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self.entry = entry
        username = entry.data.get("username", "")
        self._attr_unique_id = f"{entry.entry_id}_overdue"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Termoficare Oradea ({username})",
            manufacturer="Termoficare Oradea S.A.",
            model="Servicii Online Clienți",
            configuration_url=BASE_URL,
        )

    @property
    def is_on(self) -> bool:
        """Return true if there is an overdue or unpaid balance."""
        return bool(self.coordinator.data.get("is_overdue", False))

    @property
    def extra_state_attributes(self):
        """Return details."""
        return {
            "restant": self.coordinator.data.get("restant", 0.0),
            "total_balance": self.coordinator.data.get("total_balance", 0.0),
        }
