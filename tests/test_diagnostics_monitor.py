"""Tests for diagnostics_monitor: is_area_misconfigured (pure predicate)
and _build_message's language handling.
"""

from custom_components.smart_ventilation.diagnostics_monitor import (
    CONFIRMATION_UNREACHABLE,
    _build_message,
    is_area_misconfigured,
)


class TestIsAreaMisconfigured:
    def test_no_automation_configured_is_fine(self):
        assert is_area_misconfigured({}, {"notification_device_ids": []}) is None

    def test_automation_without_confirmation_required_is_fine(self):
        area = {"start_entity_id": "automation.open", "confirmation_required": False}
        assert is_area_misconfigured(area, {"notification_device_ids": []}) is None

    def test_automation_with_confirmation_and_notify_targets_is_fine(self):
        area = {"start_entity_id": "automation.open", "confirmation_required": True}
        settings = {"notification_device_ids": ["abc123"]}
        assert is_area_misconfigured(area, settings) is None

    def test_automation_with_confirmation_and_no_notify_targets_is_unreachable(self):
        area = {"start_entity_id": "automation.open", "confirmation_required": True}
        settings = {"notification_device_ids": []}
        assert is_area_misconfigured(area, settings) == CONFIRMATION_UNREACHABLE

    def test_stop_entity_alone_also_counts_as_automation(self):
        area = {"stop_entity_id": "automation.close", "confirmation_required": True}
        settings = {"notification_device_ids": []}
        assert is_area_misconfigured(area, settings) == CONFIRMATION_UNREACHABLE

    def test_confirmation_required_defaults_to_true_when_unset(self):
        area = {"start_entity_id": "automation.open"}
        settings = {"notification_device_ids": []}
        assert is_area_misconfigured(area, settings) == CONFIRMATION_UNREACHABLE


class TestBuildMessageLanguage:
    def test_english_default(self):
        title, message = _build_message("Keuken", CONFIRMATION_UNREACHABLE, "en")
        assert "unreachable confirmation" in title
        assert "Keuken" in message

    def test_dutch(self):
        title, message = _build_message("Keuken", CONFIRMATION_UNREACHABLE, "nl")
        assert "bevestiging onbereikbaar" in title
        assert "Keuken" in message
        assert "unreachable confirmation" not in title  # sanity: not the English string
