"""Runtime state store for Smart Ventilation.

Owns two things persisted in entry.options so they survive restarts:
- "settings": global, user-tunable settings (quiet hours, cooldowns, ...).
- "_runtime": private per-area state (action guard, notification dedup,
  pending confirmation, diagnostics) — never shown in any form.

Reads always deep-merge onto defaults so existing installs with neither key
yet degrade to defaults instead of raising — that merge *is* the migration
path, there's no separate schema-version upgrade step needed for v1.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DEFAULT_SETTINGS

SETTINGS_KEY = "settings"
RUNTIME_KEY = "_runtime"
RUNTIME_VERSION = 1

DEFAULT_AREA_RUNTIME: dict[str, Any] = {
    "guard": {
        "accepted_action": "NONE",
        "pending_action": None,
        "pending_since": None,
        "lockout_until": None,
    },
    "notify": {
        # SignalDebouncer state for the notification stability window —
        # distinct from the marker below, which tracks what was last
        # actually SENT (updated only on a successful send, gated further
        # by cooldown/severity), not what the debouncer has settled on.
        "pending_signature": None,
        "pending_since": None,
        "stable_signature": None,
        # Marker: the last notification actually sent for this area.
        "last_signature": None,
        "last_reason": None,
        "last_severity": None,
        "last_notified_at": None,
    },
    "confirmation": {
        "token": None,
        "action": None,
        "expires_at": None,
    },
    "diagnostics": {
        "misconfigured": False,
        "last_data_ok": None,
    },
}


def merge_defaults(value: dict[str, Any] | None, defaults: dict[str, Any]) -> dict[str, Any]:
    """Return `value` deep-merged onto `defaults`; never raises on missing keys."""
    merged = dict(defaults)
    if not value:
        return merged
    for key, default in defaults.items():
        if key not in value:
            continue
        if isinstance(default, dict) and isinstance(value[key], dict):
            merged[key] = merge_defaults(value[key], default)
        else:
            merged[key] = value[key]
    return merged


class RuntimeStore:
    """Owns global settings + per-area runtime markers backed by entry.options."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._suppress_next_reload = False

    @property
    def settings(self) -> dict[str, Any]:
        """Return global settings, merged onto defaults."""
        return merge_defaults(self.entry.options.get(SETTINGS_KEY), DEFAULT_SETTINGS)

    def area_state(self, area_name: str) -> dict[str, Any]:
        """Return one area's runtime state, merged onto defaults."""
        areas = self.entry.options.get(RUNTIME_KEY, {}).get("areas", {})
        return merge_defaults(areas.get(area_name), DEFAULT_AREA_RUNTIME)

    def suppress_next_reload(self) -> bool:
        """Consume-once flag: True if the caller should skip a full reload.

        Set by save_settings/save_area_state so a live number/switch/time
        entity write only triggers a coordinator refresh, not a full
        integration teardown/recreate.
        """
        value = self._suppress_next_reload
        self._suppress_next_reload = False
        return value

    def ensure_defaults(self) -> None:
        """One-time migration: persist merged defaults if either key is missing.

        Despite the rest of this class using the HA "async_" naming
        convention for anything that writes to entry.options, none of these
        methods actually await anything — hass.config_entries.async_update_entry
        is itself a plain synchronous call — so they are deliberately plain
        `def`s and must be called without `await`.
        """
        options = self.entry.options
        if SETTINGS_KEY in options and RUNTIME_KEY in options:
            return
        runtime = dict(options.get(RUNTIME_KEY, {}))
        runtime.setdefault("version", RUNTIME_VERSION)
        runtime.setdefault("areas", {})
        self._async_update_options({SETTINGS_KEY: self.settings, RUNTIME_KEY: runtime})

    def save_settings(self, patch: dict[str, Any]) -> None:
        """Persist a partial update to global settings without a full reload."""
        self._suppress_next_reload = True
        self._async_update_options({SETTINGS_KEY: {**self.settings, **patch}})

    def save_area_state(self, area_name: str, patch: dict[str, Any]) -> None:
        """Persist a partial update to one area's runtime state.

        `patch` keys are whole sub-groups ("guard"/"notify"/"confirmation"/
        "diagnostics") and replace that sub-group entirely — callers always
        build the full sub-group dict before saving, never a deep-partial one.
        """
        self._suppress_next_reload = True
        runtime = dict(self.entry.options.get(RUNTIME_KEY, {"version": RUNTIME_VERSION, "areas": {}}))
        areas = dict(runtime.get("areas", {}))
        areas[area_name] = {**self.area_state(area_name), **patch}
        runtime["areas"] = areas
        self._async_update_options({RUNTIME_KEY: runtime})

    def _async_update_options(self, patch: dict[str, Any]) -> None:
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, **patch}
        )
