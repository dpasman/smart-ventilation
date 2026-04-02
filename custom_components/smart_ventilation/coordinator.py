"""Coordinator for Smart Ventilation."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .calculator import (
    VentilationCalculator,
    calculate_absolute_humidity,
    calculate_dew_point,
    calculate_heat_index,
    get_advice,
)
from .const import (
    CONF_AREA_NAME,
    CONF_INDOOR_CO2,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_PM25,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_ABS_HUMIDITY,
    CONF_OUTDOOR_DEW_POINT,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_PM25,
    CONF_OUTDOOR_TEMP,
    CONF_OUTDOOR_TEMP_MAX_24H,
    CONF_WIND_AVG,
    CONF_WIND_MAX,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SmartVentilationCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator for Smart Ventilation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self.entry = entry

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch sensor states and calculate data for all configured areas."""
        outdoor = self._get_outdoor_data()
        areas = self.entry.options.get("areas") or self.entry.data.get("areas", [])
        return {
            area[CONF_AREA_NAME]: self._get_area_data(area, outdoor)
            for area in areas
        }

    def _read_state(self, entity_id: str | None) -> float | None:
        """Return the numeric state of an entity, or None if missing/unavailable."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _read_wind_ms(self, entity_id: str | None) -> float | None:
        """Read a wind speed sensor and return the value normalized to m/s.

        Detects the unit_of_measurement attribute and converts km/h → m/s
        automatically so the calculator always works in m/s regardless of
        what the sensor reports.
        """
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            value = float(state.state)
        except (ValueError, TypeError):
            return None
        unit = state.attributes.get("unit_of_measurement", "")
        if unit in ("km/h", "km/u"):
            return round(value / 3.6, 2)
        return value

    def _get_outdoor_data(self) -> dict[str, float | None]:
        """Read all outdoor sensor states from HA, computing derived values if needed."""
        cfg = self.entry.data
        outdoor_temp = self._read_state(cfg.get(CONF_OUTDOOR_TEMP))
        outdoor_rh = self._read_state(cfg.get(CONF_OUTDOOR_HUMIDITY))

        outdoor_abs = self._read_state(cfg.get(CONF_OUTDOOR_ABS_HUMIDITY))
        if outdoor_abs is None and outdoor_temp is not None and outdoor_rh is not None:
            outdoor_abs = calculate_absolute_humidity(outdoor_temp, outdoor_rh)

        outdoor_dew = self._read_state(cfg.get(CONF_OUTDOOR_DEW_POINT))
        if outdoor_dew is None and outdoor_temp is not None and outdoor_rh is not None:
            outdoor_dew = calculate_dew_point(outdoor_temp, outdoor_rh)

        return {
            "outdoor_temp": outdoor_temp,
            "outdoor_abs_humidity": outdoor_abs,
            "outdoor_dew_point": outdoor_dew,
            "outdoor_temp_max_24h": self._read_state(cfg.get(CONF_OUTDOOR_TEMP_MAX_24H)),
            "outdoor_humidity": outdoor_rh,
            "wind_avg": self._read_wind_ms(cfg.get(CONF_WIND_AVG)),
            "wind_max": self._read_wind_ms(cfg.get(CONF_WIND_MAX)),
            "outdoor_pm25": self._read_state(cfg.get(CONF_OUTDOOR_PM25)),
        }

    def _get_area_data(
        self, area_config: dict, outdoor: dict[str, float | None]
    ) -> dict[str, Any]:
        """Read area sensor states, run calculator, return result dict."""
        in_temp = self._read_state(area_config.get(CONF_INDOOR_TEMP))
        in_humidity = self._read_state(area_config.get(CONF_INDOOR_HUMIDITY))
        out_temp = outdoor["outdoor_temp"]

        in_hum_abs = None
        in_dew = None
        in_heat_index = None
        if in_temp is not None and in_humidity is not None:
            in_hum_abs = calculate_absolute_humidity(in_temp, in_humidity)
            in_dew = calculate_dew_point(in_temp, in_humidity)
            in_heat_index = calculate_heat_index(in_temp, in_humidity)

        calc = VentilationCalculator(
            in_temp=in_temp,
            in_rh=in_humidity,
            out_temp=out_temp,
            out_hum_abs=outdoor["outdoor_abs_humidity"],
            in_hum_abs=in_hum_abs,
            in_dew=in_dew,
            out_dew=outdoor["outdoor_dew_point"],
            out_temp_max=outdoor["outdoor_temp_max_24h"],
            in_heat_index=in_heat_index,
            in_co2=self._read_state(area_config.get(CONF_INDOOR_CO2)),
            in_pm25=self._read_state(area_config.get(CONF_INDOOR_PM25)),
            out_pm25=outdoor["outdoor_pm25"],
            wind_avg=outdoor["wind_avg"],
            wind_max=outdoor["wind_max"],
            out_rh=outdoor["outdoor_humidity"],
            room_type=self._detect_room_type(area_config[CONF_AREA_NAME]),
        )

        efficiency = calc.calculate()

        air_quality_result = calc.get_air_quality()
        ventilation_reason = calc.get_ventilation_reason()

        cooling_recommended = (
            in_temp is not None
            and out_temp is not None
            and in_temp > 23
            and out_temp < in_temp
            and efficiency > 30
        )

        humidity_diff = None
        out_abs = outdoor["outdoor_abs_humidity"]
        if in_hum_abs is not None and out_abs is not None:
            humidity_diff = round(in_hum_abs - out_abs, 2)

        temp_diff = None
        if in_temp is not None and out_temp is not None:
            temp_diff = round(in_temp - out_temp, 1)

        return {
            "efficiency": efficiency,
            "advice": get_advice(efficiency),
            "reasons": calc.get_reasons(),
            "humidity_difference": humidity_diff,
            "temperature_difference": temp_diff,
            "cooling_recommended": cooling_recommended,
            "indoor_temperature": in_temp,
            "outdoor_temperature": out_temp,
            "air_quality": air_quality_result["level"],
            "air_quality_attributes": {
                "co2_category": air_quality_result["co2_category"],
                "pm25_category": air_quality_result["pm25_category"],
                "humidity_category": air_quality_result["humidity_category"],
                "temperature_category": air_quality_result["temperature_category"],
                "worst_parameter": air_quality_result["worst_parameter"],
            },
            "ventilation_reason": ventilation_reason,
        }

    def _detect_room_type(self, area_name: str) -> str:
        """Infer room type from area name (English + Dutch keywords)."""
        name = area_name.lower()
        if any(k in name for k in ("kitchen", "keuken")):
            return "kitchen"
        if any(k in name for k in ("bathroom", "badkamer", "toilet")):
            return "bathroom"
        if any(k in name for k in ("bedroom", "slaapkamer")):
            return "bedroom"
        if any(k in name for k in ("attic", "zolder")):
            return "attic"
        return "generic"
