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
    def test_placeholder(self):
        assert False, "replace with real tests in Task 2"
