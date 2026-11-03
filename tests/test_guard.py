"""Tests for the per-area action guard: hold, lockout, override."""

from datetime import datetime, timedelta, timezone

from custom_components.smart_ventilation.guard import GuardState, evaluate

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
HOLD = 5
LOCKOUT = 20


class TestFreshState:
    def test_first_proposal_starts_a_hold_not_executed_yet(self):
        action, state = evaluate(GuardState(), "OPEN", T0, HOLD, LOCKOUT)
        assert action is None
        assert state.pending_action == "OPEN"
        assert state.pending_since == T0

    def test_proposal_matching_initial_accepted_none_is_a_noop(self):
        action, state = evaluate(GuardState(), "NONE", T0, HOLD, LOCKOUT)
        assert action is None
        assert state == GuardState()


class TestHold:
    def test_held_long_enough_is_accepted_and_arms_lockout(self):
        _, state = evaluate(GuardState(), "OPEN", T0, HOLD, LOCKOUT)
        action, state = evaluate(state, "OPEN", T0 + timedelta(minutes=HOLD), HOLD, LOCKOUT)
        assert action == "OPEN"
        assert state.accepted_action == "OPEN"
        assert state.lockout_until == T0 + timedelta(minutes=HOLD) + timedelta(minutes=LOCKOUT)

    def test_not_held_long_enough_executes_nothing(self):
        _, state = evaluate(GuardState(), "OPEN", T0, HOLD, LOCKOUT)
        action, state = evaluate(state, "OPEN", T0 + timedelta(minutes=HOLD - 1), HOLD, LOCKOUT)
        assert action is None
        assert state.pending_action == "OPEN"

    def test_changed_proposal_mid_hold_restarts_the_timer(self):
        _, state = evaluate(GuardState(), "OPEN", T0, HOLD, LOCKOUT)
        _, state = evaluate(state, "CLOSE", T0 + timedelta(minutes=3), HOLD, LOCKOUT)
        assert state.pending_action == "CLOSE"
        assert state.pending_since == T0 + timedelta(minutes=3)
        action, state = evaluate(state, "CLOSE", T0 + timedelta(minutes=7, seconds=59), HOLD, LOCKOUT)
        assert action is None  # only ~5 min elapsed since the restart, not since T0


class TestLockout:
    def test_lockout_blocks_a_changed_proposal_entirely(self):
        accepted_state = GuardState(accepted_action="OPEN", lockout_until=T0 + timedelta(minutes=LOCKOUT))
        action, state = evaluate(accepted_state, "CLOSE", T0 + timedelta(minutes=1), HOLD, LOCKOUT)
        assert action is None
        assert state == accepted_state  # proposal not even registered as pending

    def test_proposal_after_lockout_expires_starts_a_fresh_hold(self):
        accepted_state = GuardState(accepted_action="OPEN", lockout_until=T0 + timedelta(minutes=LOCKOUT))
        action, state = evaluate(
            accepted_state, "CLOSE", T0 + timedelta(minutes=LOCKOUT, seconds=1), HOLD, LOCKOUT
        )
        assert action is None
        assert state.pending_action == "CLOSE"

    def test_matching_accepted_action_is_allowed_during_lockout(self):
        accepted_state = GuardState(accepted_action="OPEN", lockout_until=T0 + timedelta(minutes=LOCKOUT))
        action, state = evaluate(accepted_state, "OPEN", T0 + timedelta(minutes=1), HOLD, LOCKOUT)
        assert action is None  # no new actuation needed, already in that state
        assert state == accepted_state

    def test_zero_lockout_minutes_means_no_lockout(self):
        _, state = evaluate(GuardState(), "OPEN", T0, HOLD, 0)
        action, state = evaluate(state, "OPEN", T0 + timedelta(minutes=HOLD), HOLD, 0)
        assert action == "OPEN"
        assert state.lockout_until is None
        # immediately proposing something else is allowed, no lockout active
        action, state = evaluate(state, "CLOSE", T0 + timedelta(minutes=HOLD, seconds=1), HOLD, 0)
        assert action is None
        assert state.pending_action == "CLOSE"


class TestOverride:
    def test_override_executes_immediately_ignoring_hold(self):
        action, state = evaluate(GuardState(), "CLOSE", T0, HOLD, LOCKOUT, override=True)
        assert action == "CLOSE"
        assert state.accepted_action == "CLOSE"
        assert state.pending_action is None

    def test_override_bypasses_an_active_lockout(self):
        accepted_state = GuardState(accepted_action="OPEN", lockout_until=T0 + timedelta(minutes=LOCKOUT))
        action, state = evaluate(
            accepted_state, "CLOSE", T0 + timedelta(minutes=1), HOLD, LOCKOUT, override=True
        )
        assert action == "CLOSE"
        assert state.accepted_action == "CLOSE"

    def test_override_rearms_a_fresh_lockout(self):
        action, state = evaluate(GuardState(), "CLOSE", T0, HOLD, LOCKOUT, override=True)
        assert state.lockout_until == T0 + timedelta(minutes=LOCKOUT)
        # A stale non-override proposal right after must not undo it.
        action2, state2 = evaluate(state, "OPEN", T0 + timedelta(seconds=1), HOLD, LOCKOUT)
        assert action2 is None
        assert state2.accepted_action == "CLOSE"

    def test_override_clears_a_preexisting_pending_proposal(self):
        pending_state = GuardState(pending_action="OPEN", pending_since=T0)
        action, state = evaluate(pending_state, "CLOSE", T0 + timedelta(minutes=1), HOLD, LOCKOUT, override=True)
        assert action == "CLOSE"
        assert state.pending_action is None
        assert state.pending_since is None


class TestSerialization:
    def test_round_trip(self):
        state = GuardState(
            accepted_action="OPEN",
            pending_action="CLOSE",
            pending_since=T0,
            lockout_until=T0 + timedelta(minutes=LOCKOUT),
        )
        assert GuardState.from_dict(state.to_dict()) == state

    def test_from_dict_handles_none_and_empty(self):
        assert GuardState.from_dict(None) == GuardState()
        assert GuardState.from_dict({}) == GuardState()
