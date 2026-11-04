"""Shared entity helpers used across all Smart Ventilation platforms."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN


def device_info(entry: ConfigEntry, area_name: str, area_id: str | None = None) -> dict:
    """Return the HA device-registry info dict for one area's device."""
    return {
        "identifiers": {(DOMAIN, f"{entry.entry_id}_{area_name}")},
        "name": area_name,
        "manufacturer": "Smart Ventilation",
        "suggested_area": area_name,
    }


def global_device_info(entry: ConfigEntry) -> dict:
    """Return the device-registry info dict for the integration-level
    device that global (non-area) settings entities attach to."""
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": "Smart Ventilation",
        "manufacturer": "Smart Ventilation",
    }


def slugify_state(value: str) -> str:
    """Normalize a human-readable enum value into a valid translation-key
    state ("Not Recommended" -> "not_recommended").

    HA's enum sensor state translation requires the native_value to match a
    strings.json state key satisfying [a-z0-9-_]+ — the calculator's
    internal values ("Optimal", "OPEN", ...) stay as-is everywhere else
    (tests, action/guard logic) and are only normalized here, at the
    sensor-entity boundary.
    """
    return value.lower().replace(" ", "_")
