"""Binary sensor for Smart Ventilation."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SmartVentilationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    areas = entry.data.get("areas", [])

    entities = []
    for area in areas:
        area_name = area["name"]
        entities.append(
            CoolingRecommendedBinarySensor(coordinator, entry, area_name),
        )

    async_add_entities(entities)


class CoolingRecommendedBinarySensor(BinarySensorEntity):
    """Binary sensor for cooling recommendation."""

    _attr_icon = "mdi:fan"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entry = entry
        self.area_name = area_name
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_cooling_recommended"
        self._attr_name = f"Cooling by Ventilation Recommended {area_name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{area_name}")},
            "name": area_name,
            "manufacturer": "Smart Ventilation",
            "model": "Cooling Recommendation",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.area_name, {})
        self._attr_is_on = data.get("cooling_recommended", False)

        reasons = []
        indoor_temp = data.get("indoor_temperature")
        outdoor_temp = data.get("outdoor_temperature")
        efficiency = data.get("efficiency", 0)

        if indoor_temp and indoor_temp <= 23:
            reasons.append("Inside not warm enough")
        if outdoor_temp and indoor_temp and outdoor_temp >= indoor_temp:
            reasons.append("Outside not cooler than inside")
        if efficiency < 30:
            reasons.append("Ventilation not recommended")

        if self._attr_is_on:
            reasons.append("Favorable conditions for summer ventilation")

        self._attr_extra_state_attributes = {"reasons": reasons}
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()
