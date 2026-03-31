"""Coordinator for Smart Ventilation."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .calculator import VentilationCalculator, get_advice
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
        return {
            area[CONF_AREA_NAME]: self._get_area_data(area, outdoor)
            for area in self.entry.data.get("areas", [])
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

    def _get_outdoor_data(self) -> dict[str, float | None]:
        """Read all outdoor sensor states from HA."""
        cfg = self.entry.data
        return {
            "outdoor_temp": self._read_state(cfg.get(CONF_OUTDOOR_TEMP)),
            "outdoor_abs_humidity": self._read_state(cfg.get(CONF_OUTDOOR_ABS_HUMIDITY)),
            "outdoor_dew_point": self._read_state(cfg.get(CONF_OUTDOOR_DEW_POINT)),
            "outdoor_temp_max_24h": self._read_state(cfg.get(CONF_OUTDOOR_TEMP_MAX_24H)),
            "outdoor_humidity": self._read_state(cfg.get(CONF_OUTDOOR_HUMIDITY)),
            "wind_avg": self._read_state(cfg.get(CONF_WIND_AVG)),
            "wind_max": self._read_state(cfg.get(CONF_WIND_MAX)),
        }

    def _get_area_data(
        self, area_config: dict, outdoor: dict[str, float | None]
    ) -> dict[str, Any]:
        """Read area sensor states, run calculator, return result dict."""
        in_temp = self._read_state(area_config.get(CONF_INDOOR_TEMP))
        in_humidity = self._read_state(area_config.get(CONF_INDOOR_HUMIDITY))
        out_temp = outdoor["outdoor_temp"]

        calc = VentilationCalculator(
            in_temp=in_temp,
            in_rh=in_humidity,
            out_temp=out_temp,
            out_hum_abs=outdoor["outdoor_abs_humidity"],
            in_hum_abs=self._read_state(area_config.get(CONF_INDOOR_ABS_HUMIDITY)),
            in_dew=self._read_state(area_config.get(CONF_INDOOR_DEW_POINT)),
            out_dew=outdoor["outdoor_dew_point"],
            out_temp_max=outdoor["outdoor_temp_max_24h"],
            in_heat_index=self._read_state(area_config.get(CONF_INDOOR_HEAT_INDEX)),
            in_co2=self._read_state(area_config.get(CONF_INDOOR_CO2)),
            in_pm25=self._read_state(area_config.get(CONF_INDOOR_PM25)),
            wind_avg=outdoor["wind_avg"],
            wind_max=outdoor["wind_max"],
            out_rh=outdoor["outdoor_humidity"],
            room_type=self._detect_room_type(area_config[CONF_AREA_NAME]),
        )

        efficiency = calc.calculate()

        cooling_recommended = (
            in_temp is not None
            and out_temp is not None
            and in_temp > 23
            and out_temp < in_temp
            and efficiency > 30
        )

        humidity_diff = None
        in_abs = self._read_state(area_config.get(CONF_INDOOR_ABS_HUMIDITY))
        out_abs = outdoor["outdoor_abs_humidity"]
        if in_abs is not None and out_abs is not None:
            humidity_diff = round(in_abs - out_abs, 2)

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
