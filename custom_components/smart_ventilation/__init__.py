"""Smart Ventilation integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_OUTDOOR_TEMP, CONF_OUTDOOR_ABS_HUMIDITY
from .coordinator import SmartVentilationCoordinator

PLATFORMS = ["sensor", "binary_sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Ventilation from a config entry."""
    _LOGGER.info("Setting up Smart Ventilation integration")

    try:
        outdoor_temp = entry.data.get(CONF_OUTDOOR_TEMP)

        _LOGGER.debug("Outdoor temp: %s", outdoor_temp)

        if not outdoor_temp:
            _LOGGER.error("Missing required outdoor temperature sensor")
            return False

        coordinator = SmartVentilationCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        entry.async_on_unload(entry.add_update_listener(async_update_entry))

        _LOGGER.info("Smart Ventilation setup complete")
        return True
    except Exception as exc:
        _LOGGER.exception("Error setting up Smart Ventilation: %s", exc)
        return False


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update a config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
