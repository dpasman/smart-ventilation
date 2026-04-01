"""Ventilation efficiency calculator — no HA imports, pure Python."""

from __future__ import annotations

import math


def calculate_absolute_humidity(temp_c: float, rh: float) -> float:
    """Calculate absolute humidity in g/m³ using the Magnus formula."""
    if temp_c <= -240 or rh <= 0 or rh > 100:
        return 0.0
    sat_vp = 6.112 * math.exp(17.67 * temp_c / (temp_c + 243.5))
    actual_vp = sat_vp * (rh / 100)
    return round((actual_vp * 216.74) / (273.15 + temp_c), 2)


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


_AIR_QUALITY_LEVELS = ["Excellent", "Good", "Moderate", "Poor", "Unhealthy"]


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
            # CO2 health override even when other sensor data is invalid
            if self.in_co2 is not None and self.in_co2 > 1400:
                return 60.0
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

        # Shared penalties — applied for all room types
        score += self._outdoor_rh_penalty()
        if self._condensation_surface_risk():
            score -= 30
        score += self._storm_penalty()

        # Bathroom floors (after shared penalties so storm can still override)
        if self.room_type == "bathroom":
            if self.in_rh is not None:
                if self.in_rh >= 80:
                    score = max(score, 65)
                elif self.in_rh >= 75 and hum_diff > 0.5:
                    score = max(score, 45)
            score = max(score, 20)

        # CO2 health override — always last, overrides everything
        if self.in_co2 is not None and self.in_co2 > 1400:
            score = max(score, 60)

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

        if self._storm_penalty() < 0:
            reasons.append(
                f"Storm conditions (wind {self.wind_avg}/{self.wind_max} m/s) — do not open windows"
            )
        elif self.wind_avg is not None and self.wind_max is not None:
            if 2 <= self.wind_avg <= 8 and self.wind_max < 12:
                reasons.append("Favorable wind conditions")
            else:
                reasons.append("Wind conditions not optimal")

        if self._condensation_surface_risk():
            reasons.append(
                f"Condensation risk: indoor dew point ({self.in_dew}°C) "
                f"above outdoor temperature ({self.out_temp}°C)"
            )

        if self._outdoor_rh_penalty() < 0:
            reasons.append(f"Very humid outdoor air ({int(self.out_rh)}% RH) — reduced moisture removal")

        if self.in_temp is not None and self.in_temp > 24 and self.out_temp is not None:
            if self.out_temp < self.in_temp - 5:
                reasons.append("Outside much cooler — strong cooling potential")
            elif self.out_temp < self.in_temp - 3:
                reasons.append("Outside cooler — cooling possible")

        if self.out_temp is not None and self.out_temp > 27:
            reasons.append("Outside too hot — ventilation discouraged")

        if self.in_co2 is not None:
            if self.in_co2 > 1400:
                reasons.append(f"Dangerous CO₂ level ({int(self.in_co2)} ppm) — health override: ventilate now")
            elif self.in_co2 > 1200:
                reasons.append(f"Very high CO₂ ({int(self.in_co2)} ppm) — strong ventilation bonus")
            elif self.in_co2 > 800:
                reasons.append(f"Elevated CO₂ ({int(self.in_co2)} ppm) — ventilation bonus")

        if self.room_type == "bathroom" and self.in_rh is not None and self.in_rh >= 80:
            reasons.append("Post-shower override active")

        return reasons

    def get_air_quality(self) -> dict:
        """Return room air quality category and per-parameter breakdown.

        Uses worst-parameter-wins: the overall level equals the worst
        individual parameter. Parameters without a configured sensor are
        skipped. Returns a dict with keys: level, co2_category,
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
                "level": _AIR_QUALITY_LEVELS[0],
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

    # ── Shared helpers ────────────────────────────────────────────────────

    def _wind_bonus(self) -> int:
        if self.wind_avg is not None and self.wind_max is not None:
            if 2 <= self.wind_avg <= 8 and self.wind_max < 12:
                return 10
        return 0

    def _storm_penalty(self) -> int:
        """Return -30 when wind is too strong to safely ventilate."""
        if self.wind_avg is not None and self.wind_avg > 10:
            return -30
        if self.wind_max is not None and self.wind_max > 15:
            return -30
        return 0

    def _outdoor_rh_penalty(self) -> int:
        """Penalty for very humid outdoor air (reduces moisture removal potential)."""
        if self.out_rh is not None:
            if self.out_rh > 90:
                return -20
            if self.out_rh > 80:
                return -10
        return 0

    def _condensation_surface_risk(self) -> bool:
        """True when indoor dew point exceeds outdoor temperature.

        Ventilating pushes warm moist indoor air towards cold surfaces (glass,
        frames), causing condensation at the point where the air cools below its
        dew point.
        """
        return (
            self.in_dew is not None
            and self.out_temp is not None
            and self.in_dew > self.out_temp
        )

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
        return 0

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
        # Primary goal: reduce indoor humidity
        s = self._base_humidity_score(hum_diff)
        # CO2 is a secondary additive bonus
        if self.in_co2 is not None and self.in_co2 > 0:
            if self.in_co2 > 1200:
                s += 40
            elif self.in_co2 > 1000:
                s += 25
            elif self.in_co2 > 800:
                s += 15
            elif self.in_co2 > 600:
                s += 5
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
        if self.out_temp_max is not None and self.out_temp_max < 20:
            if temp_diff > 10:
                s -= 30
            elif temp_diff > 7:
                s -= 20
            elif temp_diff > 5:
                s -= 10
        return max(0, min(100, s))

    def _score_attic(self) -> int:
        hum_diff = (self.in_hum_abs or 0) - (self.out_hum_abs or 0)
        temp_diff = (self.in_temp or 0) - (self.out_temp or 0)
        # Primary goal: reduce indoor humidity
        s = self._base_humidity_score(hum_diff)
        # Stronger cooling bonus since attics can get very hot
        if self.in_temp is not None and self.out_temp is not None:
            if self.in_temp > 30 and self.out_temp < self.in_temp - 5:
                s += 30
            elif self.in_temp > 27 and self.out_temp < self.in_temp - 3:
                s += 20
            elif self.in_temp > 24 and self.out_temp < self.in_temp:
                s += 10
        s += self._wind_bonus()
        if self.out_temp_max is not None and self.out_temp_max < 20:
            if temp_diff > 7:
                s -= 30
            elif temp_diff > 5:
                s -= 20
            elif temp_diff > 3:
                s -= 10
        if self.out_temp is not None and self.out_temp > 27:
            s -= 60
        return max(0, min(100, s))
