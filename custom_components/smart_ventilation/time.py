"""Live-tunable time entities for quiet-hours start/end."""

from __future__ import annotations

from datetime import time as time_

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    DEFAULT_QUIET_HOURS_END,
    DEFAULT_QUIET_HOURS_START,
    DOMAIN,
)
from .coordinator import SmartVentilationCoordinator
from .entity_helpers import global_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the quiet-hours time entities."""
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        QuietHoursStartTime(coordinator, entry),
        QuietHoursEndTime(coordinator, entry),
    ])


def _parse(value: str | None, default: str) -> time_:
    parts = (value or default).split(":")
    if len(parts) == 2:
        parts.append("00")
    hour, minute, second = (int(p) for p in parts[:3])
    return time_(hour, minute, second)


class _SettingsTime(TimeEntity):
    """Base class: reflects one key of RuntimeStore.settings live."""

    _attr_has_entity_name = True
    _settings_key: str
    _default: str

    def __init__(self, coordinator: SmartVentilationCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_device_info = global_device_info(entry)
        self._attr_unique_id = f"{entry.entry_id}_{self._settings_key}"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> time_:
        return _parse(self.coordinator.runtime.settings.get(self._settings_key), self._default)

    async def async_set_value(self, value: time_) -> None:
        self.coordinator.runtime.save_settings({self._settings_key: value.isoformat()})
        self.async_write_ha_state()


class QuietHoursStartTime(_SettingsTime):
    """Quiet hours start — notifications are suppressed from here."""

    _attr_icon = "mdi:weather-night"
    _attr_translation_key = "quiet_hours_start"
    _settings_key = CONF_QUIET_HOURS_START
    _default = DEFAULT_QUIET_HOURS_START


class QuietHoursEndTime(_SettingsTime):
    """Quiet hours end — notifications resume from here."""

    _attr_icon = "mdi:weather-sunny"
    _attr_translation_key = "quiet_hours_end"
    _settings_key = CONF_QUIET_HOURS_END
    _default = DEFAULT_QUIET_HOURS_END
