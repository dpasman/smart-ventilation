"""Per-area action guard: hold + lockout state machine for actuation.

Prevents sensor noise from flipping a physical actuator back and forth:
a changed proposal must be held stable for `hold_minutes` before it's
accepted, and once accepted it's locked in for `lockout_minutes` before a
*different* proposal can even start a new hold. A storm/weather-block/
condensation/CO2-override signal is `override=True` and bypasses both —
those are safety-critical and must never be delayed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class GuardState:
    """Persisted per-area actuation guard state."""

    accepted_action: str = "NONE"
    pending_action: str | None = None
    pending_since: datetime | None = None
    lockout_until: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted_action": self.accepted_action,
            "pending_action": self.pending_action,
            "pending_since": self.pending_since.isoformat() if self.pending_since else None,
            "lockout_until": self.lockout_until.isoformat() if self.lockout_until else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "GuardState":
        if not data:
            return cls()
        pending_since = data.get("pending_since")
        lockout_until = data.get("lockout_until")
        return cls(
            accepted_action=data.get("accepted_action", "NONE"),
            pending_action=data.get("pending_action"),
            pending_since=datetime.fromisoformat(pending_since) if pending_since else None,
            lockout_until=datetime.fromisoformat(lockout_until) if lockout_until else None,
        )


def evaluate(
    state: GuardState,
    proposed_action: str,
    now: datetime,
    hold_minutes: float,
    lockout_minutes: float,
    override: bool = False,
) -> tuple[str | None, GuardState]:
    """Return (action_to_execute_or_None, new_state).

    override=True: execute immediately, clear any pending hold, and arm a
    fresh lockout so a safety-critical action isn't immediately undone by a
    stale pending non-override proposal on the very next tick.

    Otherwise: a live lockout blocks every proposal, including a changed
    one; a proposal matching the already-accepted action clears any stale
    pending state as a no-op; a new/changed proposal (re)starts the hold
    timer; once held for >= hold_minutes, it's accepted and a fresh lockout
    is armed.
    """
    if override:
        return proposed_action, GuardState(
            accepted_action=proposed_action,
            pending_action=None,
            pending_since=None,
            lockout_until=_lockout_until(now, lockout_minutes),
        )

    if state.lockout_until is not None and now < state.lockout_until:
        return None, state

    if proposed_action == state.accepted_action:
        if state.pending_action is not None:
            return None, replace(state, pending_action=None, pending_since=None)
        return None, state

    if state.pending_action != proposed_action or state.pending_since is None:
        return None, replace(state, pending_action=proposed_action, pending_since=now)

    if now - state.pending_since < timedelta(minutes=hold_minutes):
        return None, state

    return proposed_action, GuardState(
        accepted_action=proposed_action,
        pending_action=None,
        pending_since=None,
        lockout_until=_lockout_until(now, lockout_minutes),
    )


def _lockout_until(now: datetime, lockout_minutes: float) -> datetime | None:
    if not lockout_minutes:
        return None
    return now + timedelta(minutes=lockout_minutes)
