"""Tests for weather_rules: current-condition and forecast classification."""

from datetime import datetime, timedelta, timezone

from custom_components.smart_ventilation.weather_rules import (
    classify_current_condition,
    classify_forecast,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestClassifyCurrentCondition:
    def test_none_is_clear(self):
        assert classify_current_condition(None) == "clear"

    def test_unknown_string_is_clear(self):
        assert classify_current_condition("partlycloudy") == "clear"

    def test_lightning_variants_block(self):
        assert classify_current_condition("lightning") == "block"
        assert classify_current_condition("lightning-rainy") == "block"
        assert classify_current_condition("hail") == "block"

    def test_rain_snow_fog_wind_caution(self):
        for condition in ("rainy", "pouring", "snowy", "snowy-rainy", "fog", "windy"):
            assert classify_current_condition(condition) == "caution"

    def test_case_insensitive(self):
        assert classify_current_condition("LIGHTNING") == "block"
        assert classify_current_condition(" Rainy ") == "caution"


class TestClassifyForecast:
    def test_empty_list_is_clear(self):
        assert classify_forecast([], horizon_minutes=120, now=NOW) == "clear"

    def test_entries_past_horizon_are_ignored(self):
        entries = [{"datetime": (NOW + timedelta(hours=5)).isoformat(), "condition": "lightning"}]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "clear"

    def test_entries_before_now_are_ignored(self):
        entries = [{"datetime": (NOW - timedelta(hours=1)).isoformat(), "condition": "lightning"}]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "clear"

    def test_block_condition_within_horizon(self):
        entries = [{"datetime": (NOW + timedelta(hours=1)).isoformat(), "condition": "hail"}]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "block"

    def test_worst_of_mixed_entries_wins(self):
        entries = [
            {"datetime": (NOW + timedelta(minutes=30)).isoformat(), "condition": "sunny"},
            {"datetime": (NOW + timedelta(hours=1)).isoformat(), "condition": "rainy"},
            {"datetime": (NOW + timedelta(hours=1, minutes=30)).isoformat(), "condition": "lightning"},
        ]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "block"

    def test_high_precipitation_probability_blocks(self):
        entries = [{"datetime": (NOW + timedelta(minutes=30)).isoformat(), "precipitation_probability": 85}]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "block"

    def test_moderate_precipitation_probability_cautions(self):
        entries = [{"datetime": (NOW + timedelta(minutes=30)).isoformat(), "precipitation_probability": 55}]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "caution"

    def test_high_wind_speed_blocks(self):
        entries = [{"datetime": (NOW + timedelta(minutes=30)).isoformat(), "wind_speed": 16.0}]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "block"

    def test_moderate_wind_speed_cautions(self):
        entries = [{"datetime": (NOW + timedelta(minutes=30)).isoformat(), "wind_speed": 11.0}]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "caution"

    def test_unparseable_datetime_ignored(self):
        entries = [{"datetime": "not-a-date", "condition": "hail"}]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "clear"

    def test_missing_datetime_ignored(self):
        entries = [{"condition": "hail"}]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "clear"

    def test_non_dict_entries_ignored(self):
        assert classify_forecast(["garbage", 123, None], horizon_minutes=120, now=NOW) == "clear"

    def test_naive_entry_datetime_with_aware_now(self):
        entries = [{"datetime": (NOW + timedelta(hours=1)).replace(tzinfo=None).isoformat(), "condition": "hail"}]
        assert classify_forecast(entries, horizon_minutes=120, now=NOW) == "block"
