# Air Quality Sensor, Ventilation Reason Sensor & Outdoor PM2.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new per-area sensor entities (Air Quality, Ventilation Reason) and a global outdoor PM2.5 sensor to the Smart Ventilation integration.

**Architecture:** All calculation logic lives in `calculator.py` (pure Python, no HA imports) via two new methods: `get_air_quality()` and `get_ventilation_reason()`. The coordinator reads the outdoor PM2.5 sensor and passes its value to every `VentilationCalculator` instance. Two new `CoordinatorEntity` subclasses in `sensor.py` expose the results to HA.

**Tech Stack:** Python 3.12, Home Assistant 2024.x+, pytest (no HA fixtures needed for calculator tests)

---

## File Map

| File | Change |
|---|---|
| `custom_components/smart_ventilation/const.py` | Add `CONF_OUTDOOR_PM25`, `AIR_QUALITY_LEVELS` |
| `custom_components/smart_ventilation/calculator.py` | Add `get_air_quality()`, `get_ventilation_reason()`, 4 private category helpers |
| `custom_components/smart_ventilation/coordinator.py` | Read outdoor PM2.5; add `air_quality`, `air_quality_attributes`, `ventilation_reason` to area data |
| `custom_components/smart_ventilation/config_flow.py` | Add optional `CONF_OUTDOOR_PM25` field to outdoor sensor step |
| `custom_components/smart_ventilation/sensor.py` | Add `AirQualitySensor`, `VentilationReasonSensor`; register them in `async_setup_entry` |
| `custom_components/smart_ventilation/strings.json` | Add outdoor PM2.5 label + new sensor names |
| `custom_components/smart_ventilation/translations/en.json` | Mirror strings.json |
| `tests/test_calculator.py` | New file — pure pytest tests for calculator methods |

---

## Task 1: Add constants and test scaffold

**Files:**
- Modify: `custom_components/smart_ventilation/const.py`
- Create: `tests/__init__.py`
- Create: `tests/test_calculator.py`

- [ ] **Step 1: Add `CONF_OUTDOOR_PM25` and `AIR_QUALITY_LEVELS` to const.py**

Open `custom_components/smart_ventilation/const.py` and add after the existing `CONF_WIND_MAX` line:

```python
CONF_OUTDOOR_PM25 = "outdoor_pm25"
```

And after `VENTILATION_ADVICE_LEVELS`:

```python
AIR_QUALITY_LEVELS = ["Excellent", "Good", "Moderate", "Poor", "Unhealthy"]
```

Final `const.py`:

```python
"""Constants for Smart Ventilation integration."""

DOMAIN = "smart_ventilation"

CONF_AREAS = "areas"
CONF_AREA_NAME = "name"
CONF_INDOOR_TEMP = "indoor_temperature"
CONF_INDOOR_HUMIDITY = "indoor_humidity"
CONF_INDOOR_ABS_HUMIDITY = "indoor_absolute_humidity"
CONF_INDOOR_DEW_POINT = "indoor_dew_point"
CONF_INDOOR_HEAT_INDEX = "indoor_heat_index"
CONF_INDOOR_CO2 = "indoor_co2"
CONF_INDOOR_PM25 = "indoor_pm25"

CONF_OUTDOOR_TEMP = "outdoor_temperature"
CONF_OUTDOOR_HUMIDITY = "outdoor_humidity"
CONF_OUTDOOR_ABS_HUMIDITY = "outdoor_absolute_humidity"
CONF_OUTDOOR_DEW_POINT = "outdoor_dew_point"
CONF_OUTDOOR_TEMP_MAX_24H = "outdoor_temperature_max_24h"
CONF_WIND_AVG = "wind_average"
CONF_WIND_MAX = "wind_max"
CONF_OUTDOOR_PM25 = "outdoor_pm25"

VENTILATION_ADVICE_LEVELS = ["Optimal", "Recommended", "Decent", "Neutral", "Not Recommended"]
AIR_QUALITY_LEVELS = ["Excellent", "Good", "Moderate", "Poor", "Unhealthy"]
```

- [ ] **Step 2: Create test package**

Create `tests/__init__.py` (empty file).

- [ ] **Step 3: Create failing test skeleton**

Create `tests/test_calculator.py`:

```python
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
```

- [ ] **Step 4: Verify test fails as expected**

Run: `cd /home/demi/ai/smart-ventilation && python -m pytest tests/test_calculator.py -v 2>&1 | head -30`

Expected: FAILED with `AssertionError: replace with real tests in Task 2`

- [ ] **Step 5: Commit**

```bash
git add custom_components/smart_ventilation/const.py tests/__init__.py tests/test_calculator.py
git commit -m "feat: add CONF_OUTDOOR_PM25 + AIR_QUALITY_LEVELS constants, test scaffold"
```

---

## Task 2: Implement `get_air_quality()` in calculator.py

**Files:**
- Modify: `custom_components/smart_ventilation/calculator.py`
- Modify: `tests/test_calculator.py`

- [ ] **Step 1: Replace placeholder test with real failing tests**

Replace the entire `TestGetAirQuality` class in `tests/test_calculator.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd /home/demi/ai/smart-ventilation && python -m pytest tests/test_calculator.py::TestGetAirQuality -v 2>&1 | head -40`

Expected: FAILED with `AttributeError: 'VentilationCalculator' object has no attribute 'get_air_quality'`

- [ ] **Step 3: Add 4 category helper functions and `get_air_quality()` to calculator.py**

Add after the `get_advice()` function (before the `VentilationCalculator` class) in `calculator.py`:

```python
def _co2_category(co2: float) -> int:
    """Return 0=Excellent … 4=Unhealthy for a CO2 value in ppm."""
    if co2 <= 800:
        return 0
    if co2 <= 1000:
        return 1
    if co2 <= 1400:
        return 2
    if co2 <= 2000:
        return 3
    return 4


def _pm25_category(pm25: float) -> int:
    """Return 0=Excellent … 4=Unhealthy for a PM2.5 value in µg/m³ (WHO 2021)."""
    if pm25 <= 15:
        return 0
    if pm25 <= 25:
        return 1
    if pm25 <= 37:
        return 2
    if pm25 <= 75:
        return 3
    return 4


def _humidity_category(rh: float) -> int:
    """Return 0=Excellent … 4=Unhealthy for indoor relative humidity %."""
    if 40 <= rh <= 60:
        return 0
    if (30 <= rh < 40) or (60 < rh <= 65):
        return 1
    if (25 <= rh < 30) or (65 < rh <= 70):
        return 2
    if (20 <= rh < 25) or (70 < rh <= 80):
        return 3
    return 4


def _temperature_category(temp: float) -> int:
    """Return 0=Excellent … 4=Unhealthy for indoor temperature °C."""
    if 20 <= temp <= 25:
        return 0
    if (18 <= temp < 20) or (25 < temp <= 27):
        return 1
    if (16 <= temp < 18) or (27 < temp <= 29):
        return 2
    if (14 <= temp < 16) or (29 < temp <= 31):
        return 3
    return 4
```

Also add a module-level constant at the top of `calculator.py` (after the `get_advice()` function, before the category helpers):

```python
_AIR_QUALITY_LEVELS = ["Excellent", "Good", "Moderate", "Poor", "Unhealthy"]
```

Then add the `get_air_quality()` method to the `VentilationCalculator` class, after the `get_reasons()` method:

```python
    def get_air_quality(self) -> dict:
        """Return room air quality category and per-parameter breakdown.

        Uses worst-parameter-wins: the overall level equals the worst
        individual parameter. Parameters without a configured sensor are
        skipped.  Returns a dict with keys: level, co2_category,
        pm25_category, humidity_category, temperature_category,
        worst_parameter.
        """
        scores: dict[str, int] = {}
        if self.in_co2 is not None:
            scores["CO2"] = _co2_category(self.in_co2)
        if self.in_pm25 is not None:
            scores["PM2.5"] = _pm25_category(self.in_pm25)
        if self.in_rh is not None:
            scores["Humidity"] = _humidity_category(self.in_rh)
        if self.in_temp is not None:
            scores["Temperature"] = _temperature_category(self.in_temp)

        if not scores:
            return {
                "level": _AIR_QUALITY_LEVELS[0],  # "Excellent" — assume good when no sensors
                "co2_category": None,
                "pm25_category": None,
                "humidity_category": None,
                "temperature_category": None,
                "worst_parameter": None,
            }

        worst_key = max(scores, key=lambda k: scores[k])

        return {
            "level": _AIR_QUALITY_LEVELS[scores[worst_key]],
            "co2_category": _AIR_QUALITY_LEVELS[scores["CO2"]] if "CO2" in scores else None,
            "pm25_category": _AIR_QUALITY_LEVELS[scores["PM2.5"]] if "PM2.5" in scores else None,
            "humidity_category": _AIR_QUALITY_LEVELS[scores["Humidity"]] if "Humidity" in scores else None,
            "temperature_category": _AIR_QUALITY_LEVELS[scores["Temperature"]] if "Temperature" in scores else None,
            "worst_parameter": worst_key,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/demi/ai/smart-ventilation && python -m pytest tests/test_calculator.py::TestGetAirQuality -v 2>&1`

Expected: All tests PASSED

- [ ] **Step 5: Commit**

```bash
git add custom_components/smart_ventilation/calculator.py tests/test_calculator.py
git commit -m "feat: add get_air_quality() to VentilationCalculator with WHO/EN16798 thresholds"
```

---

## Task 3: Implement `get_ventilation_reason()` in calculator.py

**Files:**
- Modify: `custom_components/smart_ventilation/calculator.py`
- Modify: `tests/test_calculator.py`

- [ ] **Step 1: Add failing tests for `get_ventilation_reason()` to test file**

Append to `tests/test_calculator.py`:

```python
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
        c = _calc(out_pm25=30.0)
        assert c.get_ventilation_reason() == "Outdoor PM2.5 too high"

    def test_outdoor_air_too_hot(self):
        c = _calc(out_temp=28.0)
        assert c.get_ventilation_reason() == "Outdoor air too hot"

    def test_outdoor_humidity_too_high(self):
        c = _calc(out_rh=85.0)
        assert c.get_ventilation_reason() == "Outdoor humidity too high"

    def test_outdoor_air_too_cold(self):
        # temp_diff > 7 and out_temp_max < 20
        c = _calc(in_temp=24.0, out_temp=15.0, out_temp_max=18.0)
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
        # hum_diff > 1.5, in_rh > 55 — use high in_hum_abs and low out_hum_abs
        c = _calc(in_temp=22.0, in_rh=70.0, out_hum_abs=5.0)
        # in_hum_abs at 22°C, 70% RH ≈ 14.6 g/m³ → diff ≈ 9.6 > 1.5
        assert c.get_ventilation_reason() == "High indoor humidity"

    def test_indoor_too_warm(self):
        # in_temp > 24, out_temp < in_temp - 3, no CO2, no high humidity
        c = _calc(in_temp=27.0, in_rh=45.0, out_temp=20.0, out_hum_abs=7.5)
        # in_hum_abs at 27°C, 45% ≈ 12.6 → diff ≈ 5.1 > 1.5 → "High indoor humidity" wins
        # Use out_hum_abs close enough so diff ≤ 1.5
        c2 = _calc(in_temp=27.0, in_rh=45.0, out_temp=20.0, out_hum_abs=11.5)
        assert c2.get_ventilation_reason() == "Indoor too warm"

    def test_good_ventilation_conditions(self):
        # Small positive hum_diff, no strong driver
        c = _calc(in_temp=21.0, in_rh=55.0, out_temp=15.0, out_hum_abs=8.0)
        # in_hum_abs at 21°C, 55% ≈ 10.8 → diff ≈ 2.8 > 0.5 but check in_rh > 55 for humidity
        # in_rh=55 → not > 55 so not "High indoor humidity"
        assert c.get_ventilation_reason() == "Good ventilation conditions"

    def test_good_air_quality_fallback(self):
        # hum_diff ≤ 0 (outdoor more humid than indoor)
        c = _calc(in_temp=21.0, in_rh=40.0, out_hum_abs=10.0)
        # in_hum_abs at 21°C, 40% ≈ 7.9 → diff = 7.9 - 10 = -2.1 ≤ 0
        assert c.get_ventilation_reason() == "Good air quality"

    def test_conditions_balanced(self):
        # hum_diff between 0 and 0.5
        c = _calc(in_temp=21.0, in_rh=43.0, out_hum_abs=8.2)
        # in_hum_abs at 21°C, 43% ≈ 8.5 → diff ≈ 0.3 — between 0 and 0.5
        assert c.get_ventilation_reason() == "Conditions balanced"
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd /home/demi/ai/smart-ventilation && python -m pytest tests/test_calculator.py::TestGetVentilationReason -v 2>&1 | head -30`

Expected: FAILED with `AttributeError: 'VentilationCalculator' object has no attribute 'get_ventilation_reason'`

- [ ] **Step 3: Add `get_ventilation_reason()` to calculator.py**

Add after the `get_air_quality()` method in `VentilationCalculator`:

```python
    def get_ventilation_reason(self) -> str:
        """Return the primary reason to ventilate or avoid ventilating.

        Negative reasons are checked first (safety > weather > air quality).
        Positive reasons follow (CO2 > humidity > temperature > general).
        """
        # --- Negative reasons ---
        if self._storm_penalty() < 0:
            return "Storm warning"

        if (
            self.out_dew is not None
            and self.in_temp is not None
            and self.out_dew >= self.in_temp - 2
        ):
            return "Condensation risk"

        if self.out_pm25 is not None and self.out_pm25 > 25:
            return "Outdoor PM2.5 too high"

        if self.out_temp is not None and self.out_temp > 27:
            return "Outdoor air too hot"

        if self.out_rh is not None and self.out_rh > 80:
            return "Outdoor humidity too high"

        temp_diff = (
            self.in_temp - self.out_temp
            if self.in_temp is not None and self.out_temp is not None
            else None
        )
        if (
            self.out_temp_max is not None
            and self.out_temp_max < 20
            and temp_diff is not None
            and temp_diff > 7
        ):
            return "Outdoor air too cold"

        # --- Positive reasons ---
        if self.in_co2 is not None:
            if self.in_co2 > 1400:
                return "Dangerously high CO2"
            if self.in_co2 > 1200:
                return "High CO2 level"
            if self.in_co2 > 800:
                return "Elevated CO2"

        hum_diff = (
            self.in_hum_abs - self.out_hum_abs
            if self.in_hum_abs is not None and self.out_hum_abs is not None
            else None
        )
        if (
            hum_diff is not None
            and hum_diff > 1.5
            and self.in_rh is not None
            and self.in_rh > 55
        ):
            return "High indoor humidity"

        if (
            self.in_temp is not None
            and self.out_temp is not None
            and self.in_temp > 24
            and self.out_temp < self.in_temp - 3
        ):
            return "Indoor too warm"

        if hum_diff is not None and hum_diff > 0.5:
            return "Good ventilation conditions"

        if hum_diff is not None and 0 < hum_diff <= 0.5:
            return "Conditions balanced"

        return "Good air quality"
```

- [ ] **Step 4: Run all tests**

Run: `cd /home/demi/ai/smart-ventilation && python -m pytest tests/test_calculator.py -v 2>&1`

Expected: All tests PASSED. If a test fails due to unexpected hum_diff value, adjust that test's `out_hum_abs` to produce the expected diff (use `calculate_absolute_humidity(in_temp, in_rh)` mentally or via Python REPL: `python3 -c "from custom_components.smart_ventilation.calculator import calculate_absolute_humidity; print(calculate_absolute_humidity(21, 43))"`)

- [ ] **Step 5: Commit**

```bash
git add custom_components/smart_ventilation/calculator.py tests/test_calculator.py
git commit -m "feat: add get_ventilation_reason() to VentilationCalculator"
```

---

## Task 4: Add outdoor PM2.5 to config_flow and coordinator

**Files:**
- Modify: `custom_components/smart_ventilation/config_flow.py`
- Modify: `custom_components/smart_ventilation/coordinator.py`

- [ ] **Step 1: Add `CONF_OUTDOOR_PM25` import to config_flow.py**

In `config_flow.py`, add `CONF_OUTDOOR_PM25` to the import from `.const`:

```python
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
```

- [ ] **Step 2: Add outdoor PM2.5 field to the config flow schema in `async_step_user`**

In `async_step_user`, add after the `CONF_WIND_MAX` field inside the `vol.Schema(...)`:

```python
                    vol.Optional(CONF_OUTDOOR_PM25): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
```

The full schema block becomes:

```python
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OUTDOOR_TEMP): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="temperature"
                        ),
                    ),
                    vol.Optional(CONF_OUTDOOR_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="humidity"
                        ),
                    ),
                    vol.Optional(CONF_OUTDOOR_ABS_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_DEW_POINT): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_TEMP_MAX_24H): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_WIND_AVG): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_WIND_MAX): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_PM25): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                }
            ),
        )
```

- [ ] **Step 3: Add `CONF_OUTDOOR_PM25` import to coordinator.py**

In `coordinator.py`, add `CONF_OUTDOOR_PM25` to the import from `.const`:

```python
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
```

- [ ] **Step 4: Read outdoor PM2.5 in `_get_outdoor_data()`**

In `_get_outdoor_data()`, add `outdoor_pm25` to the returned dict:

```python
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
```

- [ ] **Step 5: Pass `out_pm25` to `VentilationCalculator` in `_get_area_data()`**

In `_get_area_data()`, add `out_pm25=outdoor["outdoor_pm25"],` to the `VentilationCalculator(...)` constructor call:

```python
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
```

- [ ] **Step 6: Run tests to verify nothing broke**

Run: `cd /home/demi/ai/smart-ventilation && python -m pytest tests/ -v 2>&1`

Expected: All PASSED

- [ ] **Step 7: Commit**

```bash
git add custom_components/smart_ventilation/config_flow.py custom_components/smart_ventilation/coordinator.py
git commit -m "feat: add outdoor PM2.5 sensor to config flow and coordinator"
```

---

## Task 5: Wire air_quality and ventilation_reason through coordinator

**Files:**
- Modify: `custom_components/smart_ventilation/coordinator.py`

- [ ] **Step 1: Import `get_air_quality` and `get_ventilation_reason` usage**

These are methods on the `VentilationCalculator` instance, so no new imports are needed. Just add two calls after `efficiency = calc.calculate()` in `_get_area_data()`.

- [ ] **Step 2: Add air_quality and ventilation_reason to the returned dict**

Update the `return` statement in `_get_area_data()` to include the new keys:

```python
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
```

- [ ] **Step 3: Run tests**

Run: `cd /home/demi/ai/smart-ventilation && python -m pytest tests/ -v 2>&1`

Expected: All PASSED

- [ ] **Step 4: Commit**

```bash
git add custom_components/smart_ventilation/coordinator.py
git commit -m "feat: add air_quality and ventilation_reason to coordinator area data"
```

---

## Task 6: Add AirQualitySensor and VentilationReasonSensor entities

**Files:**
- Modify: `custom_components/smart_ventilation/sensor.py`

- [ ] **Step 1: Add `AIR_QUALITY_LEVELS` to the import from const in sensor.py**

Update the import line in `sensor.py`:

```python
from .const import AIR_QUALITY_LEVELS, DOMAIN, VENTILATION_ADVICE_LEVELS
```

- [ ] **Step 2: Add `AirQualitySensor` class**

Append to `sensor.py` after `TemperatureDifferenceSensor`:

```python
class AirQualitySensor(_AreaSensor):
    """Indoor air quality category based on CO2, PM2.5, humidity and temperature."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = AIR_QUALITY_LEVELS
    _attr_translation_key = "air_quality"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
        area_id: str | None = None,
    ) -> None:
        super().__init__(coordinator, entry, area_name, area_id)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_air_quality"

    @property
    def icon(self) -> str:
        value = self._attr_native_value
        if value == "Excellent":
            return "mdi:air-filter"
        if value == "Good":
            return "mdi:air-purifier"
        if value == "Moderate":
            return "mdi:cloud-alert"
        return "mdi:biohazard"

    def _update_from_data(self, data: dict) -> None:
        self._attr_native_value = data.get("air_quality", "Good")
        attrs = data.get("air_quality_attributes", {})
        self._attr_extra_state_attributes = {
            "co2_category": attrs.get("co2_category"),
            "pm25_category": attrs.get("pm25_category"),
            "humidity_category": attrs.get("humidity_category"),
            "temperature_category": attrs.get("temperature_category"),
            "worst_parameter": attrs.get("worst_parameter"),
        }
```

- [ ] **Step 3: Add `VentilationReasonSensor` class**

Append to `sensor.py` after `AirQualitySensor`:

```python
class VentilationReasonSensor(_AreaSensor):
    """Primary reason to ventilate or avoid ventilating."""

    _attr_icon = "mdi:chat-question"
    _attr_translation_key = "ventilation_reason"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
        area_id: str | None = None,
    ) -> None:
        super().__init__(coordinator, entry, area_name, area_id)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_ventilation_reason"

    def _update_from_data(self, data: dict) -> None:
        self._attr_native_value = data.get("ventilation_reason", "Good air quality")
```

- [ ] **Step 4: Register both new entities in `async_setup_entry`**

Update the `entities.extend([...])` block in `async_setup_entry` to include the two new sensors:

```python
        entities.extend(
            [
                VentilationEfficiencySensor(coordinator, entry, area_name, area_id),
                VentilationAdviceSensor(coordinator, entry, area_name, area_id),
                HumidityDifferenceSensor(coordinator, entry, area_name, area_id),
                TemperatureDifferenceSensor(coordinator, entry, area_name, area_id),
                AirQualitySensor(coordinator, entry, area_name, area_id),
                VentilationReasonSensor(coordinator, entry, area_name, area_id),
            ]
        )
```

- [ ] **Step 5: Run tests**

Run: `cd /home/demi/ai/smart-ventilation && python -m pytest tests/ -v 2>&1`

Expected: All PASSED

- [ ] **Step 6: Commit**

```bash
git add custom_components/smart_ventilation/sensor.py
git commit -m "feat: add AirQualitySensor and VentilationReasonSensor entities"
```

---

## Task 7: Update strings, translations, and verify version

**Files:**
- Modify: `custom_components/smart_ventilation/strings.json`
- Modify: `custom_components/smart_ventilation/translations/en.json`
- Verify: `custom_components/smart_ventilation/manifest.json`

- [ ] **Step 1: Update strings.json**

Add the outdoor PM2.5 label in the `config.step.user.data` section and the two new sensor names in `entity.sensor`. The complete updated file:

```json
{
  "config": {
    "title": "Smart Ventilation",
    "step": {
      "user": {
        "title": "Outdoor Sensors",
        "description": "Configure the global outdoor sensors used for all areas. Absolute humidity and dew point are calculated automatically if you provide relative humidity.",
        "data": {
          "outdoor_temperature": "Outdoor Temperature",
          "outdoor_humidity": "Outdoor Relative Humidity",
          "outdoor_absolute_humidity": "Outdoor Absolute Humidity (optional, calculated if omitted)",
          "outdoor_dew_point": "Outdoor Dew Point (optional, calculated if omitted)",
          "outdoor_temperature_max_24h": "Outdoor Max Temperature 24h (optional)",
          "wind_average": "Wind Average (optional)",
          "wind_max": "Wind Maximum (optional)",
          "outdoor_pm25": "Outdoor PM2.5 (optional)"
        }
      }
    }
  },
  "options": {
    "title": "Smart Ventilation",
    "step": {
      "init": {
        "title": "Manage Areas"
      },
      "menu": {
        "title": "Manage Areas",
        "data": {
          "action": "Action"
        }
      },
      "add_area": {
        "title": "Add Area",
        "description": "Configure sensors for a new area. Absolute humidity, dew point and heat index are calculated automatically from temperature and humidity.",
        "data": {
          "name": "Area",
          "indoor_temperature": "Indoor Temperature",
          "indoor_humidity": "Indoor Humidity",
          "indoor_co2": "Indoor CO2 (optional)",
          "indoor_pm25": "Indoor PM2.5 (optional)"
        }
      },
      "edit_area_select": {
        "title": "Edit Area",
        "data": {
          "area_to_edit": "Select Area to Edit"
        }
      },
      "edit_area": {
        "title": "Edit Area",
        "description": "Update the sensors for this area.",
        "data": {
          "name": "Area",
          "indoor_temperature": "Indoor Temperature",
          "indoor_humidity": "Indoor Humidity",
          "indoor_co2": "Indoor CO2 (optional)",
          "indoor_pm25": "Indoor PM2.5 (optional)"
        }
      },
      "remove_area": {
        "title": "Remove Area",
        "data": {
          "area_to_remove": "Select Area to Remove"
        }
      }
    }
  },
  "entity": {
    "sensor": {
      "ventilation_efficiency": {
        "name": "Ventilation Efficiency"
      },
      "ventilation_advice": {
        "name": "Ventilation Advice",
        "state": {
          "Optimal": "Optimal",
          "Recommended": "Recommended",
          "Decent": "Decent",
          "Neutral": "Neutral",
          "Not Recommended": "Not Recommended"
        }
      },
      "humidity_difference": {
        "name": "Humidity Difference"
      },
      "temperature_difference": {
        "name": "Temperature Difference"
      },
      "air_quality": {
        "name": "Air Quality",
        "state": {
          "Excellent": "Excellent",
          "Good": "Good",
          "Moderate": "Moderate",
          "Poor": "Poor",
          "Unhealthy": "Unhealthy"
        }
      },
      "ventilation_reason": {
        "name": "Ventilation Reason"
      }
    },
    "binary_sensor": {
      "cooling_recommended": {
        "name": "Cooling by Ventilation Recommended"
      }
    }
  }
}
```

- [ ] **Step 2: Mirror strings.json to translations/en.json**

Run: `cp custom_components/smart_ventilation/strings.json custom_components/smart_ventilation/translations/en.json`

- [ ] **Step 3: Verify manifest.json version is 1.2.0**

Run: `grep version custom_components/smart_ventilation/manifest.json`

Expected output: `"version": "1.2.0"` — if it shows a lower version, update it to `"1.2.0"`.

- [ ] **Step 4: Run all tests one final time**

Run: `cd /home/demi/ai/smart-ventilation && python -m pytest tests/ -v 2>&1`

Expected: All PASSED

- [ ] **Step 5: Commit and tag**

```bash
git add custom_components/smart_ventilation/strings.json custom_components/smart_ventilation/translations/en.json custom_components/smart_ventilation/manifest.json
git commit -m "feat: strings for outdoor PM2.5, air quality sensor, ventilation reason sensor"
git tag v1.2.0
git push origin main --tags
```
