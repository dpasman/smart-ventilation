"""Smart Ventilation integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_AREA_NAME, CONF_OUTDOOR_TEMP, DOMAIN
from .coordinator import SmartVentilationCoordinator
from .notification import NotificationManager
from .runtime import RuntimeStore

PLATFORMS = ["sensor", "binary_sensor", "number", "time", "switch", "button"]


def _get_areas(entry: ConfigEntry) -> list:
    """Return areas from options (current) or data (legacy)."""
    return entry.options.get("areas") or entry.data.get("areas", [])


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Ventilation from a config entry."""
    if not entry.data.get(CONF_OUTDOOR_TEMP):
        return False

    coordinator = SmartVentilationCoordinator(hass, entry)
    # Both attached before the first refresh (not after): _async_update_data
    # reads coordinator.runtime.settings and calls coordinator.notifier on
    # every poll, including the first one.
    coordinator.runtime = RuntimeStore(hass, entry)
    coordinator.runtime.ensure_defaults()
    coordinator.notifier = NotificationManager(hass, entry, coordinator.runtime)
    entry.async_on_unload(coordinator.notifier.async_setup())
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _cleanup_stale_devices(hass, entry)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


def _cleanup_stale_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove devices for areas that no longer exist.

    Keeps the integration-level global-settings device (identified by the
    entry_id alone, see entity_helpers.global_device_info) — it isn't tied
    to any area, so it would otherwise never appear in current_ids and get
    deleted on every setup.
    """
    areas = _get_areas(entry)
    current_ids = {
        (DOMAIN, f"{entry.entry_id}_{area[CONF_AREA_NAME]}") for area in areas
    }
    current_ids.add((DOMAIN, entry.entry_id))
    device_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
        if not device.identifiers & current_ids:
            device_reg.async_remove_device(device.id)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change (area added/edited/removed, or a
    global setting changed through the options flow).

    A live number/time/switch entity write goes through
    RuntimeStore.save_settings()/save_area_state(), which sets a consume-
    once "suppress next reload" flag first — those writes only need a
    coordinator refresh, not a full platform teardown/recreate.
    """
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.runtime.suppress_next_reload():
        await coordinator.async_request_refresh()
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
