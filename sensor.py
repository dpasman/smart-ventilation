from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN, CONF_INDOOR_TEMP, CONF_INDOOR_HUM, CONF_OUTDOOR_TEMP, CONF_OUTDOOR_HUM, CONF_CO2, CONF_PM25_IN, CONF_PM25_OUT, CONF_WIND, CONF_HEAT_INDEX

class SmartVentilationSensor(SensorEntity):
    """Sensor for Smart Ventilation per room."""

    def __init__(self, hass, config_entry, room_name):
        self._hass = hass
        self._config = config_entry.data
        self._room_name = room_name
        self._attr_name = f"Smart Ventilation Score {room_name}"
        self._attr_native_unit_of_measurement = "%"
        self._state = None
        self._attr_extra_state_attributes = {}

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attr_extra_state_attributes

    async def async_update(self):
        """Calculate ventilation score for the room."""
        def get_float(sensor_id):
            try:
                return float(self._hass.states.get(sensor_id).state)
            except:
                return None

        in_temp = get_float(self._config[CONF_INDOOR_TEMP])
        in_hum = get_float(self._config[CONF_INDOOR_HUM])

        if in_temp is None or in_hum is None:
            self._state = 0
            self._attr_extra_state_attributes = {"reason": "Indoor temperature/humidity missing"}
            return

        # optionele sensoren
        out_temp = get_float(self._config.get(CONF_OUTDOOR_TEMP))
        out_hum = get_float(self._config.get(CONF_OUTDOOR_HUM))
        co2 = get_float(self._config.get(CONF_CO2))
        pm25_in = get_float(self._config.get(CONF_PM25_IN))
        pm25_out = get_float(self._config.get(CONF_PM25_OUT))
        wind = get_float(self._config.get(CONF_WIND))
        heat_index = get_float(self._config.get(CONF_HEAT_INDEX))

        score = 50
        reasons = []

        # Basis indoor humidity
        if in_hum > 65:
            score += 20
            reasons.append("High indoor humidity")
        elif in_hum > 55:
            score += 10
            reasons.append("Moderate indoor humidity")

        # Buiten vergelijken als beschikbaar
        if out_temp is not None and out_hum is not None:
            abs_hum_in = in_hum * in_temp / 100
            abs_hum_out = out_hum * out_temp / 100
            hum_diff = abs_hum_in - abs_hum_out
            score += min(max(int(hum_diff*10),0),20)
            reasons.append(f"Humidity difference inside-outside: {hum_diff:.1f}")

        # CO2
        if co2:
            if co2 > 1200:
                score += 40
                reasons.append(f"High CO2: {co2}")
            elif co2 > 900:
                score += 20
                reasons.append(f"Elevated CO2: {co2}")

        # PM2.5
        if pm25_in and pm25_out:
            if pm25_out < pm25_in:
                score += 10
                reasons.append("Indoor PM2.5 higher than outside")
            elif pm25_out > 20:
                score -= 20
                reasons.append("Outdoor PM2.5 high - ventilate less")

        # Heat index
        if heat_index and heat_index > 35:
            score += 10
            reasons.append(f"High indoor heat index: {heat_index}")

        # Wind
        if wind and 2 <= wind <= 8:
            score += 10
            reasons.append(f"Optimal wind: {wind} m/s")

        score = max(0, min(100, score))
        self._state = score

        if score >= 80:
            advice = "Optimal"
        elif score >= 60:
            advice = "Recommended"
        elif score >= 40:
            advice = "Neutral"
        else:
            advice = "Not Recommended"

        self._attr_extra_state_attributes = {
            "advice": advice,
            "reasons": reasons
        }