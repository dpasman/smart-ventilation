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
