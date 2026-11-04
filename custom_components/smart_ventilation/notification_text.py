"""Localizes the text that goes INTO a sent notification.

This is deliberately separate from HA's own translation system
(strings.json/translations/*.json): that system translates entity NAMES
and STATES for the dashboard, driven by each viewer's own HA profile
language — it has no effect on the plain text a notify.* service call
sends to a phone. A household where HA's own profile is set to English
but the resident wants their push notifications in Dutch needs the
*notification* language to be its own explicit choice (the
notification_language global setting), independent of the HA profile
language. Falls back to English for any value this module doesn't
recognize, rather than raising.
"""

from __future__ import annotations

LANGUAGE_EN = "en"
LANGUAGE_NL = "nl"
NOTIFICATION_LANGUAGE_OPTIONS = [LANGUAGE_EN, LANGUAGE_NL]

_ACTION_LABELS: dict[str, dict[str, str]] = {
    "OPEN": {"en": "open", "nl": "openen"},
    "CLOSE": {"en": "close", "nl": "sluiten"},
    "VENTILATE": {"en": "ventilate briefly", "nl": "kort luchten"},
    "NONE": {"en": "no action", "nl": "geen actie"},
}

_REASON_LABELS: dict[str, dict[str, str]] = {
    "Adverse weather": {"en": "Adverse weather", "nl": "Slecht weer"},
    "Condensation risk": {"en": "Condensation risk", "nl": "Condensrisico"},
    "Conditions balanced": {"en": "Conditions balanced", "nl": "Condities in balans"},
    "Cooling conditions favorable": {
        "en": "Cooling conditions favorable", "nl": "Gunstige koelcondities",
    },
    "Dangerously high CO2": {"en": "Dangerously high CO2", "nl": "Gevaarlijk hoge CO2"},
    "Elevated CO2": {"en": "Elevated CO2", "nl": "Verhoogde CO2"},
    "Good air quality": {"en": "Good air quality", "nl": "Goede luchtkwaliteit"},
    "Good ventilation conditions": {
        "en": "Good ventilation conditions", "nl": "Goede ventilatiecondities",
    },
    "High CO2 level": {"en": "High CO2 level", "nl": "Hoog CO2-niveau"},
    "High indoor humidity": {
        "en": "High indoor humidity", "nl": "Hoge luchtvochtigheid binnen",
    },
    "Indoor too warm": {"en": "Indoor too warm", "nl": "Binnen te warm"},
    "Outdoor air too cold": {"en": "Outdoor air too cold", "nl": "Buitenlucht te koud"},
    "Outdoor air too hot": {"en": "Outdoor air too hot", "nl": "Buitenlucht te warm"},
    "Outdoor humidity too high": {
        "en": "Outdoor humidity too high", "nl": "Luchtvochtigheid buiten te hoog",
    },
    "Outdoor PM2.5 too high": {"en": "Outdoor PM2.5 too high", "nl": "PM2.5 buiten te hoog"},
    "Storm warning": {"en": "Storm warning", "nl": "Stormwaarschuwing"},
    "Weather conditions deteriorating soon": {
        "en": "Weather conditions deteriorating soon", "nl": "Weer verslechtert binnenkort",
    },
}

_UI_LABELS: dict[str, dict[str, str]] = {
    "confirm": {"en": "Confirm", "nl": "Bevestigen"},
    "dismiss": {"en": "Dismiss", "nl": "Afwijzen"},
    "confirm_open_title": {"en": "Confirm opening", "nl": "Bevestig openen"},
    "confirm_close_title": {"en": "Confirm closing", "nl": "Bevestig sluiten"},
}


def _lookup(table: dict[str, dict[str, str]], key: str, language: str) -> str:
    entry = table.get(key)
    if entry is None:
        return key  # unknown value — show it verbatim rather than raise
    return entry.get(language) or entry["en"]


def translate_action(action: str, language: str) -> str:
    return _lookup(_ACTION_LABELS, action, language)


def translate_reason(reason: str, language: str) -> str:
    return _lookup(_REASON_LABELS, reason, language)


def ui_label(key: str, language: str) -> str:
    return _lookup(_UI_LABELS, key, language)


def build_advisory_message(area_name: str, action: str, reason: str, language: str) -> str:
    return (
        f"{area_name}: {translate_action(action, language)} "
        f"— {translate_reason(reason, language)}"
    )


def build_confirmation_message(area_name: str, action: str, language: str) -> str:
    if language == LANGUAGE_NL:
        verb = "het raam openen" if action == "OPEN" else "het raam sluiten"
        return f"{area_name}: {verb}? Smart Ventilation adviseert dit nu."
    verb = "open the window" if action == "OPEN" else "close the window"
    return f"{area_name}: {verb}? Smart Ventilation recommends it now."
