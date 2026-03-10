"""Smart Ventilation integration."""

from homeassistant.core import HomeAssistant

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up integration via YAML (optional)."""
    return True

async def async_setup_entry(hass, entry):
    """Set up integration via UI."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True

async def async_unload_entry(hass, entry):
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return True