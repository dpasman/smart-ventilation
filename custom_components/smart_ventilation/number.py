"""Live-tunable number entities for global settings.

These mirror two fields of the options-flow "Global Settings" step as
dashboard-editable entities — writes go straight to RuntimeStore, which
flags the config-entry-update listener to refresh the coordinator instead
of a full platform reload (see runtime.py/__init__.py).
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_NOTIFICATION_COOLDOWN_MINUTES,
    CONF_STABILITY_WINDOW_MINUTES,
    DEFAULT_NOTIFICATION_COOLDOWN_MINUTES,
    DEFAULT_STABILITY_WINDOW_MINUTES,
    DOMAIN,
)
from .coordinator import SmartVentilationCoordinator
from .entity_helpers import global_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the global-settings number entities."""
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        NotificationCooldownNumber(coordinator, entry),
        StabilityWindowNumber(coordinator, entry),
    ])


class _SettingsNumber(NumberEntity):
    """Base class: reflects one key of RuntimeStore.settings live."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_max_value = 360
    _attr_native_step = 1

    _settings_key: str
    _default: float

    def __init__(self, coordinator: SmartVentilationCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_device_info = global_device_info(entry)
        self._attr_unique_id = f"{entry.entry_id}_{self._settings_key}"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.runtime.settings.get(self._settings_key, self._default)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.runtime.save_settings({self._settings_key: value})
        self.async_write_ha_state()


class NotificationCooldownNumber(_SettingsNumber):
    """Minutes to wait before re-notifying the same area for the same reason."""

    _attr_icon = "mdi:timer-sand"
    _attr_translation_key = "notification_cooldown_minutes"
    _settings_key = CONF_NOTIFICATION_COOLDOWN_MINUTES
    _default = DEFAULT_NOTIFICATION_COOLDOWN_MINUTES


class StabilityWindowNumber(_SettingsNumber):
    """Minutes a recommendation must hold stable before it's acted on."""

    _attr_icon = "mdi:timer-outline"
    _attr_translation_key = "stability_window_minutes"
    _settings_key = CONF_STABILITY_WINDOW_MINUTES
    _default = DEFAULT_STABILITY_WINDOW_MINUTES
    _attr_native_max_value = 120
