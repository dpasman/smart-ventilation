"""Sensor for Smart Ventilation."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEVICE_TYPE_VENTILATION_EFFICIENCY
from .coordinator import SmartVentilationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    areas = entry.data.get("areas", [])

    entities = []
    for area in areas:
        area_name = area["name"]
        entities.append(
            VentilationEfficiencySensor(coordinator, entry, area_name),
        )
        entities.append(
            VentilationAdviceSensor(coordinator, entry, area_name),
        )
        entities.append(
            HumidityDifferenceSensor(coordinator, entry, area_name),
        )
        entities.append(
            TemperatureDifferenceSensor(coordinator, entry, area_name),
        )

    async_add_entities(entities)


class VentilationEfficiencySensor(SensorEntity):
    """Sensor for ventilation efficiency."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:air-filter"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entry = entry
        self.area_name = area_name
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_efficiency"
        self._attr_name = f"Ventilation Efficiency {area_name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{area_name}")},
            "name": area_name,
            "manufacturer": "Smart Ventilation",
            "model": "Ventilation Efficiency",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.area_name, {})
        efficiency = data.get("efficiency", 0)
        self._attr_native_value = int(efficiency)

        if efficiency >= 80:
            self._attr_icon = "mdi:air-filter"
        elif efficiency >= 60:
            self._attr_icon = "mdi:air-purifier"
        elif efficiency >= 30:
            self._attr_icon = "mdi:air-humidifier"
        else:
            self._attr_icon = "mdi:air-humidifier-off"

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()


class VentilationAdviceSensor(SensorEntity):
    """Sensor for ventilation advice."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entry = entry
        self.area_name = area_name
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_advice"
        self._attr_name = f"Ventilation Advice {area_name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{area_name}")},
            "name": area_name,
            "manufacturer": "Smart Ventilation",
            "model": "Ventilation Advice",
        }
        self._attr_options = ["Optimal", "Recommended", "Decent", "Neutral", "Not Recommended"]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.area_name, {})
        self._attr_native_value = data.get("advice", "Not Recommended")
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()


class HumidityDifferenceSensor(SensorEntity):
    """Sensor for humidity difference."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = "g/m³"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entry = entry
        self.area_name = area_name
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_humidity_diff"
        self._attr_name = f"Humidity Difference {area_name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{area_name}")},
            "name": area_name,
            "manufacturer": "Smart Ventilation",
            "model": "Humidity Difference",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.area_name, {})
        self._attr_native_value = data.get("humidity_difference")
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()


class TemperatureDifferenceSensor(SensorEntity):
    """Sensor for temperature difference."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entry = entry
        self.area_name = area_name
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_temperature_diff"
        self._attr_name = f"Temperature Difference {area_name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{area_name}")},
            "name": area_name,
            "manufacturer": "Smart Ventilation",
            "model": "Temperature Difference",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.area_name, {})
        self._attr_native_value = data.get("temperature_difference")
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()
