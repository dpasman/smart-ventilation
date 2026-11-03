"""Live-tunable switch entities: global toggles + per-area confirmation gate."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_AREA_NAME,
    CONF_CONFIRMATION_REQUIRED,
    CONF_DEBUG_MODE,
    CONF_NOTIFICATIONS_ENABLED,
    CONF_QUIET_HOURS_ENABLED,
    DEFAULT_CONFIRMATION_REQUIRED,
    DEFAULT_DEBUG_MODE,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_QUIET_HOURS_ENABLED,
    DOMAIN,
)
from .coordinator import SmartVentilationCoordinator
from .entity_helpers import device_info, global_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the global and per-area switch entities."""
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [
        NotificationsEnabledSwitch(coordinator, entry),
        QuietHoursEnabledSwitch(coordinator, entry),
        DebugModeSwitch(coordinator, entry),
    ]
    for area in (entry.options.get("areas") or entry.data.get("areas", [])):
        entities.append(
            ActionConfirmationRequiredSwitch(coordinator, entry, area[CONF_AREA_NAME], area.get("area_id"))
        )
    async_add_entities(entities)


class _SettingsSwitch(SwitchEntity):
    """Base class: reflects one global key of RuntimeStore.settings live."""

    _attr_has_entity_name = True
    _settings_key: str
    _default: bool

    def __init__(self, coordinator: SmartVentilationCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_device_info = global_device_info(entry)
        self._attr_unique_id = f"{entry.entry_id}_{self._settings_key}"

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.runtime.settings.get(self._settings_key, self._default)

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.runtime.save_settings({self._settings_key: True})
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.runtime.save_settings({self._settings_key: False})
        self.async_write_ha_state()


class NotificationsEnabledSwitch(_SettingsSwitch):
    """Master on/off for Smart Ventilation notifications."""

    _attr_icon = "mdi:bell"
    _attr_translation_key = "notifications_enabled"
    _settings_key = CONF_NOTIFICATIONS_ENABLED
    _default = DEFAULT_NOTIFICATIONS_ENABLED


class QuietHoursEnabledSwitch(_SettingsSwitch):
    """Whether the configured quiet-hours window is honored."""

    _attr_icon = "mdi:weather-night"
    _attr_translation_key = "quiet_hours_enabled"
    _settings_key = CONF_QUIET_HOURS_ENABLED
    _default = DEFAULT_QUIET_HOURS_ENABLED


class DebugModeSwitch(_SettingsSwitch):
    """Verbose logging / forced debug notifications."""

    _attr_icon = "mdi:bug"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "debug_mode"
    _settings_key = CONF_DEBUG_MODE
    _default = DEFAULT_DEBUG_MODE


class ActionConfirmationRequiredSwitch(SwitchEntity):
    """Per-area: require a Companion App tap before actuating OPEN/CLOSE.

    Defaults to True (safety-first). The options-flow area schema sets the
    initial value; this switch lets it be toggled live from a dashboard —
    e.g. "temporarily trust this area's automation" — without reopening
    the options flow.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:cellphone-check"
    _attr_translation_key = "confirmation_required"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
        area_id: str | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.entry = entry
        self.area_name = area_name
        self._attr_device_info = device_info(entry, area_name, area_id)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_confirmation_required"

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        area = self._find_area()
        return bool(area.get(CONF_CONFIRMATION_REQUIRED, DEFAULT_CONFIRMATION_REQUIRED)) if area else DEFAULT_CONFIRMATION_REQUIRED

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set(False)

    def _find_area(self) -> dict | None:
        areas = self.entry.options.get("areas") or self.entry.data.get("areas", [])
        return next((a for a in areas if a[CONF_AREA_NAME] == self.area_name), None)

    async def _async_set(self, value: bool) -> None:
        areas = list(self.entry.options.get("areas") or self.entry.data.get("areas", []))
        new_areas = [
            {**a, CONF_CONFIRMATION_REQUIRED: value} if a[CONF_AREA_NAME] == self.area_name else a
            for a in areas
        ]
        self.coordinator.runtime.save_areas(new_areas)
        self.async_write_ha_state()
