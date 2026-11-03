"""Pure classification rules for weather conditions — no HA imports.

Mirrors the spirit of calculator.py's existing _storm_penalty() (wind is a
safety/practicality concern) but for the broader set of conditions a
weather entity can report: thunderstorms/hail are a safety blocker just
like strong wind already is, while rain/snow/fog/wind are a softer
"things are about to get worse" caution.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

Classification = Literal["block", "caution", "clear"]

# Home Assistant's standardized weather condition strings
# (homeassistant.components.weather.ATTR_CONDITION_*).
_BLOCK_CONDITIONS = {"lightning", "lightning-rainy", "hail", "exceptional"}
_CAUTION_CONDITIONS = {
    "pouring", "rainy", "snowy", "snowy-rainy", "windy", "windy-variant", "fog",
}

PRECIPITATION_BLOCK_PROBABILITY = 80
PRECIPITATION_CAUTION_PROBABILITY = 50
WIND_BLOCK_MS = 15.0
WIND_CAUTION_MS = 10.0


def classify_current_condition(condition: str | None) -> Classification:
    """Classify a weather entity's current `state` string."""
    if not condition:
        return "clear"
    normalized = condition.strip().lower()
    if normalized in _BLOCK_CONDITIONS:
        return "block"
    if normalized in _CAUTION_CONDITIONS:
        return "caution"
    return "clear"


def _classify_forecast_entry(entry: dict) -> Classification:
    condition = classify_current_condition(entry.get("condition"))
    if condition == "block":
        return "block"

    precipitation = entry.get("precipitation_probability")
    wind_speed = entry.get("wind_speed")

    if precipitation is not None and precipitation >= PRECIPITATION_BLOCK_PROBABILITY:
        return "block"
    if wind_speed is not None and wind_speed >= WIND_BLOCK_MS:
        return "block"

    if condition == "caution":
        return "caution"
    if precipitation is not None and precipitation >= PRECIPITATION_CAUTION_PROBABILITY:
        return "caution"
    if wind_speed is not None and wind_speed >= WIND_CAUTION_MS:
        return "caution"

    return "clear"


def classify_forecast(
    entries: list[dict],
    horizon_minutes: int,
    now: datetime,
) -> Classification:
    """Classify the worst condition among forecast entries within the horizon.

    Each entry is a plain dict with at least a "datetime" (ISO 8601 string)
    key, and optionally "condition", "precipitation_probability", and
    "wind_speed" (m/s). Entries without a parseable "datetime", or outside
    [now, now + horizon_minutes], are ignored. An empty/all-out-of-range
    list classifies as "clear" — no data is not a reason to block.
    """
    horizon_end = now + timedelta(minutes=horizon_minutes)
    worst: Classification = "clear"
    rank = {"clear": 0, "caution": 1, "block": 2}

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw_datetime = entry.get("datetime")
        if not raw_datetime:
            continue
        try:
            entry_at = datetime.fromisoformat(str(raw_datetime))
        except ValueError:
            continue
        if entry_at.tzinfo is None and now.tzinfo is not None:
            entry_at = entry_at.replace(tzinfo=now.tzinfo)
        elif entry_at.tzinfo is not None and now.tzinfo is None:
            entry_at = entry_at.replace(tzinfo=None)
        if not (now <= entry_at <= horizon_end):
            continue
        classification = _classify_forecast_entry(entry)
        if rank[classification] > rank[worst]:
            worst = classification
            if worst == "block":
                break

    return worst
