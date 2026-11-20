"""Sensor platform for Termoficare Oradea integration."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ATTRIBUTION, BASE_URL
from .coordinator import TermoficareDataUpdateCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up Termoficare Oradea sensors."""
    coordinator: TermoficareDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TermoficareBalanceSensor(coordinator, entry),
        TermoficareLastInvoiceSensor(coordinator, entry),
        TermoficareLastInvoiceNumberSensor(coordinator, entry),
        TermoficareLastInvoiceDateSensor(coordinator, entry),
    ]

    async_add_entities(entities)

class TermoficareBaseSensor(CoordinatorEntity[TermoficareDataUpdateCoordinator], SensorEntity):
    """Base sensor for Termoficare Oradea."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: TermoficareDataUpdateCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self.entry = entry
        username = entry.data.get("username", "")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Termoficare Oradea ({username})",
            manufacturer="Termoficare Oradea S.A.",
            model="Servicii Online Clienți",
            configuration_url=BASE_URL,
        )

class TermoficareBalanceSensor(TermoficareBaseSensor):
    """Sensor for current total balance / sold de plată."""

    _attr_name = "Sold total de plată"
    _attr_native_unit_of_measurement = "RON"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_total_balance"

    @property
    def native_value(self):
        """Return total balance."""
        return self.coordinator.data.get("total_balance", 0.0)

    @property
    def extra_state_attributes(self):
        """Return extra details."""
        data = self.coordinator.data
        return {
            "restant": data.get("restant", 0.0),
            "sold_initial": data.get("sold_initial", 0.0),
            "client_name": data.get("client_name"),
            "client_code": data.get("client_code"),
            "invoices": data.get("invoices", []),
        }

class TermoficareLastInvoiceSensor(TermoficareBaseSensor):
    """Sensor for latest invoice total."""

    _attr_name = "Ultima factură"
    _attr_native_unit_of_measurement = "RON"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_icon = "mdi:file-document-outline"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_latest_invoice"

    @property
    def native_value(self):
        """Return latest invoice total amount."""
        latest = self.coordinator.data.get("latest_invoice", {})
        return latest.get("total_factura", 0.0)

    @property
    def extra_state_attributes(self):
        """Return invoice metadata."""
        latest = self.coordinator.data.get("latest_invoice", {})
        return {
            "nr_factura": latest.get("nr_factura"),
            "data_factura": latest.get("data_factura"),
            "valoare_fara_tva": latest.get("valoare_fara_tva", 0.0),
            "total_tva": latest.get("total_tva", 0.0),
            "gestiune": latest.get("gestiune"),
            "pdf_url": latest.get("pdf_url"),
        }

class TermoficareLastInvoiceNumberSensor(TermoficareBaseSensor):
    """Sensor for latest invoice number."""

    _attr_name = "Număr factură"
    _attr_icon = "mdi:numeric"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_latest_invoice_number"

    @property
    def native_value(self):
        """Return latest invoice number."""
        latest = self.coordinator.data.get("latest_invoice", {})
        return latest.get("nr_factura") or "-"

class TermoficareLastInvoiceDateSensor(TermoficareBaseSensor):
    """Sensor for latest invoice date."""

    _attr_name = "Data facturii"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_latest_invoice_date"

    @property
    def native_value(self):
        """Return latest invoice date."""
        latest = self.coordinator.data.get("latest_invoice", {})
        return latest.get("data_factura") or "-"
