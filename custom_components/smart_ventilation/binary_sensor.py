"""Binary sensor platform for Smart Ventilation."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartVentilationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities for each configured area."""
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CoolingRecommendedBinarySensor(coordinator, entry, area["name"], area.get("area_id"))
        for area in entry.data.get("areas", [])
    )


class CoolingRecommendedBinarySensor(
    CoordinatorEntity[SmartVentilationCoordinator], BinarySensorEntity
):
    """Binary sensor: is cooling via ventilation recommended?"""

    _attr_has_entity_name = True
    _attr_icon = "mdi:fan"
    _attr_translation_key = "cooling_recommended"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
        area_id: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self.area_name = area_name
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_cooling_recommended"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{area_name}")},
            "name": area_name,
            "manufacturer": "Smart Ventilation",
            "suggested_area": area_name,
        }

    @property
    def available(self) -> bool:
        return super().available and self.area_name in (self.coordinator.data or {})

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data.get(self.area_name, {})
        self._attr_is_on = data.get("cooling_recommended", False)

        reasons: list[str] = []
        in_temp = data.get("indoor_temperature")
        out_temp = data.get("outdoor_temperature")
        efficiency = data.get("efficiency", 0)

        if in_temp is not None and in_temp <= 23:
            reasons.append("Inside not warm enough (≤23°C)")
        if in_temp is not None and out_temp is not None and out_temp >= in_temp:
            reasons.append("Outside not cooler than inside")
        if efficiency <= 30:
            reasons.append("Ventilation efficiency too low (≤30%)")
        if self._attr_is_on:
            reasons.append("Favorable conditions for summer ventilation")

        self._attr_extra_state_attributes = {"reasons": reasons}
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()
