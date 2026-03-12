"""Smart Ventilation integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .sensor import SmartVentilationSensor
from homeassistant.const import Platform

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up integration via YAML (optional)."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up integration via UI."""
    room_name = entry.data.get("room_name", "Unknown")
    
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(entry.domain, entry.entry_id)},
        name=f"Smart Ventilation - {room_name}",
    )
    
    sensor = SmartVentilationSensor(hass, entry, room_name, device.id)
    await hass.async_add_entities([sensor])
    
    return True

async def async_unload_entry(hass, entry):
    await hass.config_entries.async_unload_entry(entry)
    return True
