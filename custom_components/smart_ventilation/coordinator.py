"""Coordinator for Smart Ventilation."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import actuator
from .action import derive_action
from .calculator import (
    VentilationCalculator,
    calculate_absolute_humidity,
    calculate_dew_point,
    calculate_heat_index,
    get_advice,
)
from .const import (
    CONF_AREA_NAME,
    CONF_INDOOR_CO2,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_PM25,
    CONF_INDOOR_TEMP,
    CONF_NOTIFICATION_COOLDOWN_MINUTES,
    CONF_NOTIFICATION_LANGUAGE,
    CONF_NOTIFICATIONS_ENABLED,
    CONF_OUTDOOR_ABS_HUMIDITY,
    CONF_OUTDOOR_DEW_POINT,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_PM25,
    CONF_OUTDOOR_TEMP,
    CONF_OUTDOOR_TEMP_MAX_24H,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    CONF_SEASON_BIAS,
    CONF_STABILITY_WINDOW_MINUTES,
    CONF_WEATHER_ENTITY,
    CONF_WIND_AVG,
    CONF_WIND_MAX,
    DEFAULT_NOTIFICATION_COOLDOWN_MINUTES,
    DEFAULT_NOTIFICATION_LANGUAGE,
    DEFAULT_QUIET_HOURS_END,
    DEFAULT_QUIET_HOURS_START,
    DEFAULT_SEASON_BIAS,
    DEFAULT_STABILITY_WINDOW_MINUTES,
    DOMAIN,
)
from .debounce import SignalDebouncer
from .diagnostics_monitor import is_area_misconfigured, sync_notification
from .notification_rules import build_signature, classify_severity, is_quiet_hours, should_notify
from .notification_text import build_advisory_message
from .weather import WeatherSignal, async_get_weather_signal

_LOGGER = logging.getLogger(__name__)

_AREA_EFFECTS_TIMEOUT_SECONDS = 10


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
        self._efficiency_history: dict[str, deque[float]] = {}
        # Set by __init__.py's async_setup_entry before the first refresh —
        # declared here only so attribute access below type-checks cleanly.
        self.runtime = None
        self.notifier = None

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch sensor states and calculate data for all configured areas."""
        outdoor = self._get_outdoor_data()
        settings = self.runtime.settings
        weather_signal = await async_get_weather_signal(
            self.hass, settings.get(CONF_WEATHER_ENTITY)
        )
        areas = self.entry.options.get("areas") or self.entry.data.get("areas", [])
        now = dt_util.now()
        data = {
            area[CONF_AREA_NAME]: self._get_area_data(area, outdoor, weather_signal, settings, now)
            for area in areas
        }

        for area in areas:
            area_name = area[CONF_AREA_NAME]
            try:
                await asyncio.wait_for(
                    self._async_handle_area_effects(area, data[area_name], settings, now),
                    timeout=_AREA_EFFECTS_TIMEOUT_SECONDS,
                )
            except Exception:  # noqa: BLE001
                # A broken automation entity or a slow/failing notify call
                # must never take down sensor data for every other area.
                _LOGGER.warning(
                    "Smart Ventilation: actuation/notification handling failed for %s",
                    area_name, exc_info=True,
                )

        return data

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

    def _read_wind_ms(self, entity_id: str | None) -> float | None:
        """Read a wind speed sensor and return the value normalized to m/s.

        Detects the unit_of_measurement attribute and converts km/h → m/s
        automatically so the calculator always works in m/s regardless of
        what the sensor reports.
        """
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            value = float(state.state)
        except (ValueError, TypeError):
            return None
        unit = state.attributes.get("unit_of_measurement", "")
        if unit in ("km/h", "km/u"):
            return round(value / 3.6, 2)
        return value

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

    def _get_area_data(
        self,
        area_config: dict,
        outdoor: dict[str, float | None],
        weather_signal: WeatherSignal | None,
        settings: dict[str, Any],
        now,
    ) -> dict[str, Any]:
        """Read area sensor states, run calculator, return result dict."""
        in_temp = self._read_state(area_config.get(CONF_INDOOR_TEMP))
        in_humidity = self._read_state(area_config.get(CONF_INDOOR_HUMIDITY))
        out_temp = outdoor["outdoor_temp"]

        in_hum_abs = None
        in_dew = None
        in_heat_index = None
        if in_temp is not None and in_humidity is not None:
            in_hum_abs = calculate_absolute_humidity(in_temp, in_humidity)
            in_dew = calculate_dew_point(in_temp, in_humidity)
            in_heat_index = calculate_heat_index(in_temp, in_humidity)

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
            weather_block=weather_signal.block if weather_signal else False,
            weather_caution=weather_signal.caution if weather_signal else False,
        )

        efficiency = self._smooth_efficiency(
            area_config[CONF_AREA_NAME], calc.calculate()
        )

        air_quality_result = calc.get_air_quality()
        comfort_result = calc.get_comfort()
        ventilation_reason = calc.get_ventilation_reason()
        action, action_override = derive_action(
            efficiency,
            calc.get_action_signals(),
            settings.get(CONF_SEASON_BIAS, DEFAULT_SEASON_BIAS),
            now=now,
        )

        cooling_recommended = (
            in_temp is not None
            and out_temp is not None
            and in_temp > 23
            and out_temp < in_temp - 1.5
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
            "air_quality_available": air_quality_result["available"],
            "air_quality_attributes": {
                "co2_category": air_quality_result["co2_category"],
                "pm25_category": air_quality_result["pm25_category"],
                "worst_parameter": air_quality_result["worst_parameter"],
            },
            "comfort": comfort_result["level"],
            "comfort_available": comfort_result["available"],
            "comfort_attributes": {
                "temperature_category": comfort_result["temperature_category"],
                "humidity_category": comfort_result["humidity_category"],
                "worst_parameter": comfort_result["worst_parameter"],
            },
            "ventilation_reason": ventilation_reason,
            "action": action,
            "action_override": action_override,
            "weather_condition": weather_signal.condition if weather_signal else None,
        }

    async def _async_handle_area_effects(
        self, area_config: dict, data: dict[str, Any], settings: dict[str, Any], now
    ) -> None:
        """Actuate and/or notify for one area, based on this tick's data.

        Actuation (via actuator.py) always runs regardless of notification
        settings — it's a physical/safety concern, not a notification-
        preference concern. Notifications are gated separately by
        notifications_enabled and quiet hours (an override still bypasses
        quiet hours, same as it bypasses the actuation hold/lockout).
        """
        area_name = area_config[CONF_AREA_NAME]
        action = data["action"]
        is_override = data["action_override"]

        sync_notification(
            self.hass,
            self.entry,
            area_name,
            is_area_misconfigured(area_config, settings),
            settings.get(CONF_NOTIFICATION_LANGUAGE, DEFAULT_NOTIFICATION_LANGUAGE),
        )

        await actuator.async_maybe_actuate(
            self.hass, area_config, self.runtime, self.notifier, action, is_override, now
        )

        if action == "NONE" and not is_override:
            return
        if not settings.get(CONF_NOTIFICATIONS_ENABLED, True):
            return

        quiet_hours_active = settings.get(
            CONF_QUIET_HOURS_ENABLED, True
        ) and is_quiet_hours(
            now.time(),
            _parse_time(settings.get(CONF_QUIET_HOURS_START), DEFAULT_QUIET_HOURS_START),
            _parse_time(settings.get(CONF_QUIET_HOURS_END), DEFAULT_QUIET_HOURS_END),
        )
        if quiet_hours_active and not is_override:
            return

        notify_state = self.runtime.area_state(area_name)["notify"]
        debouncer = SignalDebouncer(
            pending_value=notify_state.get("pending_signature"),
            pending_since=_parse_dt(notify_state.get("pending_since")),
            stable_value=notify_state.get("stable_signature"),
        )
        marker = {
            "last_signature": notify_state.get("last_signature"),
            "last_severity": notify_state.get("last_severity"),
            "last_notified_at": notify_state.get("last_notified_at"),
        }
        reason = data["ventilation_reason"]
        signature = build_signature(area_name, action)
        severity = classify_severity(data["efficiency"])

        should_send, new_debouncer = should_notify(
            marker,
            signature,
            severity,
            now,
            settings.get(CONF_NOTIFICATION_COOLDOWN_MINUTES, DEFAULT_NOTIFICATION_COOLDOWN_MINUTES),
            debouncer,
            settings.get(CONF_STABILITY_WINDOW_MINUTES, DEFAULT_STABILITY_WINDOW_MINUTES),
            override=is_override,
        )

        notify_patch = {
            "pending_signature": new_debouncer.pending_value,
            "pending_since": new_debouncer.pending_since.isoformat() if new_debouncer.pending_since else None,
            "stable_signature": new_debouncer.stable_value,
            "last_signature": notify_state.get("last_signature"),
            "last_reason": notify_state.get("last_reason"),
            "last_severity": notify_state.get("last_severity"),
            "last_notified_at": notify_state.get("last_notified_at"),
        }
        if should_send:
            message = build_advisory_message(
                area_name, action, reason, settings.get(CONF_NOTIFICATION_LANGUAGE, DEFAULT_NOTIFICATION_LANGUAGE)
            )
            sent = await self.notifier.async_send_advisory(area_name, message, severity)
            if sent:
                notify_patch.update(
                    last_signature=signature,
                    last_reason=reason,
                    last_severity=severity,
                    last_notified_at=now.isoformat(),
                )

        if notify_patch != notify_state:
            self.runtime.save_area_state(area_name, {"notify": notify_patch})

    async def async_send_recommendation_now(self, area_name: str) -> None:
        """Send the current recommendation for one area immediately.

        Bypasses the notification stability window, cooldown, and quiet
        hours — an explicit user action, not an ambient one. Still runs
        actuation through the normal actuator.async_maybe_actuate() path
        (hold/lockout and confirmation-required both still apply there;
        this button is a notification-noise bypass, not a safety bypass).
        """
        await self.async_request_refresh()
        data = (self.data or {}).get(area_name)
        if data is None:
            return
        areas = self.entry.options.get("areas") or self.entry.data.get("areas", [])
        area_config = next((a for a in areas if a[CONF_AREA_NAME] == area_name), None)
        if area_config is None:
            return

        action = data["action"]
        reason = data["ventilation_reason"]
        severity = classify_severity(data["efficiency"])
        signature = build_signature(area_name, action)
        now = dt_util.now()
        language = self.runtime.settings.get(CONF_NOTIFICATION_LANGUAGE, DEFAULT_NOTIFICATION_LANGUAGE)

        message = build_advisory_message(area_name, action, reason, language)
        sent = await self.notifier.async_send_advisory(area_name, message, severity)
        if sent:
            notify_state = self.runtime.area_state(area_name)["notify"]
            self.runtime.save_area_state(
                area_name,
                {
                    "notify": {
                        **notify_state,
                        "last_signature": signature,
                        "last_reason": reason,
                        "last_severity": severity,
                        "last_notified_at": now.isoformat(),
                    }
                },
            )

        await actuator.async_maybe_actuate(
            self.hass, area_config, self.runtime, self.notifier, action, data["action_override"], now
        )

    def _smooth_efficiency(self, area_name: str, raw: float) -> float:
        """3-reading rolling average to dampen sensor noise."""
        history = self._efficiency_history.setdefault(area_name, deque(maxlen=3))
        history.append(raw)
        return round(sum(history) / len(history), 1)

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


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _parse_time(value: str | None, default: str) -> time:
    parts = (value or default).split(":")
    if len(parts) == 2:
        parts.append("00")
    hour, minute, second = (int(p) for p in parts[:3])
    return time(hour, minute, second)
