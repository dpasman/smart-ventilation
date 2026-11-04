"""Derive an OPEN/CLOSE/VENTILATE/NONE action from a calculator's signals.

`signals` is the dict returned by VentilationCalculator.get_action_signals()
— this module never reaches into the calculator directly. Priority order:

1. Safety/health overrides (storm, weather_block, condensation_risk all map
   to CLOSE; co2_override maps to OPEN) — always win immediately, bypassing
   everything below.
2. An efficiency tier (see TIERS below).
3. A bounded season-bias nudge of at most one tier step, only within
   SEASON_BIAS_BAND points of a tier boundary.
4. A bounded weather_caution soft downgrade of at most one step
   (OPEN -> VENTILATE -> NONE).
"""

from __future__ import annotations

from datetime import datetime

OPEN = "OPEN"
CLOSE = "CLOSE"
VENTILATE = "VENTILATE"
NONE_ACTION = "NONE"

# (lower_bound_inclusive, action) ascending by lower_bound. 60-79 and 80+ are
# both OPEN but kept as separate tiers so a season-bias nudge has a boundary
# to work against at 80 too, even though crossing it is a no-op action-wise.
TIERS: list[tuple[float, str]] = [
    (float("-inf"), CLOSE),
    (20.0, NONE_ACTION),
    (40.0, VENTILATE),
    (60.0, OPEN),
    (80.0, OPEN),
]
_BOUNDARIES = [lower for lower, _ in TIERS[1:]]  # [20, 40, 60, 80]

SEASON_BIAS_BAND = 5.0
SEASON_AUTO = "auto"
SEASON_SUMMER = "summer"
SEASON_WINTER = "winter"
_SUMMER_MONTHS = {6, 7, 8}
_WINTER_MONTHS = {12, 1, 2}

_CAUTION_DOWNGRADE = {OPEN: VENTILATE, VENTILATE: NONE_ACTION}


def _tier_index(efficiency: float) -> int:
    index = 0
    for i, (lower, _action) in enumerate(TIERS):
        if efficiency >= lower:
            index = i
    return index


def _effective_season(season_bias: str, now: datetime | None) -> str | None:
    if season_bias == SEASON_SUMMER:
        return SEASON_SUMMER
    if season_bias == SEASON_WINTER:
        return SEASON_WINTER
    if season_bias == SEASON_AUTO and now is not None:
        if now.month in _SUMMER_MONTHS:
            return SEASON_SUMMER
        if now.month in _WINTER_MONTHS:
            return SEASON_WINTER
    return None


def _apply_season_bias(tier_index: int, efficiency: float, season: str | None) -> int:
    if season == SEASON_SUMMER and tier_index < len(TIERS) - 1:
        next_boundary = _BOUNDARIES[tier_index]
        if next_boundary - SEASON_BIAS_BAND <= efficiency < next_boundary:
            return tier_index + 1
    if season == SEASON_WINTER and tier_index > 0:
        this_boundary = _BOUNDARIES[tier_index - 1]
        if this_boundary <= efficiency < this_boundary + SEASON_BIAS_BAND:
            return tier_index - 1
    return tier_index


def derive_action(
    efficiency: float,
    signals: dict,
    season_bias: str = SEASON_AUTO,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Return (action, is_override)."""
    if signals.get("storm"):
        return CLOSE, True
    if signals.get("weather_block"):
        return CLOSE, True
    if signals.get("condensation_risk"):
        return CLOSE, True
    if signals.get("co2_override"):
        return OPEN, True

    tier_index = _tier_index(efficiency)
    season = _effective_season(season_bias, now)
    tier_index = _apply_season_bias(tier_index, efficiency, season)
    action = TIERS[tier_index][1]

    if signals.get("weather_caution") and action in _CAUTION_DOWNGRADE:
        action = _CAUTION_DOWNGRADE[action]

    return action, False
