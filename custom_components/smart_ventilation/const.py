"""Constants for Smart Ventilation integration."""

from typing import TypedDict


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


class AreaConfig(TypedDict):
    """Configuration for a single area."""

    name: str
    indoor_temperature: str
    indoor_humidity: str
    indoor_absolute_humidity: str | None
    indoor_dew_point: str | None
    indoor_heat_index: str | None
    indoor_co2: str | None
    indoor_pm25: str | None


class OutdoorSensorsConfig(TypedDict):
    """Configuration for global outdoor sensors."""

    outdoor_temperature: str
    outdoor_absolute_humidity: str
    outdoor_dew_point: str | None
    outdoor_temperature_max_24h: str | None
    outdoor_humidity: str | None
    wind_average: str | None
    wind_max: str | None


DEFAULT_OUTDOOR_SENSORS = {
    "weather_station_temperature": "sensor.weather_station_temperature",
    "thermal_comfort_outside_absolute_humidity": "sensor.thermal_comfort_outside_absolute_humidity",
    "thermal_comfort_outside_dew_point": "sensor.thermal_comfort_outside_dew_point",
    "highest_outside_temperature_24h": "sensor.highest_outside_temperature_24h",
    "weather_station_humidity": "sensor.weather_station_humidity",
    "wind_avg_15min": "sensor.wind_avg_15min",
    "max_wind_speed": "sensor.max_wind_speed",
}

DEVICE_TYPE_VENTILATION_EFFICIENCY = "ventilation_efficiency"
DEVICE_TYPE_COOLING_RECOMMENDED = "cooling_recommended"

VENTILATION_ADVICE = {
    (80, 100): "Optimal",
    (60, 80): "Recommended",
    (40, 60): "Decent",
    (20, 40): "Neutral",
    (0, 20): "Not Recommended",
}


def get_advice(efficiency: float) -> str:
    """Get advice text based on efficiency value."""
    for (low, high), text in VENTILATION_ADVICE.items():
        if low <= efficiency < high:
            return text
    return "Not Recommended"


def calculate_absolute_humidity(temp_c: float, rh: float) -> float:
    """Calculate absolute humidity in g/m³ from temperature and relative humidity."""
    if temp_c < -50 or rh < 0 or rh > 100:
        return 0.0
    sat_vp = 6.112 * (17.67 * temp_c / (temp_c + 243.5)) * 2.71828 ** (17.67 * temp_c / (temp_c + 243.5))
    actual_vp = sat_vp * (rh / 100)
    abs_humidity = (actual_vp * 2.1674) / (273.15 + temp_c)
    return round(abs_humidity, 2)


def calculate_dew_point(temp_c: float, rh: float) -> float:
    """Calculate dew point in °C."""
    if temp_c < -50 or rh < 0 or rh > 100:
        return 0.0
    a = 17.27
    b = 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + (rh / 100)
    dew = (b * alpha) / (a - alpha)
    return round(dew, 1)


def calculate_heat_index(temp_c: float, rh: float) -> float:
    """Calculate heat index in °C."""
    if temp_c < 27:
        return temp_c
    T = temp_c * 9 / 5 + 32
    R = rh
    HI = -42.379 + 2.04901523 * T + 10.14333127 * R - 0.22475541 * T * R - 0.00683783 * T * T - 0.05481717 * R * R + 0.00122874 * T * T * R + 0.00085282 * T * R * R - 0.00000199 * T * T * R * R
    if R < 13 and 80 < T < 112:
        HI -= ((13 - R) / 4) * ((17 - abs(T - 95)) / 17) ** 0.5
    elif R > 85 and 80 < T < 87:
        HI += ((R - 85) / 10) * ((87 - T) / 5)
    return round((HI - 32) * 5 / 9, 1)


class VentilationCalculator:
    """Calculate ventilation efficiency based on sensor data."""

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
    ):
        self.in_temp = in_temp
        self.in_rh = in_rh
        self.out_temp = out_temp
        self.out_hum_abs = out_hum_abs
        self.in_hum_abs = in_hum_abs if in_hum_abs is not None else calculate_absolute_humidity(in_temp or 20, in_rh or 50)
        self.in_dew = in_dew if in_dew is not None else calculate_dew_point(in_temp or 20, in_rh or 50)
        self.out_dew = out_dew
        self.out_temp_max = out_temp_max if out_temp_max is not None else out_temp
        self.in_heat_index = in_heat_index if in_heat_index is not None else calculate_heat_index(in_temp or 20, in_rh or 50)
        self.in_co2 = in_co2
        self.in_pm25 = in_pm25
        self.out_pm25 = out_pm25
        self.wind_avg = wind_avg
        self.wind_max = wind_max
        self.out_rh = out_rh
        self.room_type = room_type
        self.reasons: list[str] = []
        self._valid = True

    def _check_validity(self) -> bool:
        """Check if all required values are valid."""
        required = [self.in_temp, self.in_rh, self.out_temp, self.out_hum_abs, self.in_hum_abs]
        if any(v is None or v < -100 for v in required):
            self._valid = False
            return False
        if self.out_dew is not None and self.in_temp is not None:
            if self.out_dew >= self.in_temp - 2:
                self._valid = False
                return False
        return True

    def calculate(self) -> float:
        """Calculate the ventilation efficiency score (0-100)."""
        if not self._check_validity():
            return 0.0

        hum_diff = (self.in_hum_abs or 0) - (self.out_hum_abs or 0)
        temp_diff = (self.in_temp or 0) - (self.out_temp or 0)
        efficiency = 0

        if self.room_type == "kitchen":
            efficiency = self._calculate_kitchen(hum_diff, temp_diff)
        elif self.room_type == "bathroom":
            efficiency = self._calculate_bathroom(hum_diff, temp_diff)
        else:
            efficiency = self._calculate_generic(hum_diff, temp_diff)

        return float(max(0, min(100, efficiency)))

    def _calculate_kitchen(self, hum_diff: float, temp_diff: float) -> int:
        """Calculate kitchen ventilation efficiency."""
        s = 0
        in_rh = self.in_rh if self.in_rh is not None else 0

        if in_rh > 65:
            s += 20
        elif in_rh > 55:
            s += 10

        s += int(max(0, min(100, hum_diff * 10)))

        if self.in_co2 and self.in_co2 > 0:
            if self.in_co2 > 1200:
                s += 40
            elif self.in_co2 > 800:
                s += 20

        if self.in_pm25 is not None and self.out_pm25 is not None:
            if self.out_pm25 < self.in_pm25:
                s += 10
            elif self.out_pm25 > 20:
                s -= 20

        if self.in_heat_index and self.in_heat_index > 35:
            s += 20
        elif self.in_heat_index and self.in_heat_index > 30:
            s += 10

        if self.wind_avg and self.wind_max:
            if 2 <= self.wind_avg <= 8 and self.wind_max < 12:
                s += 10

        if self.in_temp and self.out_temp:
            if self.in_temp > 24 and self.out_temp < self.in_temp - 3:
                s += int(max(0, min(20, (temp_diff - 3) * 5)))

        if self.out_temp and self.out_temp > 27:
            s -= 50

        if self.in_dew and self.in_temp and self.in_dew > self.in_temp - 1:
            s -= 40

        if self.out_temp_max and self.out_temp_max < 20 and temp_diff > 3:
            s -= int(max(0, min(30, (temp_diff - 3) * 5)))

        return max(0, min(100, s))

    def _calculate_bathroom(self, hum_diff: float, temp_diff: float) -> int:
        """Calculate bathroom ventilation efficiency."""
        s = 0

        if hum_diff > 3 and self.in_rh and self.in_rh > 60:
            s = 100
        elif hum_diff > 2.5 and self.in_rh and self.in_rh > 55:
            s = 90
        elif hum_diff > 2 and self.in_rh and self.in_rh > 55:
            s = 80
        elif hum_diff > 1.5 and self.in_rh and self.in_rh > 55:
            s = 70
        elif hum_diff > 1.0 and self.in_rh and self.in_rh > 55:
            s = 60
        elif hum_diff > 0.5:
            s = 40
        elif hum_diff > 0:
            s = 30
        else:
            s = 20

        if self.out_temp_max and self.out_temp_max < 20:
            if temp_diff > 7:
                s -= 30
            elif temp_diff > 5:
                s -= 20
            elif temp_diff > 3:
                s -= 10

        if self.wind_avg and self.wind_max:
            if 2 <= self.wind_avg <= 8 and self.wind_max < 12:
                s += 10

        if self.in_temp and self.in_temp > 24:
            if self.out_temp and self.out_temp < self.in_temp - 5:
                s += 20
            elif self.out_temp and self.out_temp < self.in_temp - 3:
                s += 10

            if self.in_heat_index:
                if self.in_heat_index > 35:
                    s += 20
                elif self.in_heat_index > 30:
                    s += 10

        if self.out_temp and self.out_temp > 27:
            s -= 50

        if self.out_dew is not None and self.in_dew is not None:
            if self.out_dew >= self.in_dew - 0.5:
                if hum_diff > 2:
                    s -= 15
                elif hum_diff > 1:
                    s -= 25
                else:
                    s -= 35

        if self.out_rh:
            if self.out_rh > 90:
                s -= 20
            elif self.out_rh > 80:
                s -= 10

        if self.in_rh and self.in_rh >= 80:
            s = max(s, 65)
        elif self.in_rh and self.in_rh >= 75 and hum_diff > 0.5:
            s = max(s, 45)

        s = max(s, 20)

        return max(0, min(100, s))

    def _calculate_generic(self, hum_diff: float, temp_diff: float) -> int:
        """Calculate generic room ventilation efficiency."""
        s = 0

        if hum_diff > 3 and self.in_rh and self.in_rh > 60:
            s = 100
        elif hum_diff > 2.5 and self.in_rh and self.in_rh > 55:
            s = 90
        elif hum_diff > 2 and self.in_rh and self.in_rh > 55:
            s = 80
        elif hum_diff > 1.5 and self.in_rh and self.in_rh > 55:
            s = 70
        elif hum_diff > 1.0 and self.in_rh and self.in_rh > 55:
            s = 60
        elif hum_diff > 0.5:
            s = 40
        elif hum_diff > 0:
            s = 30
        else:
            s = 20

        if self.out_temp_max and self.out_temp_max < 20:
            if temp_diff > 10:
                s -= 30
            elif temp_diff > 7:
                s -= 20
            elif temp_diff > 5:
                s -= 10

        if self.wind_avg and self.wind_max:
            if 2 <= self.wind_avg <= 8 and self.wind_max < 12:
                s += 10

        if self.in_temp and self.in_temp > 24:
            if self.out_temp and self.out_temp < self.in_temp - 5:
                s += 20
            elif self.out_temp and self.out_temp < self.in_temp - 3:
                s += 10

            if self.in_heat_index:
                if self.in_heat_index > 35:
                    s += 20
                elif self.in_heat_index > 30:
                    s += 10

        if self.out_temp and self.out_temp > 27:
            s -= 50

        return max(0, min(100, s))

    def get_reasons(self) -> list[str]:
        """Get list of reasons for the calculated efficiency."""
        if not self._valid:
            return ["Insufficient data available for analysis"]

        hum_diff = (self.in_hum_abs or 0) - (self.out_hum_abs or 0)
        temp_diff = (self.in_temp or 0) - (self.out_temp or 0)

        if hum_diff > 3 and self.in_rh and self.in_rh > 60:
            self.reasons.append("High moisture removal potential and high indoor RH")
        elif hum_diff > 1.5 and self.in_rh and self.in_rh > 55:
            self.reasons.append("Good moisture removal with reasonable indoor RH")
        elif hum_diff > 0.5:
            self.reasons.append("Moderate moisture removal")
        elif hum_diff > 0:
            self.reasons.append("Minimal moisture removal")
        else:
            self.reasons.append("No effective moisture removal")

        if self.out_temp_max and self.out_temp_max < 20:
            if temp_diff > 10:
                self.reasons.append("Very large indoor-outdoor temperature difference")
            elif temp_diff > 7:
                self.reasons.append("Large indoor-outdoor temperature difference")
            elif temp_diff > 5:
                self.reasons.append("Moderate indoor-outdoor temperature difference")
            else:
                self.reasons.append("Temperature difference small or negative")

        if self.wind_avg and self.wind_max:
            if 2 <= self.wind_avg <= 8 and self.wind_max < 12:
                self.reasons.append("Favorable wind conditions")
            else:
                self.reasons.append("Wind conditions not optimal")

        if self.in_temp and self.in_temp > 24:
            if self.out_temp:
                if self.out_temp < self.in_temp - 5:
                    self.reasons.append("Outside is much cooler than inside - strong summer cooling possible")
                elif self.out_temp < self.in_temp - 3:
                    self.reasons.append("Outside is cooler than inside - summer cooling possible")

            if self.in_heat_index:
                if self.in_heat_index > 35:
                    self.reasons.append("High heat index inside - strong ventilation desired")
                elif self.in_heat_index > 30:
                    self.reasons.append("Elevated heat index inside - ventilation useful")

        if self.out_temp and self.out_temp > 27:
            self.reasons.append("Outside air too hot - ventilation discouraged")

        if self.in_rh and self.in_rh >= 80 and self.room_type == "bathroom":
            self.reasons.append("Post-shower override: at least Recommended")

        return self.reasons
