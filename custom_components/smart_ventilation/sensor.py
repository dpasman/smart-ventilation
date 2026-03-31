"""Sensor platform for Smart Ventilation."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VENTILATION_ADVICE_LEVELS
from .coordinator import SmartVentilationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for each configured area."""
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for area in entry.data.get("areas", []):
        area_name = area["name"]
        entities.extend(
            [
                VentilationEfficiencySensor(coordinator, entry, area_name),
                VentilationAdviceSensor(coordinator, entry, area_name),
                HumidityDifferenceSensor(coordinator, entry, area_name),
                TemperatureDifferenceSensor(coordinator, entry, area_name),
            ]
        )
    async_add_entities(entities)


def _device_info(entry: ConfigEntry, area_name: str) -> dict:
    return {
        "identifiers": {(DOMAIN, f"{entry.entry_id}_{area_name}")},
        "name": area_name,
        "manufacturer": "Smart Ventilation",
    }


class _AreaSensor(CoordinatorEntity[SmartVentilationCoordinator], SensorEntity):
    """Base class for all Smart Ventilation area sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.area_name = area_name
        self._attr_device_info = _device_info(entry, area_name)

    @property
    def available(self) -> bool:
        return super().available and self.area_name in (self.coordinator.data or {})

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data.get(self.area_name, {}))
        self.async_write_ha_state()

    def _update_from_data(self, data: dict) -> None:
        """Extract entity value from coordinator data. Override in subclasses."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()


class VentilationEfficiencySensor(_AreaSensor):
    """Ventilation efficiency as a percentage (0–100%)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:air-filter"
    _attr_translation_key = "ventilation_efficiency"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator, entry, area_name)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_efficiency"

    def _update_from_data(self, data: dict) -> None:
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


class VentilationAdviceSensor(_AreaSensor):
    """Ventilation advice as an ENUM string."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = VENTILATION_ADVICE_LEVELS
    _attr_translation_key = "ventilation_advice"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator, entry, area_name)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_advice"

    def _update_from_data(self, data: dict) -> None:
        self._attr_native_value = data.get("advice", "Not Recommended")


class HumidityDifferenceSensor(_AreaSensor):
    """Absolute humidity difference indoor vs outdoor (g/m³)."""

    _attr_native_unit_of_measurement = "g/m³"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-percent"
    _attr_translation_key = "humidity_difference"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator, entry, area_name)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_humidity_diff"

    def _update_from_data(self, data: dict) -> None:
        self._attr_native_value = data.get("humidity_difference")


class TemperatureDifferenceSensor(_AreaSensor):
    """Temperature difference indoor vs outdoor (°C)."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "temperature_difference"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator, entry, area_name)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_temperature_diff"

    def _update_from_data(self, data: dict) -> None:
        self._attr_native_value = data.get("temperature_difference")
