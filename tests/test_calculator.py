"""Tests for VentilationCalculator.get_air_quality() and get_ventilation_reason()."""

import pytest
from custom_components.smart_ventilation.calculator import VentilationCalculator


def _calc(**kwargs) -> VentilationCalculator:
    """Helper: build a VentilationCalculator with sensible defaults, overridable by kwargs."""
    defaults = dict(
        in_temp=21.0,
        in_rh=50.0,
        out_temp=15.0,
        out_hum_abs=7.0,
    )
    defaults.update(kwargs)
    return VentilationCalculator(**defaults)


# ── get_air_quality ───────────────────────────────────────────────────────────

class TestGetAirQuality:
    """get_air_quality() covers CO2 and PM2.5 only — see TestGetComfort for
    temperature/humidity, which live on the separate get_comfort() method."""

    def test_excellent_all_parameters(self):
        c = _calc(in_temp=22.0, in_rh=50.0, in_co2=700.0, in_pm25=10.0)
        result = c.get_air_quality()
        assert result["level"] == "Excellent"
        assert result["co2_category"] == "Excellent"
        assert result["pm25_category"] == "Excellent"

    def test_worst_parameter_wins(self):
        # CO2 is Poor, everything else is Excellent
        c = _calc(in_temp=22.0, in_rh=50.0, in_co2=1600.0, in_pm25=10.0)
        result = c.get_air_quality()
        assert result["level"] == "Poor"
        assert result["worst_parameter"] == "CO2"

    def test_pm25_drives_unhealthy(self):
        c = _calc(in_temp=22.0, in_rh=50.0, in_pm25=80.0)
        result = c.get_air_quality()
        assert result["level"] == "Unhealthy"
        assert result["worst_parameter"] == "PM2.5"

    def test_no_optional_sensors_returns_unavailable(self):
        # Only in_temp and in_rh available (no CO2, no PM2.5) — air quality
        # has nothing to score, so the entity should be skipped entirely.
        c = _calc(in_temp=22.0, in_rh=50.0)
        result = c.get_air_quality()
        assert result["available"] is False
        assert result["co2_category"] is None
        assert result["pm25_category"] is None

    def test_co2_thresholds(self):
        assert _calc(in_co2=800.0).get_air_quality()["co2_category"] == "Excellent"
        assert _calc(in_co2=801.0).get_air_quality()["co2_category"] == "Good"
        assert _calc(in_co2=1001.0).get_air_quality()["co2_category"] == "Moderate"
        assert _calc(in_co2=1401.0).get_air_quality()["co2_category"] == "Poor"
        assert _calc(in_co2=2001.0).get_air_quality()["co2_category"] == "Unhealthy"

    def test_pm25_thresholds(self):
        assert _calc(in_pm25=15.0).get_air_quality()["pm25_category"] == "Excellent"
        assert _calc(in_pm25=16.0).get_air_quality()["pm25_category"] == "Good"
        assert _calc(in_pm25=26.0).get_air_quality()["pm25_category"] == "Moderate"
        assert _calc(in_pm25=38.0).get_air_quality()["pm25_category"] == "Poor"
        assert _calc(in_pm25=76.0).get_air_quality()["pm25_category"] == "Unhealthy"


class TestGetComfort:
    """get_comfort() covers indoor temperature and humidity only."""

    def test_excellent_all_parameters(self):
        c = _calc(in_temp=22.0, in_rh=50.0)
        result = c.get_comfort()
        assert result["level"] == "Excellent"
        assert result["humidity_category"] == "Excellent"
        assert result["temperature_category"] == "Excellent"

    def test_humidity_too_low_is_poor(self):
        c = _calc(in_temp=22.0, in_rh=22.0)
        result = c.get_comfort()
        assert result["humidity_category"] == "Poor"

    def test_humidity_too_high_is_moderate(self):
        c = _calc(in_temp=22.0, in_rh=68.0)
        result = c.get_comfort()
        assert result["humidity_category"] == "Moderate"

    def test_temperature_too_hot_is_moderate(self):
        c = _calc(in_temp=28.5, in_rh=50.0)
        result = c.get_comfort()
        assert result["temperature_category"] == "Moderate"

    def test_temperature_too_cold_is_moderate(self):
        # Temperature is capped at "Moderate" by design — it never
        # contributes "Poor"/"Unhealthy" to the comfort score.
        c = _calc(in_temp=15.0, in_rh=50.0)
        result = c.get_comfort()
        assert result["temperature_category"] == "Moderate"


class TestGetVentilationReason:
    def test_storm_warning_is_top_priority(self):
        # Storm overrides even dangerously high CO2
        c = _calc(wind_avg=12.0, wind_max=18.0, in_co2=1500.0)
        assert c.get_ventilation_reason() == "Storm warning"

    def test_condensation_risk(self):
        # out_dew >= in_temp - 2 triggers condensation risk
        c = _calc(in_temp=18.0, out_dew=17.0)
        assert c.get_ventilation_reason() == "Condensation risk"

    def test_outdoor_pm25_too_high(self):
        c = _calc(out_pm25=105.0)
        assert c.get_ventilation_reason() == "Outdoor PM2.5 too high"

    def test_outdoor_air_too_hot(self):
        c = _calc(out_temp=28.0)
        assert c.get_ventilation_reason() == "Outdoor air too hot"

    def test_outdoor_humidity_too_high(self):
        # Dry inside (hum_diff clearly below the -1.0 "cooling favorable"
        # band) and not hot outside, so no positive reason fires first
        c = _calc(in_temp=21.0, in_rh=40.0, out_temp=20.0, out_hum_abs=10.0, out_rh=85.0)
        assert c.get_ventilation_reason() == "Outdoor humidity too high"

    def test_outdoor_air_too_cold(self):
        # temp_diff > 7 and out_temp_max < 20; minimal hum_diff so no positive reason fires
        c = _calc(in_temp=24.0, in_rh=44.0, out_temp=15.0, out_hum_abs=9.5, out_temp_max=18.0)
        assert c.get_ventilation_reason() == "Outdoor air too cold"

    def test_dangerously_high_co2(self):
        c = _calc(in_co2=1500.0)
        assert c.get_ventilation_reason() == "Dangerously high CO2"

    def test_high_co2_level(self):
        c = _calc(in_co2=1300.0)
        assert c.get_ventilation_reason() == "High CO2 level"

    def test_elevated_co2(self):
        c = _calc(in_co2=900.0)
        assert c.get_ventilation_reason() == "Elevated CO2"

    def test_high_indoor_humidity(self):
        # in_rh=70% at 22°C → in_hum_abs ≈ 14.6 g/m³; out_hum_abs=5.0 → diff ≈ 9.6 > 1.5
        c = _calc(in_temp=22.0, in_rh=70.0, out_hum_abs=5.0)
        assert c.get_ventilation_reason() == "High indoor humidity"

    def test_indoor_too_warm(self):
        # in_temp=27, in_rh=45% → in_hum_abs ≈ 12.6; out_hum_abs=11.5 → diff ≈ 1.1 ≤ 1.5
        # out_temp=20, so out_temp < in_temp - 3 (27-3=24 > 20) → cooling condition met
        c = _calc(in_temp=27.0, in_rh=45.0, out_temp=20.0, out_hum_abs=11.5)
        assert c.get_ventilation_reason() == "Indoor too warm"

    def test_good_ventilation_conditions(self):
        # in_rh=54 (below >=55 threshold so High indoor humidity doesn't fire), hum_diff ≈ 2.6 > 0.5
        # in_hum_abs at 21°C, 54% ≈ 10.6; out_hum_abs=8.0 → diff ≈ 2.6
        c = _calc(in_temp=21.0, in_rh=54.0, out_temp=15.0, out_hum_abs=8.0)
        assert c.get_ventilation_reason() == "Good ventilation conditions"

    def test_good_air_quality_fallback(self):
        # hum_diff clearly negative (< -1.0): out_hum_abs >> in_hum_abs, no cooling either
        # in_hum_abs at 21°C, 40% ≈ 7.9; out_hum_abs=10.0 → diff = -2.1
        c = _calc(in_temp=21.0, in_rh=40.0, out_hum_abs=10.0, out_temp=20.0)
        assert c.get_ventilation_reason() == "Good air quality"

    def test_cooling_conditions_favorable(self):
        # hum_diff in [-1.0, 0] and outdoor meaningfully cooler: should return cooling reason
        # in_hum_abs at 21°C, 50% ≈ 9.2; out_hum_abs=9.7 → diff ≈ -0.5 (near-neutral)
        c = _calc(in_temp=21.0, in_rh=50.0, out_temp=17.0, out_hum_abs=9.7)
        assert c.get_ventilation_reason() == "Cooling conditions favorable"

    def test_near_neutral_humidity_can_reach_recommended(self):
        # hum_diff ≈ -0.44 (inside the >= -0.5 "near-neutral" bucket) + wind
        # + cooling should give ≥ 60
        c = _calc(in_temp=21.0, in_rh=50.0, out_temp=17.0, out_hum_abs=9.6,
                  wind_avg=3.0, wind_max=7.0)
        assert c.calculate() >= 60

    def test_base_humidity_score_cliff_at_minus_half(self):
        # Pins the exact -0.5 bucket boundary so a rounding drift in future
        # changes can't silently fall into the wrong bucket again.
        just_inside = _calc(in_temp=21.0, in_rh=50.0, out_hum_abs=9.6)  # hum_diff ≈ -0.44
        just_outside = _calc(in_temp=21.0, in_rh=50.0, out_hum_abs=9.7)  # hum_diff ≈ -0.54
        assert just_inside._base_humidity_score(-0.44) == 30
        assert just_outside._base_humidity_score(-0.54) == 10

    def test_conditions_balanced(self):
        # hum_diff between 0 and 0.5
        # in_hum_abs at 21°C, 43% = 7.88; out_hum_abs=7.58 → diff ≈ 0.3
        c = _calc(in_temp=21.0, in_rh=43.0, out_hum_abs=7.58)
        assert c.get_ventilation_reason() == "Conditions balanced"


class TestWeatherSignals:
    def test_weather_block_is_top_priority_after_storm(self):
        # Even with excellent humidity removal potential, adverse weather wins
        c = _calc(in_temp=22.0, in_rh=65.0, out_hum_abs=3.0, weather_block=True)
        assert c.get_ventilation_reason() == "Adverse weather"

    def test_storm_outranks_weather_block(self):
        c = _calc(wind_avg=12.0, wind_max=18.0, weather_block=True)
        assert c.get_ventilation_reason() == "Storm warning"

    def test_weather_block_caps_score_low(self):
        # Would otherwise score very high (large hum_diff, high in_rh)
        c = _calc(in_temp=22.0, in_rh=65.0, out_hum_abs=3.0, weather_block=True)
        assert c.calculate() <= 15

    def test_weather_caution_reduces_score(self):
        c_clear = _calc(in_temp=21.0, in_rh=50.0, out_temp=15.0, out_hum_abs=7.0)
        c_caution = _calc(in_temp=21.0, in_rh=50.0, out_temp=15.0, out_hum_abs=7.0, weather_caution=True)
        assert c_caution.calculate() == c_clear.calculate() - 15

    def test_weather_caution_is_soft_warning_after_positive_reasons(self):
        # A clear positive reason (high indoor humidity) still wins over the
        # soft weather_caution warning, which only fires as a fallback.
        c = _calc(in_temp=22.0, in_rh=65.0, out_hum_abs=3.0, weather_caution=True)
        assert c.get_ventilation_reason() == "High indoor humidity"

    def test_weather_caution_fires_as_fallback_when_no_positive_reason(self):
        # Dry inside, no positive reason, weather caution should surface
        # before the generic "Good air quality" fallback
        c = _calc(in_temp=21.0, in_rh=40.0, out_temp=20.0, out_hum_abs=10.0, weather_caution=True)
        assert c.get_ventilation_reason() == "Weather conditions deteriorating soon"

    def test_get_action_signals_shape(self):
        c = _calc(in_co2=1500.0, weather_block=True)
        signals = c.get_action_signals()
        assert signals["co2_override"] is True
        assert signals["weather_block"] is True
        assert signals["weather_caution"] is False
        assert signals["storm"] is False
        assert "efficiency" in signals and "advice" in signals
