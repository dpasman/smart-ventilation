"""Surfaces otherwise-silent misconfiguration as a persistent notification.

The one case this currently detects: an area has an actuation automation
configured and requires confirmation before using it, but no notification
device is configured to actually deliver that confirmation request — the
area would recommend OPEN/CLOSE forever and never actually act, with
nothing visible telling the user why.
"""

from __future__ import annotations

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_AREA_NAME,
    CONF_CONFIRMATION_REQUIRED,
    CONF_NOTIFICATION_DEVICE_IDS,
    CONF_START_ENTITY,
    CONF_STOP_ENTITY,
    DEFAULT_CONFIRMATION_REQUIRED,
    DEFAULT_NOTIFICATION_LANGUAGE,
    DOMAIN,
)
from .notification_text import LANGUAGE_NL

CONFIRMATION_UNREACHABLE = "confirmation_unreachable"


def is_area_misconfigured(area_config: dict, settings: dict) -> str | None:
    """Return a stable diagnostic reason code for one area, or None if fine."""
    has_automation = bool(area_config.get(CONF_START_ENTITY) or area_config.get(CONF_STOP_ENTITY))
    if not has_automation:
        return None
    confirmation_required = area_config.get(CONF_CONFIRMATION_REQUIRED, DEFAULT_CONFIRMATION_REQUIRED)
    if not confirmation_required:
        return None
    has_notify_targets = bool(settings.get(CONF_NOTIFICATION_DEVICE_IDS))
    if not has_notify_targets:
        return CONFIRMATION_UNREACHABLE
    return None


def sync_notification(
    hass: HomeAssistant,
    entry: ConfigEntry,
    area_name: str,
    reason: str | None,
    language: str = DEFAULT_NOTIFICATION_LANGUAGE,
) -> None:
    """Create or dismiss the persistent notification for one area's diagnostic state."""
    notification_id = _notification_id(entry, area_name)
    if reason is None:
        persistent_notification.async_dismiss(hass, notification_id)
        return
    title, message = _build_message(area_name, reason, language)
    persistent_notification.async_create(hass, message, title=title, notification_id=notification_id)


def _notification_id(entry: ConfigEntry, area_name: str) -> str:
    return f"{DOMAIN}_{entry.entry_id}_{area_name}_diagnostic"


def _build_message(area_name: str, reason: str, language: str) -> tuple[str, str]:
    if reason == CONFIRMATION_UNREACHABLE:
        if language == LANGUAGE_NL:
            return (
                "Smart Ventilation: bevestiging onbereikbaar",
                (
                    f"{area_name} heeft een open/dicht-automatisering geconfigureerd en "
                    "vereist bevestiging voordat die wordt gebruikt, maar er is geen "
                    "meldingsapparaat ingesteld bij Algemene instellingen — de actie "
                    "wordt dus nooit daadwerkelijk uitgevoerd. Voeg een meldingsapparaat "
                    "toe, of zet \"Bevestiging vereist voor actie\" uit voor deze ruimte."
                ),
            )
        return (
            "Smart Ventilation: unreachable confirmation",
            (
                f"{area_name} has an open/close automation configured and requires "
                "confirmation before using it, but no notification device is "
                "configured under Global Settings — it will never actually be "
                "triggered. Either add a notification device, or turn off "
                "\"Require Confirmation Before Acting\" for this area."
            ),
        )
    return ("Smart Ventilation", f"{area_name}: {reason}")
