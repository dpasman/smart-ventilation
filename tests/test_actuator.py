"""Tests for actuator.async_maybe_actuate: guard integration, idempotency,
confirmation gating. Uses plain Mock/AsyncMock substitutes for hass, not a
real HA test harness.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.smart_ventilation.actuator import async_maybe_actuate
from custom_components.smart_ventilation.runtime import RuntimeStore

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class _FakeConfigEntries:
    def async_update_entry(self, entry, options):
        entry.options = dict(options)


class _FakeEntry:
    def __init__(self, options=None):
        self.options = options or {}


def _make_hass(window_states: dict[str, str] | None = None):
    hass = MagicMock()
    hass.config_entries = _FakeConfigEntries()
    hass.services.async_call = AsyncMock()

    def _get_state(entity_id):
        if window_states and entity_id in window_states:
            state = MagicMock()
            state.state = window_states[entity_id]
            return state
        return None

    hass.states.get = MagicMock(side_effect=_get_state)
    return hass


def _area_config(**overrides):
    base = {
        "name": "Keuken",
        "start_entity_id": "automation.keuken_open",
        "stop_entity_id": "automation.keuken_close",
        "confirmation_required": False,
    }
    return {**base, **overrides}


@pytest.fixture
def notifier():
    n = MagicMock()
    n.async_send_confirmation_request = AsyncMock(return_value="token123")
    return n


class TestNonActuatableActions:
    async def test_ventilate_never_calls_automation_trigger(self, notifier):
        hass = _make_hass()
        entry = _FakeEntry()
        runtime = RuntimeStore(hass, entry)
        await async_maybe_actuate(hass, _area_config(), runtime, notifier, "VENTILATE", False, T0)
        hass.services.async_call.assert_not_called()

    async def test_none_never_calls_automation_trigger(self, notifier):
        hass = _make_hass()
        entry = _FakeEntry()
        runtime = RuntimeStore(hass, entry)
        await async_maybe_actuate(hass, _area_config(), runtime, notifier, "NONE", False, T0)
        hass.services.async_call.assert_not_called()


class TestGuardHoldGating:
    async def test_first_proposal_does_not_actuate_immediately(self, notifier):
        hass = _make_hass()
        entry = _FakeEntry()
        runtime = RuntimeStore(hass, entry)
        await async_maybe_actuate(hass, _area_config(), runtime, notifier, "OPEN", False, T0)
        hass.services.async_call.assert_not_called()
        assert runtime.area_state("Keuken")["guard"]["pending_action"] == "OPEN"

    async def test_override_actuates_immediately_without_confirmation(self, notifier):
        hass = _make_hass()
        entry = _FakeEntry()
        runtime = RuntimeStore(hass, entry)
        await async_maybe_actuate(
            hass, _area_config(confirmation_required=True), runtime, notifier, "CLOSE", True, T0
        )
        hass.services.async_call.assert_awaited_once_with(
            "automation", "trigger", {"skip_condition": False},
            target={"entity_id": "automation.keuken_close"}, blocking=True,
        )
        notifier.async_send_confirmation_request.assert_not_called()


class TestIdempotency:
    async def test_open_skipped_when_window_already_open(self, notifier):
        hass = _make_hass(window_states={"binary_sensor.keuken_raam": "on"})
        entry = _FakeEntry()
        runtime = RuntimeStore(hass, entry)
        config = _area_config(window_sensor_entity_ids=["binary_sensor.keuken_raam"])
        await async_maybe_actuate(hass, config, runtime, notifier, "OPEN", True, T0)  # override -> accepted immediately
        hass.services.async_call.assert_not_called()

    async def test_close_skipped_when_window_already_closed(self, notifier):
        hass = _make_hass(window_states={"binary_sensor.keuken_raam": "off"})
        entry = _FakeEntry()
        runtime = RuntimeStore(hass, entry)
        config = _area_config(window_sensor_entity_ids=["binary_sensor.keuken_raam"])
        await async_maybe_actuate(hass, config, runtime, notifier, "CLOSE", True, T0)
        hass.services.async_call.assert_not_called()

    async def test_open_proceeds_when_window_closed(self, notifier):
        hass = _make_hass(window_states={"binary_sensor.keuken_raam": "off"})
        entry = _FakeEntry()
        runtime = RuntimeStore(hass, entry)
        config = _area_config(window_sensor_entity_ids=["binary_sensor.keuken_raam"])
        await async_maybe_actuate(hass, config, runtime, notifier, "OPEN", True, T0)
        hass.services.async_call.assert_awaited_once()

    async def test_no_window_sensors_never_skips(self, notifier):
        hass = _make_hass()
        entry = _FakeEntry()
        runtime = RuntimeStore(hass, entry)
        await async_maybe_actuate(hass, _area_config(), runtime, notifier, "OPEN", True, T0)
        hass.services.async_call.assert_awaited_once()


class TestConfirmationFlow:
    """These use is_override=False and two ticks (hold starts, then settles)
    so an accepted-but-not-override OPEN is actually produced — passing
    is_override=True would bypass confirmation entirely (see
    TestGuardHoldGating.test_override_actuates_immediately_without_confirmation),
    which is not the path under test here.
    """

    async def _accept_open(self, hass, runtime, notifier, config):
        await async_maybe_actuate(hass, config, runtime, notifier, "OPEN", False, T0)
        await async_maybe_actuate(
            hass, config, runtime, notifier, "OPEN", False, T0 + timedelta(minutes=5)
        )

    async def test_confirmation_required_sends_request_not_direct_trigger(self, notifier):
        hass = _make_hass()
        runtime = RuntimeStore(hass, _FakeEntry())
        config = _area_config(confirmation_required=True)
        await self._accept_open(hass, runtime, notifier, config)
        notifier.async_send_confirmation_request.assert_awaited_once()
        hass.services.async_call.assert_not_called()

    async def test_confirming_triggers_the_automation(self, notifier):
        hass = _make_hass()
        runtime = RuntimeStore(hass, _FakeEntry())
        config = _area_config(confirmation_required=True)
        await self._accept_open(hass, runtime, notifier, config)

        # Simulate the user confirming: invoke the captured on_resolved callback.
        on_resolved = notifier.async_send_confirmation_request.call_args.args[-1]
        await on_resolved(True)
        hass.services.async_call.assert_awaited_once_with(
            "automation", "trigger", {"skip_condition": False},
            target={"entity_id": "automation.keuken_open"}, blocking=True,
        )

    async def test_dismissing_never_triggers_the_automation(self, notifier):
        hass = _make_hass()
        runtime = RuntimeStore(hass, _FakeEntry())
        config = _area_config(confirmation_required=True)
        await self._accept_open(hass, runtime, notifier, config)

        on_resolved = notifier.async_send_confirmation_request.call_args.args[-1]
        await on_resolved(False)
        hass.services.async_call.assert_not_called()


class TestMissingAutomationEntity:
    async def test_no_start_entity_configured_does_nothing(self, notifier):
        hass = _make_hass()
        entry = _FakeEntry()
        runtime = RuntimeStore(hass, entry)
        config = _area_config(start_entity_id=None)
        await async_maybe_actuate(hass, config, runtime, notifier, "OPEN", True, T0)
        hass.services.async_call.assert_not_called()
        notifier.async_send_confirmation_request.assert_not_called()
