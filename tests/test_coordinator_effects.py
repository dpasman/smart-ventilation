"""Tests for SmartVentilationCoordinator._async_handle_area_effects: the
quiet-hours/notifications-enabled gating around notifier.async_send_advisory,
and that actuation always runs regardless of those settings. Uses plain
Mock/AsyncMock substitutes, not a real HA test harness.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smart_ventilation.coordinator import SmartVentilationCoordinator
from custom_components.smart_ventilation.const import DEFAULT_SETTINGS
from custom_components.smart_ventilation.runtime import RuntimeStore

NIGHT = datetime(2026, 1, 1, 23, 0, 0, tzinfo=timezone.utc)  # inside default 22:00-07:00 quiet hours
DAY = datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)


class _FakeConfigEntries:
    def async_update_entry(self, entry, options):
        entry.options = dict(options)


class _FakeEntry:
    def __init__(self, options=None):
        self.options = options or {}
        self.entry_id = "test_entry"


def _make_coordinator():
    # Built via __new__, bypassing __init__: the real DataUpdateCoordinator
    # base class isn't meaningfully constructible under the lightweight
    # pure-python stub (that's exactly why the plan scopes real
    # coordinator-construction testing to the pytest-homeassistant-custom-
    # component harness instead) — _async_handle_area_effects only touches
    # self.hass/self.runtime/self.notifier, so those are all it needs.
    hass = MagicMock()
    hass.config_entries = _FakeConfigEntries()
    entry = _FakeEntry()
    coordinator = SmartVentilationCoordinator.__new__(SmartVentilationCoordinator)
    coordinator.entry = entry
    coordinator.hass = hass
    coordinator.runtime = RuntimeStore(hass, entry)
    coordinator.notifier = MagicMock()
    coordinator.notifier.async_send_advisory = AsyncMock(return_value=True)
    return coordinator


def _area_config():
    return {"name": "Keuken"}


def _data(action="OPEN", override=False, efficiency=85.0):
    return {
        "action": action,
        "action_override": override,
        "ventilation_reason": "Elevated CO2",
        "efficiency": efficiency,
    }


@pytest.fixture(autouse=True)
def _patch_actuator():
    with patch(
        "custom_components.smart_ventilation.coordinator.actuator.async_maybe_actuate",
        new=AsyncMock(),
    ) as mocked:
        yield mocked


class TestActuationAlwaysRuns:
    async def test_actuation_runs_even_during_quiet_hours(self, _patch_actuator):
        coordinator = _make_coordinator()
        await coordinator._async_handle_area_effects(_area_config(), _data(), DEFAULT_SETTINGS, NIGHT)
        _patch_actuator.assert_awaited_once()

    async def test_actuation_runs_even_with_notifications_disabled(self, _patch_actuator):
        coordinator = _make_coordinator()
        settings = {**DEFAULT_SETTINGS, "notifications_enabled": False}
        await coordinator._async_handle_area_effects(_area_config(), _data(), settings, DAY)
        _patch_actuator.assert_awaited_once()


class TestNotificationGating:
    async def test_notifies_once_the_signature_has_settled(self):
        # A single tick never notifies — the signature must first hold
        # stable for stability_window_minutes (default 10) before
        # should_notify() lets anything through.
        coordinator = _make_coordinator()
        data = _data()
        await coordinator._async_handle_area_effects(_area_config(), data, DEFAULT_SETTINGS, DAY)
        coordinator.notifier.async_send_advisory.assert_not_called()
        await coordinator._async_handle_area_effects(
            _area_config(), data, DEFAULT_SETTINGS, DAY + timedelta(minutes=10)
        )
        coordinator.notifier.async_send_advisory.assert_awaited_once()

    async def test_suppressed_during_quiet_hours(self):
        coordinator = _make_coordinator()
        await coordinator._async_handle_area_effects(_area_config(), _data(), DEFAULT_SETTINGS, NIGHT)
        coordinator.notifier.async_send_advisory.assert_not_called()

    async def test_override_bypasses_quiet_hours(self):
        coordinator = _make_coordinator()
        await coordinator._async_handle_area_effects(
            _area_config(), _data(action="CLOSE", override=True), DEFAULT_SETTINGS, NIGHT
        )
        coordinator.notifier.async_send_advisory.assert_awaited_once()

    async def test_suppressed_when_notifications_disabled(self):
        coordinator = _make_coordinator()
        settings = {**DEFAULT_SETTINGS, "notifications_enabled": False}
        await coordinator._async_handle_area_effects(_area_config(), _data(), settings, DAY)
        coordinator.notifier.async_send_advisory.assert_not_called()

    async def test_none_action_without_override_is_skipped_entirely(self):
        coordinator = _make_coordinator()
        await coordinator._async_handle_area_effects(
            _area_config(), _data(action="NONE"), DEFAULT_SETTINGS, DAY
        )
        coordinator.notifier.async_send_advisory.assert_not_called()

    async def test_repeated_identical_signature_within_cooldown_does_not_renotify(self):
        coordinator = _make_coordinator()
        data = _data()
        # Prime, then settle+send at the 10-minute stability mark.
        await coordinator._async_handle_area_effects(_area_config(), data, DEFAULT_SETTINGS, DAY)
        await coordinator._async_handle_area_effects(
            _area_config(), data, DEFAULT_SETTINGS, DAY + timedelta(minutes=10)
        )
        coordinator.notifier.async_send_advisory.assert_awaited_once()
        coordinator.notifier.async_send_advisory.reset_mock()

        # Same signature again, well within the default 60-minute cooldown.
        await coordinator._async_handle_area_effects(
            _area_config(), data, DEFAULT_SETTINGS, DAY + timedelta(minutes=15)
        )
        coordinator.notifier.async_send_advisory.assert_not_called()

    async def test_repeated_identical_signature_after_cooldown_renotifies(self):
        coordinator = _make_coordinator()
        data = _data()
        await coordinator._async_handle_area_effects(_area_config(), data, DEFAULT_SETTINGS, DAY)
        await coordinator._async_handle_area_effects(
            _area_config(), data, DEFAULT_SETTINGS, DAY + timedelta(minutes=10)
        )
        coordinator.notifier.async_send_advisory.reset_mock()

        await coordinator._async_handle_area_effects(
            _area_config(), data, DEFAULT_SETTINGS, DAY + timedelta(minutes=71)
        )
        coordinator.notifier.async_send_advisory.assert_awaited_once()

    async def test_flickering_reason_text_with_unchanged_action_does_not_spam(self):
        # Regression test for the notification-spam report: a value
        # hovering near a threshold can flip calculator.get_ventilation_reason()
        # back and forth (e.g. "Elevated CO2" <-> "High CO2 level") while the
        # recommended action stays OPEN the whole time. That must never look
        # like a new recommendation.
        coordinator = _make_coordinator()
        reason_a = _data()
        reason_b = {**reason_a, "ventilation_reason": "High CO2 level"}

        await coordinator._async_handle_area_effects(_area_config(), reason_a, DEFAULT_SETTINGS, DAY)
        await coordinator._async_handle_area_effects(
            _area_config(), reason_b, DEFAULT_SETTINGS, DAY + timedelta(minutes=10)
        )
        coordinator.notifier.async_send_advisory.assert_awaited_once()
        coordinator.notifier.async_send_advisory.reset_mock()

        # Reason flips again, still within cooldown, action still unchanged.
        await coordinator._async_handle_area_effects(
            _area_config(), reason_a, DEFAULT_SETTINGS, DAY + timedelta(minutes=20)
        )
        await coordinator._async_handle_area_effects(
            _area_config(), reason_b, DEFAULT_SETTINGS, DAY + timedelta(minutes=30)
        )
        coordinator.notifier.async_send_advisory.assert_not_called()
