# Smart Ventilation Full Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `smart_ventilation` HA custom component for full compatibility with HA 2024.x+ and correct ventilation calculation logic.

**Architecture:** Pure-Python `calculator.py` handles all math with no HA imports. `coordinator.py` reads HA sensor states and feeds them to the calculator. All entity classes use `CoordinatorEntity` for correct availability handling. `config_flow.py` uses modern HA 2024.x+ API patterns (`ConfigFlowResult`, `OptionsFlow` without `config_entry` in `__init__`).

**Tech Stack:** Python 3.12, Home Assistant 2024.x+, `voluptuous` for config schemas, `homeassistant.helpers.update_coordinator.CoordinatorEntity`.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `custom_components/smart_ventilation/manifest.json` | Rewrite | Version, integration type |
| `custom_components/smart_ventilation/const.py` | Rewrite | String constants only — no functions, no classes |
| `custom_components/smart_ventilation/calculator.py` | **Create** | Pure Python: math helpers + VentilationCalculator |
| `custom_components/smart_ventilation/coordinator.py` | Rewrite | HA coordinator: reads states, calls calculator |
| `custom_components/smart_ventilation/__init__.py` | Rewrite | Entry setup/teardown |
| `custom_components/smart_ventilation/config_flow.py` | Rewrite | Modern ConfigFlow + OptionsFlow |
| `custom_components/smart_ventilation/sensor.py` | Rewrite | Sensors via CoordinatorEntity |
| `custom_components/smart_ventilation/binary_sensor.py` | Rewrite | Binary sensor via CoordinatorEntity |
| `custom_components/smart_ventilation/strings.json` | **Create** | HA i18n source (required by HA) |
| `custom_components/smart_ventilation/translations/en.json` | Rewrite | English translations |

---

### Task 1: manifest.json and const.py

**Files:**
- Rewrite: `custom_components/smart_ventilation/manifest.json`
- Rewrite: `custom_components/smart_ventilation/const.py`

- [ ] **Step 1: Rewrite manifest.json**

```json
{
  "domain": "smart_ventilation",
  "name": "Smart Ventilation",
  "codeowners": ["@dpasman"],
  "config_flow": true,
  "documentation": "https://github.com/dpasman/smart-ventilation",
  "integration_type": "service",
  "issue_tracker": "https://github.com/dpasman/smart-ventilation/issues",
  "requirements": [],
  "version": "1.0.0",
  "iot_class": "calculated"
}
```

`integration_type` changes from `"device"` to `"service"` — this integration calculates data, it is not a physical device.

- [ ] **Step 2: Rewrite const.py — constants only**

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

VENTILATION_ADVICE_LEVELS = ["Optimal", "Recommended", "Decent", "Neutral", "Not Recommended"]
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/smart_ventilation/manifest.json custom_components/smart_ventilation/const.py
git commit -m "refactor: rewrite manifest.json and const.py (constants only)"
```

---

### Task 2: calculator.py (new file)

**Files:**
- Create: `custom_components/smart_ventilation/calculator.py`

This file has **zero HA imports**. All scoring math lives here — standalone testable.

Key math fixes vs old code:
- `calculate_absolute_humidity`: was `6.112 * X * e^X`, must be `6.112 * e^X`
- `calculate_dew_point`: was `alpha = ... + rh/100`, must be `alpha = ... + math.log(rh/100)`
- New: `_score_bedroom()` — CO2-dominant scoring
- New: `_score_attic()` — temperature-only cooling logic
- New: `_base_humidity_score()` — shared humidity baseline used by generic/bathroom/bedroom
- Removed: magic -999 sentinels — all inputs are `float | None`

- [ ] **Step 1: Create calculator.py**

```python
"""Ventilation efficiency calculator — no HA imports, pure Python."""

from __future__ import annotations

import math


def calculate_absolute_humidity(temp_c: float, rh: float) -> float:
    """Calculate absolute humidity in g/m³ using the Magnus formula."""
    if temp_c <= -240 or rh <= 0 or rh > 100:
        return 0.0
    sat_vp = 6.112 * math.exp(17.67 * temp_c / (temp_c + 243.5))
    actual_vp = sat_vp * (rh / 100)
    return round((actual_vp * 2.1674) / (273.15 + temp_c), 2)


def calculate_dew_point(temp_c: float, rh: float) -> float:
    """Calculate dew point in °C using the Magnus formula."""
    if temp_c < -50 or rh <= 0 or rh > 100:
        return 0.0
    a, b = 17.27, 237.7
    alpha = (a * temp_c) / (b + temp_c) + math.log(rh / 100)
    return round((b * alpha) / (a - alpha), 1)


def calculate_heat_index(temp_c: float, rh: float) -> float:
    """Calculate heat index in °C using the Rothfusz regression."""
    if temp_c < 27:
        return temp_c
    T = temp_c * 9 / 5 + 32
    HI = (
        -42.379
        + 2.04901523 * T
        + 10.14333127 * rh
        - 0.22475541 * T * rh
        - 0.00683783 * T * T
        - 0.05481717 * rh * rh
        + 0.00122874 * T * T * rh
        + 0.00085282 * T * rh * rh
        - 0.00000199 * T * T * rh * rh
    )
    if rh < 13 and 80 < T < 112:
        HI -= ((13 - rh) / 4) * math.sqrt((17 - abs(T - 95)) / 17)
    elif rh > 85 and 80 < T < 87:
        HI += ((rh - 85) / 10) * ((87 - T) / 5)
    return round((HI - 32) * 5 / 9, 1)


def get_advice(efficiency: float) -> str:
    """Return human-readable advice string for a given efficiency (0–100)."""
    if efficiency >= 80:
        return "Optimal"
    if efficiency >= 60:
        return "Recommended"
    if efficiency >= 40:
        return "Decent"
    if efficiency >= 20:
        return "Neutral"
    return "Not Recommended"


class VentilationCalculator:
    """Calculate ventilation efficiency score (0–100) for a single area."""

    def __init__(
        self,
        in_temp: float | None,
        in_rh: float | None,
        out_temp: float | None,
        out_hum_abs: float | None,
        in_hum_abs: float | None = None,
        in_dew: float | None = None,
        out_dew: float | None = None,
        out_temp_max: float | None = None,
        in_heat_index: float | None = None,
        in_co2: float | None = None,
        in_pm25: float | None = None,
        out_pm25: float | None = None,
        wind_avg: float | None = None,
        wind_max: float | None = None,
        out_rh: float | None = None,
        room_type: str = "generic",
    ) -> None:
        self.in_temp = in_temp
        self.in_rh = in_rh
        self.out_temp = out_temp
        self.out_hum_abs = out_hum_abs
        self.out_dew = out_dew
        self.out_temp_max = out_temp_max if out_temp_max is not None else out_temp
        self.in_co2 = in_co2
        self.in_pm25 = in_pm25
        self.out_pm25 = out_pm25
        self.wind_avg = wind_avg
        self.wind_max = wind_max
        self.out_rh = out_rh
        self.room_type = room_type

        # Derive optional values when not provided
        if in_temp is not None and in_rh is not None:
            self.in_hum_abs = (
                in_hum_abs if in_hum_abs is not None
                else calculate_absolute_humidity(in_temp, in_rh)
            )
            self.in_dew = (
                in_dew if in_dew is not None
                else calculate_dew_point(in_temp, in_rh)
            )
            self.in_heat_index = (
                in_heat_index if in_heat_index is not None
                else calculate_heat_index(in_temp, in_rh)
            )
        else:
            self.in_hum_abs = in_hum_abs
            self.in_dew = in_dew
            self.in_heat_index = in_heat_index

    def _is_valid(self) -> bool:
        """Return False if required sensor data is missing or condensation risk is present."""
        if any(
            v is None
            for v in [self.in_temp, self.in_rh, self.out_temp, self.out_hum_abs, self.in_hum_abs]
        ):
            return False
        if self.out_dew is not None and self.in_temp is not None:
            if self.out_dew >= self.in_temp - 2:
                return False
        return True

    def calculate(self) -> float:
        """Return efficiency score 0–100."""
        if not self._is_valid():
            return 0.0
        hum_diff = (self.in_hum_abs or 0) - (self.out_hum_abs or 0)
        temp_diff = (self.in_temp or 0) - (self.out_temp or 0)
        if self.room_type == "kitchen":
            score = self._score_kitchen(hum_diff, temp_diff)
        elif self.room_type == "bathroom":
            score = self._score_bathroom(hum_diff, temp_diff)
        elif self.room_type == "bedroom":
            score = self._score_bedroom(hum_diff, temp_diff)
        elif self.room_type == "attic":
            score = self._score_attic()
        else:
            score = self._score_generic(hum_diff, temp_diff)
        return float(max(0, min(100, score)))

    def get_reasons(self) -> list[str]:
        """Return a list of human-readable reasons for the calculated score."""
        if not self._is_valid():
            return ["Insufficient sensor data"]
        reasons: list[str] = []
        hum_diff = (self.in_hum_abs or 0) - (self.out_hum_abs or 0)
        temp_diff = (self.in_temp or 0) - (self.out_temp or 0)

        if hum_diff > 3 and self.in_rh and self.in_rh > 60:
            reasons.append("High moisture removal potential")
        elif hum_diff > 1.5 and self.in_rh and self.in_rh > 55:
            reasons.append("Good moisture removal")
        elif hum_diff > 0.5:
            reasons.append("Moderate moisture removal")
        elif hum_diff > 0:
            reasons.append("Minimal moisture removal")
        else:
            reasons.append("No effective moisture removal")

        if self.out_temp_max is not None and self.out_temp_max < 20 and temp_diff > 5:
            reasons.append("Large temperature difference when it is cold outside")

        if self.wind_avg is not None and self.wind_max is not None:
            if 2 <= self.wind_avg <= 8 and self.wind_max < 12:
                reasons.append("Favorable wind conditions")
            else:
                reasons.append("Wind conditions not optimal")

        if self.in_temp is not None and self.in_temp > 24 and self.out_temp is not None:
            if self.out_temp < self.in_temp - 5:
                reasons.append("Outside much cooler — strong cooling potential")
            elif self.out_temp < self.in_temp - 3:
                reasons.append("Outside cooler — cooling possible")

        if self.out_temp is not None and self.out_temp > 27:
            reasons.append("Outside too hot — ventilation discouraged")

        if self.in_co2 is not None and self.in_co2 > 800:
            reasons.append(f"Elevated CO\u2082 ({int(self.in_co2)} ppm)")

        if self.room_type == "bathroom" and self.in_rh is not None and self.in_rh >= 80:
            reasons.append("Post-shower override active")

        return reasons

    # ── Shared helpers ────────────────────────────────────────────────────

    def _wind_bonus(self) -> int:
        if self.wind_avg is not None and self.wind_max is not None:
            if 2 <= self.wind_avg <= 8 and self.wind_max < 12:
                return 10
        return 0

    def _base_humidity_score(self, hum_diff: float) -> int:
        """Humidity-based starting score shared by generic, bathroom, bedroom."""
        in_rh = self.in_rh
        if hum_diff > 3 and in_rh and in_rh > 60:
            return 100
        if hum_diff > 2.5 and in_rh and in_rh > 55:
            return 90
        if hum_diff > 2 and in_rh and in_rh > 55:
            return 80
        if hum_diff > 1.5 and in_rh and in_rh > 55:
            return 70
        if hum_diff > 1.0 and in_rh and in_rh > 55:
            return 60
        if hum_diff > 0.5:
            return 40
        if hum_diff > 0:
            return 30
        return 20

    # ── Room-type scoring ─────────────────────────────────────────────────

    def _score_generic(self, hum_diff: float, temp_diff: float) -> int:
        s = self._base_humidity_score(hum_diff)
        if self.out_temp_max is not None and self.out_temp_max < 20:
            if temp_diff > 10:
                s -= 30
            elif temp_diff > 7:
                s -= 20
            elif temp_diff > 5:
                s -= 10
        s += self._wind_bonus()
        if self.in_temp is not None and self.in_temp > 24 and self.out_temp is not None:
            if self.out_temp < self.in_temp - 5:
                s += 20
            elif self.out_temp < self.in_temp - 3:
                s += 10
            if self.in_heat_index is not None:
                if self.in_heat_index > 35:
                    s += 20
                elif self.in_heat_index > 30:
                    s += 10
        if self.out_temp is not None and self.out_temp > 27:
            s -= 50
        return max(0, min(100, s))

    def _score_bathroom(self, hum_diff: float, temp_diff: float) -> int:
        s = self._base_humidity_score(hum_diff)
        if self.out_temp_max is not None and self.out_temp_max < 20:
            if temp_diff > 7:
                s -= 30
            elif temp_diff > 5:
                s -= 20
            elif temp_diff > 3:
                s -= 10
        s += self._wind_bonus()
        if self.in_temp is not None and self.in_temp > 24 and self.out_temp is not None:
            if self.out_temp < self.in_temp - 5:
                s += 20
            elif self.out_temp < self.in_temp - 3:
                s += 10
            if self.in_heat_index is not None:
                if self.in_heat_index > 35:
                    s += 20
                elif self.in_heat_index > 30:
                    s += 10
        if self.out_temp is not None and self.out_temp > 27:
            s -= 50
        if self.out_dew is not None and self.in_dew is not None:
            if self.out_dew >= self.in_dew - 0.5:
                if hum_diff > 2:
                    s -= 15
                elif hum_diff > 1:
                    s -= 25
                else:
                    s -= 35
        if self.out_rh is not None:
            if self.out_rh > 90:
                s -= 20
            elif self.out_rh > 80:
                s -= 10
        if self.in_rh is not None:
            if self.in_rh >= 80:
                s = max(s, 65)
            elif self.in_rh >= 75 and hum_diff > 0.5:
                s = max(s, 45)
        s = max(s, 20)
        return max(0, min(100, s))

    def _score_kitchen(self, hum_diff: float, temp_diff: float) -> int:
        s = 0
        in_rh = self.in_rh or 0
        if in_rh > 65:
            s += 20
        elif in_rh > 55:
            s += 10
        s += int(max(0, min(40, hum_diff * 10)))
        if self.in_co2 is not None and self.in_co2 > 0:
            if self.in_co2 > 1200:
                s += 40
            elif self.in_co2 > 800:
                s += 20
        if self.in_pm25 is not None and self.out_pm25 is not None:
            if self.out_pm25 < self.in_pm25:
                s += 10
            elif self.out_pm25 > 20:
                s -= 20
        if self.in_heat_index is not None:
            if self.in_heat_index > 35:
                s += 20
            elif self.in_heat_index > 30:
                s += 10
        s += self._wind_bonus()
        if self.in_temp is not None and self.out_temp is not None:
            if self.in_temp > 24 and self.out_temp < self.in_temp - 3:
                s += int(max(0, min(20, (temp_diff - 3) * 5)))
        if self.out_temp is not None and self.out_temp > 27:
            s -= 50
        if self.in_dew is not None and self.in_temp is not None and self.in_dew > self.in_temp - 1:
            s -= 40
        if self.out_temp_max is not None and self.out_temp_max < 20 and temp_diff > 3:
            s -= int(max(0, min(30, (temp_diff - 3) * 5)))
        return max(0, min(100, s))

    def _score_bedroom(self, hum_diff: float, temp_diff: float) -> int:
        s = 0
        # CO2 is the primary signal for bedroom ventilation
        if self.in_co2 is not None and self.in_co2 > 0:
            if self.in_co2 > 1200:
                s += 50
            elif self.in_co2 > 1000:
                s += 35
            elif self.in_co2 > 800:
                s += 20
            elif self.in_co2 > 600:
                s += 10
        # Secondary: humidity
        if hum_diff > 2 and self.in_rh is not None and self.in_rh > 60:
            s += 20
        elif hum_diff > 1:
            s += 10
        s += self._wind_bonus()
        # Cooling bonus: outside meaningfully cooler than inside
        if self.in_temp is not None and self.out_temp is not None:
            if self.out_temp < self.in_temp - 5:
                s += 25
            elif self.out_temp < self.in_temp - 3:
                s += 15
            elif self.out_temp < self.in_temp:
                s += 5
        if self.out_temp is not None and self.out_temp > 27:
            s -= 50
        if self.out_temp_max is not None and self.out_temp_max < 20:
            if temp_diff > 10:
                s -= 30
            elif temp_diff > 7:
                s -= 20
            elif temp_diff > 5:
                s -= 10
        return max(0, min(100, s))

    def _score_attic(self) -> int:
        s = 0
        if self.in_temp is not None and self.out_temp is not None:
            if self.in_temp > 30 and self.out_temp < self.in_temp - 5:
                s += 60
            elif self.in_temp > 27 and self.out_temp < self.in_temp - 3:
                s += 40
            elif self.in_temp > 24 and self.out_temp < self.in_temp:
                s += 20
        s += self._wind_bonus()
        if self.out_temp is not None and self.out_temp > 27:
            s -= 60
        return max(0, min(100, s))
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/smart_ventilation/calculator.py
git commit -m "feat: add calculator.py — corrected Magnus formulas, bedroom/attic room logic"
```

---

### Task 3: coordinator.py

**Files:**
- Rewrite: `custom_components/smart_ventilation/coordinator.py`

Key changes: `_read_state()` helper replaces repeated try/except blocks; `_get_outdoor_data()` and `_get_area_data()` are regular sync methods (they don't await anything); no -999 magic values passed to calculator.

- [ ] **Step 1: Rewrite coordinator.py**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/smart_ventilation/coordinator.py
git commit -m "refactor: rewrite coordinator.py — uses calculator.py, no magic -999 values"
```

---

### Task 4: config_flow.py

**Files:**
- Rewrite: `custom_components/smart_ventilation/config_flow.py`

Key changes that fix the 500 error:
- `FlowResult` (removed in HA 2024.x) → `ConfigFlowResult` from `homeassistant.config_entries`
- `OptionsFlowHandler` has **no `__init__`** — `self.config_entry` is provided by the base class
- `async_get_options_flow` returns `OptionsFlowHandler()` with no args

- [ ] **Step 1: Rewrite config_flow.py**

```python
"""Config flow for Smart Ventilation integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

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


class SmartVentilationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Ventilation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — outdoor sensor configuration."""
        if user_input is not None:
            return self.async_create_entry(
                title="Smart Ventilation",
                data={**user_input, "areas": []},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OUTDOOR_TEMP): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="temperature"
                        ),
                    ),
                    vol.Required(CONF_OUTDOOR_ABS_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_DEW_POINT): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_TEMP_MAX_24H): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="humidity"
                        ),
                    ),
                    vol.Optional(CONF_WIND_AVG): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_WIND_MAX): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Smart Ventilation — manage areas.

    Note: self.config_entry is set automatically by the OptionsFlow base class
    in HA 2024.x+. Do NOT define __init__ here.
    """

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Show area management menu, or go straight to add if no areas exist."""
        if not self.config_entry.data.get("areas"):
            return await self.async_step_add_area()

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="add"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="add", label="Add Area"),
                                selector.SelectOptionDict(
                                    value="remove", label="Remove Area"
                                ),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_menu(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Route menu selection to add or remove step."""
        if user_input is not None:
            if user_input.get("action") == "add":
                return await self.async_step_add_area()
            if user_input.get("action") == "remove":
                return await self.async_step_remove_area()
        return await self.async_step_init()

    async def async_step_add_area(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Add a new area with its indoor sensors."""
        if user_input is not None:
            areas = list(self.config_entry.data.get("areas", []))
            areas.append(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, "areas": areas},
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_area",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AREA_NAME): str,
                    vol.Required(CONF_INDOOR_TEMP): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="temperature"
                        ),
                    ),
                    vol.Required(CONF_INDOOR_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="humidity"
                        ),
                    ),
                    vol.Optional(CONF_INDOOR_ABS_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_INDOOR_DEW_POINT): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_INDOOR_HEAT_INDEX): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_INDOOR_CO2): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_INDOOR_PM25): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                }
            ),
        )

    async def async_step_remove_area(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Remove an existing area."""
        areas = self.config_entry.data.get("areas", [])

        if user_input is not None:
            area_name = user_input.get("area_to_remove")
            new_areas = [a for a in areas if a[CONF_AREA_NAME] != area_name]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, "areas": new_areas},
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="remove_area",
            data_schema=vol.Schema(
                {
                    vol.Required("area_to_remove"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=a[CONF_AREA_NAME], label=a[CONF_AREA_NAME]
                                )
                                for a in areas
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/smart_ventilation/config_flow.py
git commit -m "fix: rewrite config_flow.py for HA 2024.x+ — ConfigFlowResult, OptionsFlow no __init__"
```

---

### Task 5: __init__.py

**Files:**
- Rewrite: `custom_components/smart_ventilation/__init__.py`

- [ ] **Step 1: Rewrite __init__.py**

```python
"""Smart Ventilation integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_OUTDOOR_ABS_HUMIDITY, CONF_OUTDOOR_TEMP, DOMAIN
from .coordinator import SmartVentilationCoordinator

PLATFORMS = ["sensor", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Ventilation from a config entry."""
    if not entry.data.get(CONF_OUTDOOR_TEMP) or not entry.data.get(CONF_OUTDOOR_ABS_HUMIDITY):
        return False

    coordinator = SmartVentilationCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options or data change (e.g. area added/removed)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/smart_ventilation/__init__.py
git commit -m "refactor: clean up __init__.py"
```

---

### Task 6: sensor.py

**Files:**
- Rewrite: `custom_components/smart_ventilation/sensor.py`

Key changes:
- All sensors inherit from `CoordinatorEntity[SmartVentilationCoordinator]` — `available` is automatic
- `VentilationEfficiencySensor`: removed `device_class=ENUM`, keeps `unit=PERCENTAGE` + `state_class=MEASUREMENT`
- `HumidityDifferenceSensor`: removed `device_class=HUMIDITY` (incompatible with `g/m³`)
- `_attr_has_entity_name = True` + `_attr_translation_key` for HA-native entity naming
- Shared base class `_AreaSensor` removes boilerplate
- `_update_from_data()` hook called from `_handle_coordinator_update()`

- [ ] **Step 1: Rewrite sensor.py**

```python
"""Sensor platform for Smart Ventilation."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VENTILATION_ADVICE_LEVELS
from .coordinator import SmartVentilationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for each configured area."""
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for area in entry.data.get("areas", []):
        area_name = area["name"]
        entities.extend(
            [
                VentilationEfficiencySensor(coordinator, entry, area_name),
                VentilationAdviceSensor(coordinator, entry, area_name),
                HumidityDifferenceSensor(coordinator, entry, area_name),
                TemperatureDifferenceSensor(coordinator, entry, area_name),
            ]
        )
    async_add_entities(entities)


def _device_info(entry: ConfigEntry, area_name: str) -> dict:
    return {
        "identifiers": {(DOMAIN, f"{entry.entry_id}_{area_name}")},
        "name": area_name,
        "manufacturer": "Smart Ventilation",
    }


class _AreaSensor(CoordinatorEntity[SmartVentilationCoordinator], SensorEntity):
    """Base class for all Smart Ventilation area sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.area_name = area_name
        self._attr_device_info = _device_info(entry, area_name)

    @property
    def available(self) -> bool:
        return super().available and self.area_name in (self.coordinator.data or {})

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data.get(self.area_name, {}))
        self.async_write_ha_state()

    def _update_from_data(self, data: dict) -> None:
        """Extract entity value from coordinator data. Override in subclasses."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()


class VentilationEfficiencySensor(_AreaSensor):
    """Ventilation efficiency as a percentage (0–100%)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:air-filter"
    _attr_translation_key = "ventilation_efficiency"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator, entry, area_name)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_efficiency"

    def _update_from_data(self, data: dict) -> None:
        efficiency = data.get("efficiency", 0)
        self._attr_native_value = int(efficiency)
        if efficiency >= 80:
            self._attr_icon = "mdi:air-filter"
        elif efficiency >= 60:
            self._attr_icon = "mdi:air-purifier"
        elif efficiency >= 30:
            self._attr_icon = "mdi:air-humidifier"
        else:
            self._attr_icon = "mdi:air-humidifier-off"


class VentilationAdviceSensor(_AreaSensor):
    """Ventilation advice as an ENUM string."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = VENTILATION_ADVICE_LEVELS
    _attr_translation_key = "ventilation_advice"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator, entry, area_name)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_advice"

    def _update_from_data(self, data: dict) -> None:
        self._attr_native_value = data.get("advice", "Not Recommended")


class HumidityDifferenceSensor(_AreaSensor):
    """Absolute humidity difference indoor vs outdoor (g/m³)."""

    _attr_native_unit_of_measurement = "g/m³"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-percent"
    _attr_translation_key = "humidity_difference"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator, entry, area_name)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_humidity_diff"

    def _update_from_data(self, data: dict) -> None:
        self._attr_native_value = data.get("humidity_difference")


class TemperatureDifferenceSensor(_AreaSensor):
    """Temperature difference indoor vs outdoor (°C)."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "temperature_difference"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator, entry, area_name)
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_temperature_diff"

    def _update_from_data(self, data: dict) -> None:
        self._attr_native_value = data.get("temperature_difference")
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/smart_ventilation/sensor.py
git commit -m "fix: rewrite sensor.py — CoordinatorEntity, valid device_class/unit combos, translation keys"
```

---

### Task 7: binary_sensor.py

**Files:**
- Rewrite: `custom_components/smart_ventilation/binary_sensor.py`

- [ ] **Step 1: Rewrite binary_sensor.py**

```python
"""Binary sensor platform for Smart Ventilation."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartVentilationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities for each configured area."""
    coordinator: SmartVentilationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CoolingRecommendedBinarySensor(coordinator, entry, area["name"])
        for area in entry.data.get("areas", [])
    )


class CoolingRecommendedBinarySensor(
    CoordinatorEntity[SmartVentilationCoordinator], BinarySensorEntity
):
    """Binary sensor: is cooling via ventilation recommended?"""

    _attr_has_entity_name = True
    _attr_icon = "mdi:fan"
    _attr_translation_key = "cooling_recommended"

    def __init__(
        self,
        coordinator: SmartVentilationCoordinator,
        entry: ConfigEntry,
        area_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.area_name = area_name
        self._attr_unique_id = f"{entry.entry_id}_{area_name}_cooling_recommended"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{area_name}")},
            "name": area_name,
            "manufacturer": "Smart Ventilation",
        }

    @property
    def available(self) -> bool:
        return super().available and self.area_name in (self.coordinator.data or {})

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data.get(self.area_name, {})
        self._attr_is_on = data.get("cooling_recommended", False)

        reasons: list[str] = []
        in_temp = data.get("indoor_temperature")
        out_temp = data.get("outdoor_temperature")
        efficiency = data.get("efficiency", 0)

        if in_temp is not None and in_temp <= 23:
            reasons.append("Inside not warm enough (\u226423\u00b0C)")
        if in_temp is not None and out_temp is not None and out_temp >= in_temp:
            reasons.append("Outside not cooler than inside")
        if efficiency <= 30:
            reasons.append("Ventilation efficiency too low (\u226430%)")
        if self._attr_is_on:
            reasons.append("Favorable conditions for summer ventilation")

        self._attr_extra_state_attributes = {"reasons": reasons}
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/smart_ventilation/binary_sensor.py
git commit -m "fix: rewrite binary_sensor.py — CoordinatorEntity, cleaner reason messages"
```

---

### Task 8: strings.json and translations/en.json

**Files:**
- Create: `custom_components/smart_ventilation/strings.json`
- Rewrite: `custom_components/smart_ventilation/translations/en.json`

HA requires `strings.json` as the primary i18n source. The ENUM sensor `ventilation_advice` needs `state` translations to match its `_attr_options` values exactly.

- [ ] **Step 1: Create strings.json**

```json
{
  "config": {
    "title": "Smart Ventilation",
    "step": {
      "user": {
        "title": "Outdoor Sensors",
        "description": "Configure the global outdoor sensors used for all areas.",
        "data": {
          "outdoor_temperature": "Outdoor Temperature",
          "outdoor_absolute_humidity": "Outdoor Absolute Humidity",
          "outdoor_dew_point": "Outdoor Dew Point (optional)",
          "outdoor_temperature_max_24h": "Outdoor Max Temperature 24h (optional)",
          "outdoor_humidity": "Outdoor Relative Humidity (optional)",
          "wind_average": "Wind Average (optional)",
          "wind_max": "Wind Maximum (optional)"
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
        "description": "Configure sensors for a new area or room.",
        "data": {
          "name": "Area Name",
          "indoor_temperature": "Indoor Temperature",
          "indoor_humidity": "Indoor Humidity",
          "indoor_absolute_humidity": "Indoor Absolute Humidity (optional)",
          "indoor_dew_point": "Indoor Dew Point (optional)",
          "indoor_heat_index": "Indoor Heat Index (optional)",
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

- [ ] **Step 2: Rewrite translations/en.json — identical content to strings.json**

Copy the exact same JSON content from Step 1 into `translations/en.json`.

- [ ] **Step 3: Commit**

```bash
git add custom_components/smart_ventilation/strings.json custom_components/smart_ventilation/translations/en.json
git commit -m "feat: add strings.json, update translations/en.json with entity translation keys"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Task |
|-----------------|------|
| Fix `FlowResult` import (500 error root cause) | Task 4 |
| Fix `OptionsFlowHandler.__init__` | Task 4 |
| Fix `VentilationEfficiencySensor` device_class+unit+state_class | Task 6 |
| Fix `HumidityDifferenceSensor` device_class | Task 6 |
| `CoordinatorEntity` for all entities | Tasks 6, 7 |
| Fix `calculate_absolute_humidity` formula | Task 2 |
| Fix `calculate_dew_point` formula | Task 2 |
| Bedroom room logic (CO2-dominant) | Task 2 |
| Attic room logic (temperature-only) | Task 2 |
| Remove -999 magic values from coordinator | Task 3 |
| Split `calculator.py` as pure Python | Task 2 |
| `strings.json` added | Task 8 |
| `integration_type: "service"` | Task 1 |
| `version: "1.0.0"` | Task 1 |
| `const.py` constants only | Task 1 |

All spec requirements covered.

### Type consistency

- `VentilationCalculator(...)` defined Task 2, called Task 3 — signature matches exactly
- `get_advice()` defined Task 2, imported Task 3 — consistent
- `VENTILATION_ADVICE_LEVELS` defined Task 1, used Task 6 (`_attr_options`) and must match `strings.json` state keys (Task 8) — all five values identical: `"Optimal"`, `"Recommended"`, `"Decent"`, `"Neutral"`, `"Not Recommended"`
- `_detect_room_type()` returns one of `"kitchen"`, `"bathroom"`, `"bedroom"`, `"attic"`, `"generic"` — matches `VentilationCalculator.calculate()` routing
- `SmartVentilationCoordinator` defined Task 3, typed in Tasks 6 and 7 as `CoordinatorEntity[SmartVentilationCoordinator]`
- unique_id pattern `f"{entry.entry_id}_{area_name}_{suffix}"` consistent across sensor.py and binary_sensor.py
- `_device_info()` helper in sensor.py and inline dict in binary_sensor.py use same identifier key `f"{entry.entry_id}_{area_name}"`
- `_attr_translation_key` values in sensor.py/binary_sensor.py match keys in `strings.json` entity section

No inconsistencies found.
