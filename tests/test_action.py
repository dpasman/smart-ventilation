"""Tests for derive_action: tiers, overrides, season bias, weather caution."""

from datetime import datetime, timezone

from custom_components.smart_ventilation.action import derive_action

NO_SIGNALS = {
    "storm": False, "weather_block": False, "condensation_risk": False,
    "co2_override": False, "weather_caution": False,
}
JULY = datetime(2026, 7, 15, tzinfo=timezone.utc)
JANUARY = datetime(2026, 1, 15, tzinfo=timezone.utc)
APRIL = datetime(2026, 4, 15, tzinfo=timezone.utc)


def _signals(**overrides):
    return {**NO_SIGNALS, **overrides}


class TestTiers:
    def test_80_plus_is_open(self):
        assert derive_action(85.0, NO_SIGNALS) == ("OPEN", False)

    def test_60_to_79_is_open(self):
        assert derive_action(65.0, NO_SIGNALS) == ("OPEN", False)

    def test_40_to_59_is_ventilate(self):
        assert derive_action(50.0, NO_SIGNALS) == ("VENTILATE", False)

    def test_20_to_39_is_none(self):
        assert derive_action(25.0, NO_SIGNALS) == ("NONE", False)

    def test_below_20_is_close(self):
        assert derive_action(10.0, NO_SIGNALS) == ("CLOSE", False)

    def test_zero_is_close(self):
        assert derive_action(0.0, NO_SIGNALS) == ("CLOSE", False)


class TestOverridesWinInPriorityOrder:
    def test_storm_overrides_everything(self):
        signals = _signals(storm=True, weather_block=True, condensation_risk=True, co2_override=True)
        assert derive_action(90.0, signals) == ("CLOSE", True)

    def test_weather_block_overrides_condensation_and_co2(self):
        signals = _signals(weather_block=True, condensation_risk=True, co2_override=True)
        assert derive_action(90.0, signals) == ("CLOSE", True)

    def test_condensation_risk_overrides_co2(self):
        signals = _signals(condensation_risk=True, co2_override=True)
        assert derive_action(90.0, signals) == ("CLOSE", True)

    def test_co2_override_alone_forces_open(self):
        signals = _signals(co2_override=True)
        assert derive_action(10.0, signals) == ("OPEN", True)

    def test_co2_override_wins_over_low_efficiency(self):
        signals = _signals(co2_override=True)
        action, override = derive_action(0.0, signals)
        assert action == "OPEN"
        assert override is True


class TestSeasonBias:
    def test_summer_nudges_up_near_60_boundary(self):
        # 57 is within 5 points below 60 -> nudged from VENTILATE to OPEN
        assert derive_action(57.0, NO_SIGNALS, season_bias="summer") == ("OPEN", False)

    def test_summer_does_not_nudge_far_from_boundary(self):
        assert derive_action(45.0, NO_SIGNALS, season_bias="summer") == ("VENTILATE", False)

    def test_summer_nudge_is_only_one_tier_step(self):
        # 57 nudged from VENTILATE to OPEN, not further
        action, _ = derive_action(57.0, NO_SIGNALS, season_bias="summer")
        assert action == "OPEN"

    def test_summer_cannot_push_past_open(self):
        # Already at the top tier (80+) — nudging across the inert 80
        # boundary stays OPEN, never anything beyond.
        assert derive_action(77.0, NO_SIGNALS, season_bias="summer") == ("OPEN", False)

    def test_winter_nudges_down_near_40_boundary(self):
        # 42 is within 5 points above 40 -> nudged from VENTILATE to NONE
        assert derive_action(42.0, NO_SIGNALS, season_bias="winter") == ("NONE", False)

    def test_winter_does_not_nudge_far_from_boundary(self):
        assert derive_action(55.0, NO_SIGNALS, season_bias="winter") == ("VENTILATE", False)

    def test_winter_nudges_none_down_to_close_near_20_boundary(self):
        assert derive_action(21.0, NO_SIGNALS, season_bias="winter") == ("CLOSE", False)

    def test_winter_cannot_push_past_close(self):
        # Already CLOSE, nowhere lower to go, and no boundary below it to nudge against.
        assert derive_action(10.0, NO_SIGNALS, season_bias="winter") == ("CLOSE", False)

    def test_auto_summer_month_behaves_like_summer(self):
        assert derive_action(57.0, NO_SIGNALS, season_bias="auto", now=JULY) == ("OPEN", False)

    def test_auto_winter_month_behaves_like_winter(self):
        assert derive_action(42.0, NO_SIGNALS, season_bias="auto", now=JANUARY) == ("NONE", False)

    def test_auto_shoulder_month_applies_no_bias(self):
        assert derive_action(57.0, NO_SIGNALS, season_bias="auto", now=APRIL) == ("VENTILATE", False)

    def test_auto_with_no_now_applies_no_bias(self):
        assert derive_action(57.0, NO_SIGNALS, season_bias="auto", now=None) == ("VENTILATE", False)


class TestWeatherCaution:
    def test_caution_downgrades_open_to_ventilate(self):
        signals = _signals(weather_caution=True)
        assert derive_action(85.0, signals) == ("VENTILATE", False)

    def test_caution_downgrades_ventilate_to_none(self):
        signals = _signals(weather_caution=True)
        assert derive_action(50.0, signals) == ("NONE", False)

    def test_caution_does_not_touch_none(self):
        signals = _signals(weather_caution=True)
        assert derive_action(25.0, signals) == ("NONE", False)

    def test_caution_does_not_touch_close(self):
        signals = _signals(weather_caution=True)
        assert derive_action(10.0, signals) == ("CLOSE", False)

    def test_caution_applies_after_season_bias(self):
        # 57 summer-nudged to OPEN, then caution downgrades one step to VENTILATE
        signals = _signals(weather_caution=True)
        assert derive_action(57.0, signals, season_bias="summer") == ("VENTILATE", False)

    def test_caution_is_bypassed_by_an_override(self):
        signals = _signals(weather_caution=True, co2_override=True)
        assert derive_action(10.0, signals) == ("OPEN", True)
