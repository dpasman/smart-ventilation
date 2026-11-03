"""Tests for diagnostics_monitor.is_area_misconfigured (pure predicate)."""

from custom_components.smart_ventilation.diagnostics_monitor import (
    CONFIRMATION_UNREACHABLE,
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
