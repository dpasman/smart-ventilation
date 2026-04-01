# Design: Air Quality Sensor, Ventilation Reason Sensor & Outdoor PM2.5

**Date:** 2026-04-01
**Status:** Approved

## Summary

Three additions to the smart-ventilation integration:

1. **Outdoor PM2.5** — new optional global outdoor sensor, passed to all room calculators
2. **Air Quality Sensor** — per-area sensor showing room health category (Excellent → Unhealthy), worst-parameter-wins
3. **Ventilation Reason Sensor** — per-area sensor showing the primary reason to ventilate or not as a short English string

---

## 1. Outdoor PM2.5

### Config flow
Add optional field `CONF_OUTDOOR_PM25 = "outdoor_pm25"` in `const.py`.
Add to the outdoor sensor setup step in `config_flow.py` alongside existing optional sensors.

### Coordinator
Read the sensor state in `coordinator.py` and pass as `out_pm25` to every `VentilationCalculator` call (already used in kitchen room type; now available globally for health scoring in all room types).

---

## 2. Air Quality Sensor

### Entity
- **Class:** `AirQualitySensor` in `sensor.py`
- **State:** one of `["Excellent", "Good", "Moderate", "Poor", "Unhealthy"]`
- **Attributes:** `co2_category`, `pm25_category`, `humidity_category`, `temperature_category`, `worst_parameter`
- **Unique ID:** `{entry_id}_{area_name}_air_quality`
- **Icon:** dynamic — `mdi:air-filter` (Excellent), `mdi:air-purifier` (Good), `mdi:cloud-alert` (Moderate), `mdi:biohazard` (Poor/Unhealthy)

### Calculation — `calculator.py` `get_air_quality()`
Worst-parameter-wins: each available parameter is scored independently; the worst category determines the sensor state.

Parameters with no sensor configured are skipped (graceful degradation). The `worst_parameter` attribute names which parameter drove the result.

#### Thresholds (based on WHO 2021 AQG + EN 16798-1 + ASHRAE 55)

| Parameter | Excellent | Good | Moderate | Poor | Unhealthy |
|---|---|---|---|---|---|
| CO2 (ppm) | ≤800 | 801–1000 | 1001–1400 | 1401–2000 | >2000 |
| PM2.5 (µg/m³) | ≤15 | 16–25 | 26–37 | 38–75 | >75 |
| Humidity (%) | 40–60 | 30–39 / 61–65 | 25–29 / 66–70 | 20–24 / 71–80 | <20 / >80 |
| Temperature (°C) | 20–25 | 18–19 / 26–27 | 16–17 / 28–29 | 14–15 / 30–31 | <14 / >31 |

Sources: WHO 2021 Air Quality Guidelines (PM2.5), EN 16798-1:2019 (CO2, temperature categories), EPA Indoor Air Quality guide + WHO dampness guidelines (humidity), ASHRAE 55-2023 (temperature comfort zones).

### Coordinator
Add `air_quality` (string) and `air_quality_attributes` (dict) to area data dict.

---

## 3. Ventilation Reason Sensor

### Entity
- **Class:** `VentilationReasonSensor` in `sensor.py`
- **State:** short English string (see reason strings below)
- **Unique ID:** `{entry_id}_{area_name}_ventilation_reason`
- **Icon:** `mdi:chat-question` (static)

### Calculation — `calculator.py` `get_ventilation_reason()`
Inspects the calculator's internal state after `calculate()` to determine the dominant factor. Logic:

**Positive reasons** (ventilation recommended):
- `"Dangerously high CO2"` — `in_co2 > 1400`
- `"High CO2 level"` — `in_co2 > 1200`
- `"Elevated CO2"` — `in_co2 > 800`
- `"High indoor humidity"` — humidity difference is primary driver (`hum_diff > 1.5` and `in_rh > 55%`)
- `"Indoor too warm"` — cooling benefit active (`in_temp > 24` and `out_temp < in_temp - 3`)
- `"Good ventilation conditions"` — general high efficiency, no dominant factor

**Negative reasons** (ventilation not recommended):
- `"Storm warning"` — wind_avg > 10 m/s or wind_max > 15 m/s
- `"Condensation risk"` — `out_dew >= in_temp - 2`
- `"Outdoor PM2.5 too high"` — `out_pm25 > 25`
- `"Outdoor air too hot"` — `out_temp > 27`
- `"Outdoor humidity too high"` — `out_rh > 80`
- `"Outdoor air too cold"` — large temp diff with cold outside (`temp_diff > 7` and `out_temp_max < 20`)

**Neutral:**
- `"Conditions balanced"` — efficiency 20–39, no strong positive or negative driver
- `"Good air quality"` — efficiency ≥ 40, no dominant factor

Priority order for positive reasons: CO2 > humidity > temperature > general.
Priority order for negative reasons: storm > condensation > PM2.5 > heat > humidity > cold.

### Coordinator
Add `ventilation_reason` (string) to area data dict.

---

## 4. Strings & Translations

Add to `strings.json` (and mirror to `translations/en.json`):

```json
"outdoor_pm25": "Outdoor PM2.5",
"air_quality": "Air Quality",
"ventilation_reason": "Ventilation Reason"
```

---

## 5. Files Changed

| File | Change |
|---|---|
| `const.py` | Add `CONF_OUTDOOR_PM25` |
| `config_flow.py` | Add outdoor PM2.5 optional field |
| `calculator.py` | Add `get_air_quality()`, `get_ventilation_reason()` methods; accept `out_pm25` in constructor |
| `coordinator.py` | Read outdoor PM2.5 sensor; add `air_quality`, `air_quality_attributes`, `ventilation_reason` to area data |
| `sensor.py` | Add `AirQualitySensor`, `VentilationReasonSensor` classes |
| `strings.json` | Add new field labels and sensor names |
| `translations/en.json` | Mirror strings.json |

---

## 6. Version Bump

Bump to **1.2.0** (minor version — new entities added).
