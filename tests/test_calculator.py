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
    def test_excellent_all_parameters(self):
        c = _calc(in_temp=22.0, in_rh=50.0, in_co2=700.0, in_pm25=10.0)
        result = c.get_air_quality()
        assert result["level"] == "Excellent"
        assert result["co2_category"] == "Excellent"
        assert result["pm25_category"] == "Excellent"
        assert result["humidity_category"] == "Excellent"
        assert result["temperature_category"] == "Excellent"

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

    def test_humidity_too_low_is_poor(self):
        c = _calc(in_temp=22.0, in_rh=22.0)
        result = c.get_air_quality()
        assert result["humidity_category"] == "Poor"

    def test_humidity_too_high_is_moderate(self):
        c = _calc(in_temp=22.0, in_rh=68.0)
        result = c.get_air_quality()
        assert result["humidity_category"] == "Moderate"

    def test_temperature_too_hot_is_moderate(self):
        c = _calc(in_temp=28.5, in_rh=50.0)
        result = c.get_air_quality()
        assert result["temperature_category"] == "Moderate"

    def test_temperature_too_cold_is_poor(self):
        c = _calc(in_temp=15.0, in_rh=50.0)
        result = c.get_air_quality()
        assert result["temperature_category"] == "Poor"

    def test_no_optional_sensors_returns_level_from_available(self):
        # Only in_temp and in_rh available (no CO2, no PM2.5) — excellent temp+humidity
        c = _calc(in_temp=22.0, in_rh=50.0)
        result = c.get_air_quality()
        assert result["level"] == "Excellent"
        assert result["co2_category"] is None
        assert result["pm25_category"] is None
        assert result["humidity_category"] == "Excellent"
        assert result["temperature_category"] == "Excellent"

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
