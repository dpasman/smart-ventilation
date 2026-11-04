"""Generic "has this value been stable for N minutes" tracker — no HA imports.

Used independently for two different purposes with different durations:
- the per-area action-change-hold (don't flip an actuator on a one-tick blip)
- the global notification stability window (don't notify until advice settles)

Kept as two separate SignalDebouncer instances rather than one shared
concept, since flapping a physical actuator is a worse failure than an
extra notification, and a purely-advisory area (no actuator configured at
all) still wants notification debounce with no actuator hold whatsoever.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class SignalDebouncer:
    """Tracks whether `value` has been the same for at least `hold` minutes.

    Immutable: evaluate() returns (is_stable_and_changed, new_debouncer) —
    callers persist the returned debouncer, they don't mutate this one.
    """

    pending_value: Any = None
    pending_since: datetime | None = None
    stable_value: Any = None

    def evaluate(
        self, value: Any, now: datetime, hold_minutes: float
    ) -> tuple[bool, "SignalDebouncer"]:
        """Return (just_became_stable, new_state).

        `just_became_stable` is True only on the exact evaluation where
        `value` has been pending for >= hold_minutes and differs from the
        previously-accepted stable_value — i.e. once per transition, not
        on every tick while already stable.
        """
        if value == self.stable_value:
            # Already the accepted value — clear any stale pending value.
            if self.pending_value is not None or self.pending_since is not None:
                return False, SignalDebouncer(stable_value=self.stable_value)
            return False, self

        if self.pending_value != value:
            # New/changed proposal — (re)start the hold timer.
            return False, SignalDebouncer(
                pending_value=value, pending_since=now, stable_value=self.stable_value
            )

        assert self.pending_since is not None
        if now - self.pending_since < timedelta(minutes=hold_minutes):
            return False, self

        return True, SignalDebouncer(stable_value=value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pending_value": self.pending_value,
            "pending_since": self.pending_since.isoformat() if self.pending_since else None,
            "stable_value": self.stable_value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SignalDebouncer":
        if not data:
            return cls()
        pending_since = data.get("pending_since")
        return cls(
            pending_value=data.get("pending_value"),
            pending_since=datetime.fromisoformat(pending_since) if pending_since else None,
            stable_value=data.get("stable_value"),
        )
