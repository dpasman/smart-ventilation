"""Tests for notification_rules: signatures, quiet hours, should_notify."""

from datetime import datetime, time, timedelta, timezone

from custom_components.smart_ventilation.debounce import SignalDebouncer
from custom_components.smart_ventilation.notification_rules import (
    build_signature,
    classify_severity,
    is_quiet_hours,
    should_notify,
)

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
STABILITY = 10
COOLDOWN = 60


class TestBuildSignature:
    def test_distinct_areas_or_actions_produce_distinct_signatures(self):
        a = build_signature("Keuken", "OPEN")
        b = build_signature("Badkamer", "OPEN")
        c = build_signature("Keuken", "CLOSE")
        assert len({a, b, c}) == 3

    def test_identical_inputs_produce_identical_signatures(self):
        # Also demonstrates the point of dropping reason from the
        # signature: a reason-text flip alone (not modeled here, since the
        # parameter no longer exists) can never change the identity of
        # "this area recommends this action" — only area or action can.
        assert build_signature("Keuken", "OPEN") == build_signature("Keuken", "OPEN")


class TestClassifySeverity:
    def test_thresholds(self):
        assert classify_severity(54.9) == "normal"
        assert classify_severity(55.0) == "elevated"
        assert classify_severity(74.0) == "elevated"
        assert classify_severity(75.0) == "urgent"
        assert classify_severity(100.0) == "urgent"


class TestIsQuietHours:
    def test_same_day_window(self):
        assert is_quiet_hours(time(13, 0), time(12, 0), time(14, 0)) is True
        assert is_quiet_hours(time(11, 0), time(12, 0), time(14, 0)) is False
        assert is_quiet_hours(time(14, 0), time(12, 0), time(14, 0)) is False  # end exclusive

    def test_overnight_wraparound_window(self):
        assert is_quiet_hours(time(23, 0), time(22, 0), time(7, 0)) is True
        assert is_quiet_hours(time(3, 0), time(22, 0), time(7, 0)) is True
        assert is_quiet_hours(time(12, 0), time(22, 0), time(7, 0)) is False
        assert is_quiet_hours(time(22, 0), time(22, 0), time(7, 0)) is True  # start inclusive
        assert is_quiet_hours(time(7, 0), time(22, 0), time(7, 0)) is False  # end exclusive

    def test_zero_width_window_is_never_quiet(self):
        assert is_quiet_hours(time(5, 0), time(22, 0), time(22, 0)) is False


class TestShouldNotify:
    def test_override_sends_immediately_ignoring_stability_window(self):
        d = SignalDebouncer()
        result, _ = should_notify(
            marker=None, signature="sig", severity="urgent", now=T0,
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY, override=True,
        )
        assert result is True

    def test_override_still_respects_cooldown_once_a_marker_exists(self):
        # Regression test: a persisting safety-critical condition (e.g. CO2
        # stuck above the dangerous threshold) must NOT re-notify on every
        # single poll tick forever — override only buys skipping the
        # stability wait for the first alert, not an indefinite cooldown
        # bypass.
        marker = {"last_signature": "sig", "last_severity": "urgent", "last_notified_at": T0.isoformat()}
        d = SignalDebouncer()
        result, _ = should_notify(
            marker=marker, signature="sig", severity="urgent", now=T0 + timedelta(minutes=1),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY, override=True,
        )
        assert result is False

    def test_override_bypasses_cooldown_on_further_severity_escalation(self):
        marker = {"last_signature": "sig", "last_severity": "elevated", "last_notified_at": T0.isoformat()}
        d = SignalDebouncer()
        result, _ = should_notify(
            marker=marker, signature="sig", severity="urgent", now=T0 + timedelta(minutes=1),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY, override=True,
        )
        assert result is True

    def test_override_notifies_again_once_the_normal_cooldown_elapses(self):
        marker = {"last_signature": "sig", "last_severity": "urgent", "last_notified_at": T0.isoformat()}
        d = SignalDebouncer()
        result, _ = should_notify(
            marker=marker, signature="sig", severity="urgent", now=T0 + timedelta(minutes=COOLDOWN + 1),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY, override=True,
        )
        assert result is True

    def test_override_with_a_changed_signature_notifies_immediately(self):
        # A storm replacing a CO2 alert, say — genuinely new, no reason to wait.
        marker = {"last_signature": "old-sig", "last_severity": "urgent", "last_notified_at": T0.isoformat()}
        d = SignalDebouncer()
        result, _ = should_notify(
            marker=marker, signature="new-sig", severity="urgent", now=T0 + timedelta(minutes=1),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY, override=True,
        )
        assert result is True

    def test_unsettled_signature_does_not_notify(self):
        d = SignalDebouncer()
        result, d = should_notify(
            marker=None, signature="sig", severity="normal", now=T0,
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY,
        )
        assert result is False

    def test_settled_new_signature_with_no_marker_notifies(self):
        d = SignalDebouncer()
        _, d = should_notify(
            marker=None, signature="sig", severity="normal", now=T0,
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY,
        )
        result, d = should_notify(
            marker=None, signature="sig", severity="normal", now=T0 + timedelta(minutes=STABILITY),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY,
        )
        assert result is True

    def test_same_signature_within_cooldown_is_suppressed(self):
        marker = {"last_signature": "sig", "last_severity": "normal", "last_notified_at": T0.isoformat()}
        d = SignalDebouncer(stable_value="sig")
        result, _ = should_notify(
            marker=marker, signature="sig", severity="normal", now=T0 + timedelta(minutes=30),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY,
        )
        assert result is False

    def test_same_signature_after_cooldown_elapses_notifies_again(self):
        marker = {"last_signature": "sig", "last_severity": "normal", "last_notified_at": T0.isoformat()}
        d = SignalDebouncer(stable_value="sig")
        result, _ = should_notify(
            marker=marker, signature="sig", severity="normal", now=T0 + timedelta(minutes=COOLDOWN + 1),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY,
        )
        assert result is True

    def test_changed_signature_bypasses_cooldown_once_settled(self):
        marker = {"last_signature": "old-sig", "last_severity": "normal", "last_notified_at": T0.isoformat()}
        d = SignalDebouncer(stable_value="old-sig")
        # New signature proposed — not settled yet on this tick
        result, d = should_notify(
            marker=marker, signature="new-sig", severity="normal", now=T0 + timedelta(minutes=1),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY,
        )
        assert result is False
        # Settled after the stability window
        result, d = should_notify(
            marker=marker, signature="new-sig", severity="normal", now=T0 + timedelta(minutes=1 + STABILITY),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY,
        )
        assert result is True

    def test_severity_escalation_to_urgent_bypasses_cooldown(self):
        marker = {"last_signature": "sig", "last_severity": "normal", "last_notified_at": T0.isoformat()}
        d = SignalDebouncer(stable_value="sig")
        result, _ = should_notify(
            marker=marker, signature="sig", severity="urgent", now=T0 + timedelta(minutes=5),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY,
        )
        assert result is True

    def test_already_urgent_marker_does_not_re_bypass_on_still_urgent(self):
        marker = {"last_signature": "sig", "last_severity": "urgent", "last_notified_at": T0.isoformat()}
        d = SignalDebouncer(stable_value="sig")
        result, _ = should_notify(
            marker=marker, signature="sig", severity="urgent", now=T0 + timedelta(minutes=5),
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY,
        )
        assert result is False

    def test_marker_with_no_last_notified_at_notifies(self):
        marker = {"last_signature": "sig", "last_severity": "normal", "last_notified_at": None}
        d = SignalDebouncer(stable_value="sig")
        result, _ = should_notify(
            marker=marker, signature="sig", severity="normal", now=T0,
            cooldown_minutes=COOLDOWN, debouncer=d, stability_minutes=STABILITY,
        )
        assert result is True
