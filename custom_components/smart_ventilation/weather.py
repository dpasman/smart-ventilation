"""Thin HA-aware wrapper around weather_rules: reads a weather entity's
current condition and near-term forecast, never raising into the caller.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .weather_rules import classify_current_condition, classify_forecast

_LOGGER = logging.getLogger(__name__)

DEFAULT_FORECAST_HORIZON_MINUTES = 120


@dataclass(frozen=True)
class WeatherSignal:
    """Classified current + near-term-forecast weather state for one poll."""

    condition: str | None
    current: str  # "block" | "caution" | "clear"
    forecast: str  # "block" | "caution" | "clear"

    @property
    def block(self) -> bool:
        return self.current == "block" or self.forecast == "block"

    @property
    def caution(self) -> bool:
        return not self.block and (self.current == "caution" or self.forecast == "caution")


async def async_get_weather_signal(
    hass: HomeAssistant,
    weather_entity_id: str | None,
    horizon_minutes: int = DEFAULT_FORECAST_HORIZON_MINUTES,
) -> WeatherSignal | None:
    """Return the classified weather signal for `weather_entity_id`, or None.

    Returns None cleanly when no weather entity is configured or its state
    is unavailable — callers should treat that the same as "no weather
    information", not as an error. Never raises.
    """
    if not weather_entity_id:
        return None

    state = hass.states.get(weather_entity_id)
    if state is None or state.state in ("unknown", "unavailable"):
        return None

    condition = str(state.state)
    current = classify_current_condition(condition)

    forecast_entries = await _async_fetch_forecast_entries(hass, weather_entity_id, state)
    now = dt_util.now()
    forecast = classify_forecast(forecast_entries, horizon_minutes, now)

    return WeatherSignal(condition=condition, current=current, forecast=forecast)


async def _async_fetch_forecast_entries(
    hass: HomeAssistant,
    weather_entity_id: str,
    state,
) -> list[dict]:
    """Return hourly forecast entries via the weather.get_forecasts service,
    falling back to the entity's "forecast" state attribute.

    Not every weather integration supports the get_forecasts service (or
    hourly granularity) — any failure degrades silently to the attribute
    fallback, and ultimately to an empty list, rather than raising.
    """
    try:
        response = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": weather_entity_id, "type": "hourly"},
            blocking=True,
            return_response=True,
        )
        if isinstance(response, dict):
            payload = response.get(weather_entity_id)
            if isinstance(payload, dict):
                forecast = payload.get("forecast")
                if isinstance(forecast, list):
                    return forecast
    except Exception:  # noqa: BLE001 - a provider may not support this at all
        _LOGGER.debug(
            "Smart Ventilation: hourly forecast unavailable for %s, "
            "falling back to the forecast state attribute",
            weather_entity_id,
            exc_info=True,
        )

    attributes = getattr(state, "attributes", {}) or {}
    forecast = attributes.get("forecast")
    return forecast if isinstance(forecast, list) else []
