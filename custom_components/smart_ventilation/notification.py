"""Notification delivery + companion-app confirmation flow.

NotificationManager sends plain advisory notifications and, for an area
configured to require confirmation before actuation, sends an actionable
Companion App notification and waits for an explicit tap before letting
actuator.py proceed. It never actuates anything itself — it only tracks
pending confirmation tokens and hands a confirmed/expired/dismissed result
back to whoever is waiting (actuator.py).
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later
from homeassistant.util import slugify

from .const import CONF_NOTIFICATION_DEVICE_IDS, CONFIRMATION_TOKEN_TTL_MINUTES
from .runtime import RuntimeStore

_LOGGER = logging.getLogger(__name__)

_MOBILE_APP_NOTIFICATION_ACTION_EVENT = "mobile_app_notification_action"
_CONFIRM_PREFIX = "sv_confirm_"
_DISMISS_PREFIX = "sv_dismiss_"


class NotificationManager:
    """Sends notifications and tracks companion-app confirmation tokens."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, runtime: RuntimeStore) -> None:
        self.hass = hass
        self.entry = entry
        self.runtime = runtime
        # token -> {"area_name": str, "action": str, "on_resolved": Callable}
        self._pending: dict[str, dict[str, Any]] = {}
        self._bus_unsub: Callable[[], None] | None = None

    def async_setup(self) -> Callable[[], None]:
        """Register the bus listener once per config entry; returns the unsub."""
        self._bus_unsub = self.hass.bus.async_listen(
            _MOBILE_APP_NOTIFICATION_ACTION_EVENT, self._handle_notification_action
        )

        def _unsub() -> None:
            if self._bus_unsub is not None:
                self._bus_unsub()
                self._bus_unsub = None
            self._pending.clear()

        return _unsub

    async def async_send_advisory(self, area_name: str, message: str, severity: str) -> bool:
        """Send a plain (non-actionable) notification for one area."""
        targets = self._notify_targets()
        if not targets:
            return False
        sent = False
        for service in targets:
            try:
                await self.hass.services.async_call(
                    "notify", service, {"title": "Smart Ventilation", "message": message}, blocking=True,
                )
                sent = True
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Smart Ventilation: notify.%s failed", service, exc_info=True)
        return sent

    async def async_send_confirmation_request(
        self,
        area_name: str,
        action: str,
        message: str,
        on_resolved: Callable[[bool], Any],
    ) -> str | None:
        """Send an actionable confirmation notification; returns the token, or None if undeliverable.

        `on_resolved(confirmed: bool)` is an async callable invoked exactly
        once — on an explicit Confirm/Dismiss tap, or on TTL expiry (treated
        as an implicit decline, confirmed=False) — scheduled as a background
        task, never awaited inline from the bus-event callback.
        """
        targets = self._notify_targets()
        if not targets:
            return None

        token = secrets.token_hex(8)
        confirm_action = f"{_CONFIRM_PREFIX}{token}"
        dismiss_action = f"{_DISMISS_PREFIX}{token}"

        sent = False
        for service in targets:
            try:
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {
                        "title": "Smart Ventilation",
                        "message": message,
                        "data": {
                            "actions": [
                                {"action": confirm_action, "title": "Confirm"},
                                {"action": dismiss_action, "title": "Dismiss"},
                            ]
                        },
                    },
                    blocking=True,
                )
                sent = True
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Smart Ventilation: notify.%s failed", service, exc_info=True)

        if not sent:
            return None

        self._pending[token] = {"area_name": area_name, "action": action, "on_resolved": on_resolved}
        async_call_later(
            self.hass, timedelta(minutes=CONFIRMATION_TOKEN_TTL_MINUTES), self._expire(token)
        )
        return token

    def _notify_targets(self) -> list[str]:
        """Return configured notify.* service names (without the "notify." prefix).

        Resolved from the configured mobile_app device(s) via the long-
        standing `notify.mobile_app_<slugified device name>` convention,
        rather than an entity-registry lookup — stable across HA versions
        and doesn't depend on the newer per-entity notify platform being
        populated for every mobile_app device.
        """
        device_ids = self.runtime.settings.get(CONF_NOTIFICATION_DEVICE_IDS) or ()
        device_reg = dr.async_get(self.hass)
        services: list[str] = []
        for device_id in device_ids:
            device = device_reg.async_get(device_id)
            if device is None or not device.name:
                continue
            services.append(f"mobile_app_{slugify(device.name)}")
        return services

    @callback
    def _handle_notification_action(self, event: Event) -> None:
        action = event.data.get("action")
        if not isinstance(action, str):
            return
        if action.startswith(_CONFIRM_PREFIX):
            token = action[len(_CONFIRM_PREFIX):]
            self._resolve(token, confirmed=True)
        elif action.startswith(_DISMISS_PREFIX):
            token = action[len(_DISMISS_PREFIX):]
            self._resolve(token, confirmed=False)

    def _resolve(self, token: str, confirmed: bool) -> None:
        # pop (not get) so a confirm/dismiss race with the TTL timeout can
        # only ever invoke on_resolved once.
        entry = self._pending.pop(token, None)
        if entry is None:
            return
        self.hass.async_create_task(entry["on_resolved"](confirmed))

    def _expire(self, token: str) -> Callable[[Any], None]:
        @callback
        def _on_timeout(_now: Any) -> None:
            # Timeout is an implicit decline — never actuate on timeout.
            self._resolve(token, confirmed=False)

        return _on_timeout
