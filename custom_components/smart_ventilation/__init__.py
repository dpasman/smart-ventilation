"""Smart Ventilation integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_AREA_NAME, CONF_OUTDOOR_TEMP, DOMAIN
from .coordinator import SmartVentilationCoordinator

PLATFORMS = ["sensor", "binary_sensor"]


def _get_areas(entry: ConfigEntry) -> list:
    """Return areas from options (current) or data (legacy)."""
    return entry.options.get("areas") or entry.data.get("areas", [])


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Ventilation from a config entry."""
    if not entry.data.get(CONF_OUTDOOR_TEMP):
        return False

    coordinator = SmartVentilationCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _cleanup_stale_devices(hass, entry)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


def _cleanup_stale_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove devices for areas that no longer exist."""
    areas = _get_areas(entry)
    current_ids = {
        (DOMAIN, f"{entry.entry_id}_{area[CONF_AREA_NAME]}") for area in areas
    }
    device_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
        if not device.identifiers & current_ids:
            device_reg.async_remove_device(device.id)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change (area added, edited or removed)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
