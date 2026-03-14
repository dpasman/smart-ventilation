"""Coordinator for Smart Ventilation."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_AREA_NAME,
    CONF_INDOOR_ABS_HUMIDITY,
    CONF_INDOOR_CO2,
    CONF_INDOOR_DEW_POINT,
    CONF_INDOOR_HEAT_INDEX,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_PM25,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_ABS_HUMIDITY,
    CONF_OUTDOOR_DEW_POINT,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMP,
    CONF_OUTDOOR_TEMP_MAX_24H,
    CONF_WIND_AVG,
    CONF_WIND_MAX,
    DOMAIN,
    VentilationCalculator,
    get_advice,
)


class SmartVentilationCoordinator(DataUpdateCoordinator):
    """Coordinator for Smart Ventilation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.data: dict[str, dict[str, Any]] = {}
        super().__init__(
            hass,
            name=DOMAIN,
            logger=logging.getLogger(__name__),
            update_interval=timedelta(minutes=1),
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Update data for all areas."""
        areas = self.entry.data.get("areas", [])
        outdoor_config = self.entry.data

        outdoor_data = await self._get_outdoor_data(outdoor_config)

        for area in areas:
            area_name = area[CONF_AREA_NAME]
            area_data = await self._get_area_data(area, outdoor_data)
            self.data[area_name] = area_data

        return self.data

    async def _get_outdoor_data(self, config: dict) -> dict[str, float | None]:
        """Get outdoor sensor data."""
        outdoor = {}

        for key, conf_key in [
            ("outdoor_temp", CONF_OUTDOOR_TEMP),
            ("outdoor_abs_humidity", CONF_OUTDOOR_ABS_HUMIDITY),
            ("outdoor_dew_point", CONF_OUTDOOR_DEW_POINT),
            ("outdoor_temp_max_24h", CONF_OUTDOOR_TEMP_MAX_24H),
            ("outdoor_humidity", CONF_OUTDOOR_HUMIDITY),
            ("wind_avg", CONF_WIND_AVG),
            ("wind_max", CONF_WIND_MAX),
        ]:
            entity_id = config.get(conf_key)
            if entity_id:
                state = self.hass.states.get(entity_id)
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        outdoor[key] = float(state.state)
                    except (ValueError, TypeError):
                        outdoor[key] = None
                else:
                    outdoor[key] = None
            else:
                outdoor[key] = None

        return outdoor

    async def _get_area_data(self, area_config: dict, outdoor_data: dict) -> dict[str, Any]:
        """Get area sensor data and calculate efficiency."""
        indoor = {}

        for key, conf_key in [
            ("indoor_temp", CONF_INDOOR_TEMP),
            ("indoor_humidity", CONF_INDOOR_HUMIDITY),
            ("indoor_abs_humidity", CONF_INDOOR_ABS_HUMIDITY),
            ("indoor_dew_point", CONF_INDOOR_DEW_POINT),
            ("indoor_heat_index", CONF_INDOOR_HEAT_INDEX),
            ("indoor_co2", CONF_INDOOR_CO2),
            ("indoor_pm25", CONF_INDOOR_PM25),
        ]:
            entity_id = area_config.get(conf_key)
            if entity_id:
                state = self.hass.states.get(entity_id)
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        indoor[key] = float(state.state)
                    except (ValueError, TypeError):
                        indoor[key] = None
                else:
                    indoor[key] = None
            else:
                indoor[key] = None

        calculator = VentilationCalculator(
            in_temp=indoor.get("indoor_temp") if indoor.get("indoor_temp") is not None else -999,
            in_rh=indoor.get("indoor_humidity") if indoor.get("indoor_humidity") is not None else -999,
            out_temp=outdoor_data.get("outdoor_temp") if outdoor_data.get("outdoor_temp") is not None else -999,
            out_hum_abs=outdoor_data.get("outdoor_abs_humidity") if outdoor_data.get("outdoor_abs_humidity") is not None else 0,
            in_hum_abs=indoor.get("indoor_abs_humidity"),
            in_dew=indoor.get("indoor_dew_point"),
            out_dew=outdoor_data.get("outdoor_dew_point"),
            out_temp_max=outdoor_data.get("outdoor_temp_max_24h"),
            in_heat_index=indoor.get("indoor_heat_index"),
            in_co2=indoor.get("indoor_co2"),
            in_pm25=indoor.get("indoor_pm25"),
            wind_avg=outdoor_data.get("wind_avg"),
            wind_max=outdoor_data.get("wind_max"),
            out_rh=outdoor_data.get("outdoor_humidity"),
            room_type=self._detect_room_type(area_config[CONF_AREA_NAME]),
        )

        efficiency = calculator.calculate()
        reasons = calculator.get_reasons()
        advice = get_advice(efficiency)

        humidity_diff = None
        if indoor.get("indoor_abs_humidity") is not None and outdoor_data.get("outdoor_abs_humidity") is not None:
            humidity_diff = round(indoor["indoor_abs_humidity"] - outdoor_data["outdoor_abs_humidity"], 2)

        temp_diff = None
        if indoor.get("indoor_temp") is not None and outdoor_data.get("outdoor_temp") is not None:
            temp_diff = round(indoor["indoor_temp"] - outdoor_data["outdoor_temp"], 1)

        cooling_recommended = (
            indoor.get("indoor_temp", 0) > 23
            and outdoor_data.get("outdoor_temp", 999) < indoor.get("indoor_temp", 0)
            and outdoor_data.get("outdoor_temp", 999) < 999
            and efficiency > 30
        )

        return {
            "efficiency": efficiency,
            "advice": advice,
            "reasons": reasons,
            "humidity_difference": humidity_diff,
            "temperature_difference": temp_diff,
            "indoor_humidity": indoor.get("indoor_humidity"),
            "indoor_temperature": indoor.get("indoor_temp"),
            "outdoor_humidity": outdoor_data.get("outdoor_humidity"),
            "outdoor_temperature": outdoor_data.get("outdoor_temp"),
            "wind_average": outdoor_data.get("wind_avg"),
            "wind_max": outdoor_data.get("wind_max"),
            "cooling_recommended": cooling_recommended,
        }

    def _detect_room_type(self, area_name: str) -> str:
        """Detect room type from area name."""
        name_lower = area_name.lower()
        if "kitchen" in name_lower or "keuken" in name_lower:
            return "kitchen"
        if "bathroom" in name_lower or "badkamer" in name_lower or "toilet" in name_lower:
            return "bathroom"
        if "bedroom" in name_lower or "slaapkamer" in name_lower:
            return "bedroom"
        if "attic" in name_lower or "zolder" in name_lower:
            return "attic"
        return "generic"

    def get_unique_id(self, area_name: str, sensor_type: str) -> str:
        """Generate unique ID for an entity."""
        return f"{self.entry.entry_id}_{area_name}_{sensor_type}"
