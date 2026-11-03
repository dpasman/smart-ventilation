"""Turns an accepted OPEN/CLOSE action into an automation.trigger call.

Only OPEN and CLOSE are actuatable — VENTILATE/NONE have no associated
automation entity and are advisory-only. Flow per poll tick:

1. guard.evaluate() decides whether this tick's proposal is accepted yet
   (hold/lockout), or bypasses both on a safety override.
2. An accepted OPEN/CLOSE skips re-triggering if the configured window
   sensors already show the target state (idempotency).
3. If the area requires confirmation (and this isn't an override), a
   Companion App confirmation request is sent and the actuation happens
   later, asynchronously, when/if the user confirms — this function
   returns without having actuated anything yet in that case.
4. Otherwise (no confirmation required, or an override), actuate now.
"""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACTION_HOLD_MINUTES,
    CONF_ACTION_LOCKOUT_MINUTES,
    CONF_AREA_NAME,
    CONF_CONFIRMATION_REQUIRED,
    CONF_START_ENTITY,
    CONF_STOP_ENTITY,
    CONF_WINDOW_SENSORS,
    DEFAULT_ACTION_HOLD_MINUTES,
    DEFAULT_ACTION_LOCKOUT_MINUTES,
    DEFAULT_CONFIRMATION_REQUIRED,
)
from .guard import GuardState, evaluate as guard_evaluate
from .notification import NotificationManager
from .runtime import RuntimeStore

_LOGGER = logging.getLogger(__name__)

_ACTUATABLE = {"OPEN", "CLOSE"}


async def async_maybe_actuate(
    hass: HomeAssistant,
    area_config: dict,
    runtime: RuntimeStore,
    notifier: NotificationManager,
    action: str,
    is_override: bool,
    now: datetime,
) -> None:
    """Evaluate and, if accepted and due, actuate one area's automation."""
    area_name = area_config[CONF_AREA_NAME]
    hold_minutes = area_config.get(CONF_ACTION_HOLD_MINUTES, DEFAULT_ACTION_HOLD_MINUTES)
    lockout_minutes = area_config.get(CONF_ACTION_LOCKOUT_MINUTES, DEFAULT_ACTION_LOCKOUT_MINUTES)

    area_state = runtime.area_state(area_name)
    guard_state = GuardState.from_dict(area_state["guard"])
    to_execute, new_guard_state = guard_evaluate(
        guard_state, action, now, hold_minutes, lockout_minutes, override=is_override
    )
    if new_guard_state != guard_state:
        runtime.save_area_state(area_name, {"guard": new_guard_state.to_dict()})

    if to_execute not in _ACTUATABLE:
        return

    automation_entity = (
        area_config.get(CONF_START_ENTITY) if to_execute == "OPEN" else area_config.get(CONF_STOP_ENTITY)
    )
    if not automation_entity:
        return

    if _window_state_already_matches(hass, area_config.get(CONF_WINDOW_SENSORS) or [], to_execute):
        return

    confirmation_required = area_config.get(CONF_CONFIRMATION_REQUIRED, DEFAULT_CONFIRMATION_REQUIRED)
    if is_override or not confirmation_required:
        await _async_trigger(hass, automation_entity)
        return

    async def _on_resolved(confirmed: bool) -> None:
        if confirmed:
            await _async_trigger(hass, automation_entity)

    message = _confirmation_message(area_name, to_execute)
    await notifier.async_send_confirmation_request(area_name, to_execute, message, _on_resolved)


def _window_state_already_matches(hass: HomeAssistant, window_sensor_ids: list[str], action: str) -> bool:
    """Return True if the configured window sensors already reflect `action`.

    No window sensors configured means "unknown" — never skip on that basis.
    """
    if not window_sensor_ids:
        return False
    states = [hass.states.get(entity_id) for entity_id in window_sensor_ids]
    known_states = [s for s in states if s is not None and s.state in ("on", "off")]
    if not known_states:
        return False
    any_open = any(s.state == "on" for s in known_states)
    if action == "OPEN":
        return any_open
    return not any_open  # CLOSE: idempotent only once every known sensor reports closed


async def _async_trigger(hass: HomeAssistant, automation_entity: str) -> None:
    try:
        await hass.services.async_call(
            "automation", "trigger", {"skip_condition": False}, target={"entity_id": automation_entity},
            blocking=True,
        )
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Smart Ventilation: could not trigger %s", automation_entity, exc_info=True)


def _confirmation_message(area_name: str, action: str) -> str:
    if action == "OPEN":
        return f"{area_name}: open the window? Smart Ventilation recommends it now."
    return f"{area_name}: close the window? Smart Ventilation recommends it now."
