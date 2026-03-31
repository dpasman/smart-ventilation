# Smart Ventilation — Full Rebuild Design

**Date:** 2026-03-31
**Scope:** Complete rebuild of the `smart_ventilation` HA custom component for compatibility with HA 2024.x+ and correctness of ventilation logic.

---

## 1. Problem Summary

The current component has two categories of issues:

### HA Compatibility Breaks
- `FlowResult` imported from `homeassistant.data_entry_flow` — removed in HA 2024.x+, causes 500 error on config flow load
- `OptionsFlowHandler.__init__` accepts `config_entry` parameter — no longer valid in HA 2024.x+
- `VentilationEfficiencySensor` combines `device_class=ENUM` with `unit=PERCENTAGE` and `state_class=MEASUREMENT` — invalid combination, HA rejects it
- `HumidityDifferenceSensor` uses `device_class=HUMIDITY` with `g/m³` unit — HUMIDITY device class only accepts `%`
- Sensors do not inherit from `CoordinatorEntity` — no automatic `available` handling

### Logic / Math Bugs
- `calculate_absolute_humidity`: formula multiplies by the exponent argument instead of computing `exp()`, producing wrong values
- `calculate_dew_point`: uses `rh/100` where `math.log(rh/100)` is required by the Magnus formula
- `bedroom` and `attic` room types are detected but fall through to generic calculation — no actual differentiation
- Coordinator passes `-999` magic sentinel values to calculator instead of `None`

---

## 2. Architecture

```
custom_components/smart_ventilation/
├── __init__.py          # async_setup_entry, async_unload_entry
├── manifest.json        # domain, version, iot_class
├── const.py             # constants only — no functions, no classes
├── calculator.py        # VentilationCalculator, helper math functions
├── coordinator.py       # SmartVentilationCoordinator (DataUpdateCoordinator)
├── config_flow.py       # SmartVentilationConfigFlow + OptionsFlowHandler
├── sensor.py            # sensor entities via CoordinatorEntity
├── binary_sensor.py     # binary sensor entities via CoordinatorEntity
├── strings.json         # i18n source (HA standard, required)
└── translations/
    └── en.json
```

**Key principle:** `calculator.py` is pure Python with no HA imports. It can be unit-tested standalone.

---

## 3. `const.py`

Contains only string constants and dicts. No functions, no TypedDicts with logic.

```python
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

---

## 4. `calculator.py`

### Math helper functions (corrected)

```python
import math

def calculate_absolute_humidity(temp_c: float, rh: float) -> float:
    """g/m³ via Magnus formula."""
    # Correct: exp() not multiply-by-exponent-arg
    sat_vp = 6.112 * math.exp(17.67 * temp_c / (temp_c + 243.5))
    actual_vp = sat_vp * (rh / 100)
    return round((actual_vp * 2.1674) / (273.15 + temp_c), 2)

def calculate_dew_point(temp_c: float, rh: float) -> float:
    """Dew point via Magnus formula."""
    # Correct: log(rh/100), not rh/100
    a, b = 17.27, 237.7
    alpha = (a * temp_c) / (b + temp_c) + math.log(rh / 100)
    return round((b * alpha) / (a - alpha), 1)

def calculate_heat_index(temp_c: float, rh: float) -> float:
    """Rothfusz regression, valid for temp_c >= 27."""
    if temp_c < 27:
        return temp_c
    T = temp_c * 9 / 5 + 32
    HI = (-42.379 + 2.04901523*T + 10.14333127*rh
          - 0.22475541*T*rh - 0.00683783*T*T
          - 0.05481717*rh*rh + 0.00122874*T*T*rh
          + 0.00085282*T*rh*rh - 0.00000199*T*T*rh*rh)
    if rh < 13 and 80 < T < 112:
        HI -= ((13 - rh) / 4) * math.sqrt((17 - abs(T - 95)) / 17)
    elif rh > 85 and 80 < T < 87:
        HI += ((rh - 85) / 10) * ((87 - T) / 5)
    return round((HI - 32) * 5 / 9, 1)

def get_advice(efficiency: float) -> str:
    if efficiency >= 80: return "Optimal"
    if efficiency >= 60: return "Recommended"
    if efficiency >= 40: return "Decent"
    if efficiency >= 20: return "Neutral"
    return "Not Recommended"
```

### `VentilationCalculator`

Accepts all sensor values as `float | None`. No magic sentinel values.

**Required inputs:** `in_temp`, `in_rh`, `out_temp`, `out_hum_abs`
**Optional inputs:** all others

**Validity check:**
- Returns `0.0` if any required input is `None`
- Returns `0.0` if outdoor dew point >= indoor temp - 2 (condensation risk)

**Room-type routing:**

| Room type | Primary signal | Secondary | Notes |
|-----------|---------------|-----------|-------|
| `generic` | absolute humidity diff | temperature diff | current logic, corrected |
| `bathroom` | absolute humidity diff | temperature diff | aggressive humidity thresholds, post-shower override |
| `kitchen`  | humidity + CO2 + heat index | temperature | accumulative scoring |
| `bedroom`  | CO2 level | humidity diff | sleep quality focus, CO2 dominant |
| `attic`    | temperature diff | (no humidity focus) | cooling-only logic, summer-oriented |

**Bedroom calculation (new):**
- CO2 > 1200: +50
- CO2 > 1000: +35
- CO2 > 800: +20
- CO2 > 600: +10
- humidity_diff > 2 and in_rh > 60: +20
- humidity_diff > 1: +10
- out_temp > in_temp - 3: cooling bonus
- out_temp > 27: penalty -50
- out_temp_max < 20 and large temp_diff: penalty

**Attic calculation (new):**
- No humidity focus — attics are intentionally ventilated for temperature
- in_temp > 30 and out_temp < in_temp - 5: +60 (strong cooling need)
- in_temp > 27 and out_temp < in_temp - 3: +40
- in_temp > 24 and out_temp < in_temp: +20
- out_temp > 27: penalty -60 (no benefit ventilating with hot air)
- Wind bonus same as other rooms

**`get_reasons()` returns `list[str]`** — one human-readable reason per contributing factor.

---

## 5. `coordinator.py`

- Inherits `DataUpdateCoordinator[dict[str, dict]]`
- `update_interval = timedelta(minutes=1)`
- `_async_update_data()` reads HA states, calls `VentilationCalculator`, returns structured dict per area
- Passes `None` for missing/unavailable sensor states — no -999 magic values
- `_get_outdoor_data()` and `_get_area_data()` are regular (sync) methods, not async — they don't await anything

Data shape per area:
```python
{
    "efficiency": float,          # 0-100
    "advice": str,                # "Optimal" | "Recommended" | ...
    "reasons": list[str],
    "humidity_difference": float | None,
    "temperature_difference": float | None,
    "cooling_recommended": bool,
    "indoor_temperature": float | None,
    "outdoor_temperature": float | None,
}
```

---

## 6. `config_flow.py`

**Modern HA 2024.x+ patterns:**
- Return type: `ConfigFlowResult` (from `homeassistant.config_entries`) — no `FlowResult`
- `OptionsFlowHandler` does NOT accept `config_entry` in `__init__` — uses `self.config_entry` from base class
- `async_get_options_flow` is a `@staticmethod @callback` returning `OptionsFlowHandler(config_entry)` — wait, in HA 2024.4+ this changed too. The new pattern is just `return OptionsFlowHandler()` and the base class sets `self.config_entry`.

Flow steps (unchanged in UX):
1. `user` — outdoor sensors
2. Options: `init` → menu → `add_area` or `remove_area`

---

## 7. `sensor.py`

All sensors inherit from `CoordinatorEntity[SmartVentilationCoordinator]` and `SensorEntity`.

`CoordinatorEntity` provides:
- `available` property (False when coordinator has no data)
- `_handle_coordinator_update()` pattern
- Automatic state write on coordinator update

**Sensor classes and their correct attributes:**

| Class | device_class | unit | state_class |
|-------|-------------|------|-------------|
| `VentilationEfficiencySensor` | `None` | `%` | `MEASUREMENT` |
| `VentilationAdviceSensor` | `ENUM` | None | None |
| `HumidityDifferenceSensor` | `None` | `g/m³` | `MEASUREMENT` |
| `TemperatureDifferenceSensor` | `TEMPERATURE` | `°C` | `MEASUREMENT` |

All sensors use `_attr_has_entity_name = True` and a translation key for their name.

Device info is shared per area (same `identifiers`), so all area sensors are grouped under one device in HA.

---

## 8. `binary_sensor.py`

`CoolingRecommendedBinarySensor` inherits from `CoordinatorEntity` + `BinarySensorEntity`.

- `device_class = BinarySensorDeviceClass.RUNNING` (or `None` — cooling is not a standard device class)
- `extra_state_attributes` includes `reasons` list

---

## 9. `manifest.json`

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

Note: `integration_type` changed from `"device"` to `"service"` — this integration calculates data, it is not a physical device.

---

## 10. `strings.json` + `translations/en.json`

`strings.json` is the primary source; `translations/en.json` mirrors it. Contains:
- Config flow step labels and field descriptions
- Options flow step labels
- Entity names (via translation keys, used with `_attr_has_entity_name = True`)

---

## 11. What is NOT in scope

- Tests (can be added later — calculator.py is now structured to be easily testable)
- HACS `hacs.json` updates
- Dutch translation (`translations/nl.json`)
- Switching to event-driven updates (coordinator polling every minute is sufficient)
