from homeassistant.core import HomeAssistant
from .sensor import SmartVentilationSensor

async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up sensors per config entry (room)."""
    room_name = entry.title
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    # register sensor entity
    hass.states.async_set(
        f"sensor.smart_ventilation_score_{room_name.lower()}",
        None,
        {}
    )
    return True