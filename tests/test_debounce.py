"""Tests for SignalDebouncer: stability transitions and serialization."""

from datetime import datetime, timedelta, timezone

from custom_components.smart_ventilation.debounce import SignalDebouncer

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestEvaluate:
    def test_first_proposal_is_not_immediately_stable(self):
        d = SignalDebouncer()
        stable, new_d = d.evaluate("OPEN", T0, hold_minutes=5)
        assert stable is False
        assert new_d.pending_value == "OPEN"
        assert new_d.pending_since == T0

    def test_value_matching_initial_default_stable_value_is_a_noop(self):
        # stable_value defaults to None; proposing None matches it immediately.
        d = SignalDebouncer()
        stable, new_d = d.evaluate(None, T0, hold_minutes=5)
        assert stable is False
        assert new_d is d

    def test_held_long_enough_becomes_stable(self):
        d = SignalDebouncer()
        _, d = d.evaluate("OPEN", T0, hold_minutes=5)
        stable, d = d.evaluate("OPEN", T0 + timedelta(minutes=5, seconds=1), hold_minutes=5)
        assert stable is True
        assert d.stable_value == "OPEN"
        assert d.pending_value is None

    def test_not_yet_held_long_enough_stays_pending(self):
        d = SignalDebouncer()
        _, d = d.evaluate("OPEN", T0, hold_minutes=5)
        stable, d = d.evaluate("OPEN", T0 + timedelta(minutes=4), hold_minutes=5)
        assert stable is False
        assert d.pending_value == "OPEN"

    def test_exactly_at_boundary_is_stable(self):
        # "held for >= hold_minutes" includes the exact boundary.
        d = SignalDebouncer()
        _, d = d.evaluate("OPEN", T0, hold_minutes=5)
        stable, d = d.evaluate("OPEN", T0 + timedelta(minutes=5), hold_minutes=5)
        assert stable is True

    def test_one_second_short_of_boundary_is_not_yet_stable(self):
        d = SignalDebouncer()
        _, d = d.evaluate("OPEN", T0, hold_minutes=5)
        stable, d = d.evaluate("OPEN", T0 + timedelta(minutes=5) - timedelta(seconds=1), hold_minutes=5)
        assert stable is False

    def test_changed_proposal_restarts_the_hold_timer(self):
        d = SignalDebouncer()
        _, d = d.evaluate("OPEN", T0, hold_minutes=5)
        # Almost stable, then the proposal changes to CLOSE
        _, d = d.evaluate("CLOSE", T0 + timedelta(minutes=4), hold_minutes=5)
        assert d.pending_value == "CLOSE"
        assert d.pending_since == T0 + timedelta(minutes=4)
        # Old elapsed time doesn't carry over
        stable, d = d.evaluate("CLOSE", T0 + timedelta(minutes=8, seconds=59), hold_minutes=5)
        assert stable is False

    def test_already_stable_value_resubmitted_stays_stable_and_clears_pending(self):
        d = SignalDebouncer()
        _, d = d.evaluate("OPEN", T0, hold_minutes=5)
        _, d = d.evaluate("OPEN", T0 + timedelta(minutes=6), hold_minutes=5)
        assert d.stable_value == "OPEN"
        stable, d = d.evaluate("OPEN", T0 + timedelta(minutes=7), hold_minutes=5)
        assert stable is False
        assert d.pending_value is None
        assert d.pending_since is None

    def test_transition_away_from_stable_value_starts_new_hold(self):
        d = SignalDebouncer()
        _, d = d.evaluate("OPEN", T0, hold_minutes=5)
        _, d = d.evaluate("OPEN", T0 + timedelta(minutes=6), hold_minutes=5)
        assert d.stable_value == "OPEN"
        stable, d = d.evaluate("CLOSE", T0 + timedelta(minutes=7), hold_minutes=5)
        assert stable is False
        assert d.pending_value == "CLOSE"
        assert d.stable_value == "OPEN"  # old stable value retained until the new one settles


class TestSerialization:
    def test_round_trip_pending_state(self):
        d = SignalDebouncer(pending_value="OPEN", pending_since=T0, stable_value=None)
        restored = SignalDebouncer.from_dict(d.to_dict())
        assert restored == d

    def test_round_trip_stable_state(self):
        d = SignalDebouncer(stable_value="CLOSE")
        restored = SignalDebouncer.from_dict(d.to_dict())
        assert restored == d

    def test_from_dict_handles_none_and_empty(self):
        assert SignalDebouncer.from_dict(None) == SignalDebouncer()
        assert SignalDebouncer.from_dict({}) == SignalDebouncer()

    def test_round_trip_preserves_behavior_across_a_simulated_restart(self):
        d = SignalDebouncer()
        _, d = d.evaluate("OPEN", T0, hold_minutes=5)
        restored = SignalDebouncer.from_dict(d.to_dict())
        stable, restored = restored.evaluate("OPEN", T0 + timedelta(minutes=5, seconds=1), hold_minutes=5)
        assert stable is True
        assert restored.stable_value == "OPEN"
