"""Pure notification dedup/gating rules — no HA imports.

- build_signature(): a stable identity for "this area currently recommends
  this action", used to tell a genuinely new recommendation apart from a
  repeat of the one already notified about. Deliberately area+action only,
  NOT the free-text reason: the calculator's get_ventilation_reason() can
  flip between several near-equivalent reason strings (e.g. "Elevated
  CO2" <-> "High CO2 level" as a value hovers near a threshold) without
  the actual recommended action changing at all — including reason in the
  signature made every such flip look like a brand-new recommendation and
  bypass the cooldown, which was the direct cause of notification spam.
- is_quiet_hours(): a standalone time-of-day gate, evaluated separately from
  should_notify() so a safety-critical override can still bypass quiet
  hours at the call site without this module needing to know about it.
- should_notify(): combines the notification stability window (via a
  SignalDebouncer — don't notify on a signature that hasn't settled yet)
  with cooldown + severity-escalation + signature-change dedup against the
  last-sent marker.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from .debounce import SignalDebouncer

SEVERITY_NORMAL = "normal"
SEVERITY_ELEVATED = "elevated"
SEVERITY_URGENT = "urgent"

_URGENT_SCORE_THRESHOLD = 75
_ELEVATED_SCORE_THRESHOLD = 55


def build_signature(area_name: str, action: str) -> str:
    """Return a stable identity for one area's current recommended action.

    Area+action only — see the module docstring for why the reason text
    is deliberately excluded.
    """
    return f"{area_name}|{action}"


def classify_severity(score_0_to_100: float) -> str:
    """Bucket a 0-100 score so a material urgency jump can bypass cooldown."""
    if score_0_to_100 >= _URGENT_SCORE_THRESHOLD:
        return SEVERITY_URGENT
    if score_0_to_100 >= _ELEVATED_SCORE_THRESHOLD:
        return SEVERITY_ELEVATED
    return SEVERITY_NORMAL


def is_quiet_hours(now: time, start: time, end: time) -> bool:
    """Return whether `now` falls in the [start, end) quiet-hours window.

    Handles the common overnight case where start > end (e.g. 22:00-07:00)
    by wrapping around midnight. A zero-width window (start == end) is
    treated as "never quiet" rather than "always quiet".
    """
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def should_notify(
    marker: dict | None,
    signature: str,
    severity: str,
    now: datetime,
    cooldown_minutes: float,
    debouncer: SignalDebouncer,
    stability_minutes: float,
    override: bool = False,
) -> tuple[bool, SignalDebouncer]:
    """Return (should_notify, new_debouncer).

    override=True (storm/weather_block/condensation/CO2) only skips the
    stability wait — a safety-critical FIRST alert must never be delayed
    10 minutes for the signature to "settle". It does NOT skip the cooldown/
    marker dedup below: a condition that stays safety-critical for a
    while (e.g. CO2 sitting above the dangerous threshold for an hour)
    must not re-notify on every single poll tick forever — once the first
    alert is out, a persisting override still follows the normal cooldown
    pacing, same as everything else, unless severity escalates further.
    """
    if override:
        new_debouncer = SignalDebouncer(stable_value=signature)
    else:
        _, new_debouncer = debouncer.evaluate(signature, now, stability_minutes)
        if new_debouncer.stable_value != signature:
            return False, new_debouncer

    if marker is None or marker.get("last_signature") != signature:
        return True, new_debouncer

    if severity == SEVERITY_URGENT and marker.get("last_severity") != SEVERITY_URGENT:
        return True, new_debouncer

    last_notified_raw = marker.get("last_notified_at")
    if not last_notified_raw:
        return True, new_debouncer

    last_notified_at = (
        last_notified_raw if isinstance(last_notified_raw, datetime)
        else datetime.fromisoformat(last_notified_raw)
    )
    if now - last_notified_at >= timedelta(minutes=cooldown_minutes):
        return True, new_debouncer

    return False, new_debouncer
