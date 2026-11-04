"""Per-area "send recommendation now" button."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_AREA_NAME, DOMAIN
from .coordinator import SmartVentilationCoordinator
from .entity_helpers import device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the per-area recommendation-now buttons."""
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SendRecommendationNowButton(coordinator, entry, area[CONF_AREA_NAME], area.get("area_id"))
        for area in (entry.options.get("areas") or entry.data.get("areas", []))
    )


class SendRecommendationNowButton(ButtonEntity):
    """Send this area's current recommendation immediately.

    Bypasses the notification stability window, cooldown, and quiet hours
    (an explicit user action) but any resulting actuation still goes
    through the normal hold/lockout + confirmation-required gate — this
    button cuts notification noise, not safety checks.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:bell-ring-outline"
    _attr_translation_key = "send_recommendation_now"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
        area_id: str | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.area_name = area_name
        self._attr_device_info = device_info(entry, area_name, area_id)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_send_recommendation_now"

    async def async_press(self) -> None:
        await self.coordinator.async_send_recommendation_now(self.area_name)
