"""Tests for RuntimeStore: defaults, migration, and the suppress-reload flag."""

from custom_components.smart_ventilation.runtime import RuntimeStore, DEFAULT_AREA_RUNTIME
from custom_components.smart_ventilation.const import DEFAULT_SETTINGS


class _FakeConfigEntries:
    def async_update_entry(self, entry, options):
        entry.options = dict(options)


class _FakeHass:
    def __init__(self):
        self.config_entries = _FakeConfigEntries()


class _FakeEntry:
    def __init__(self, options=None):
        self.options = options or {}


def _store(options=None):
    return RuntimeStore(_FakeHass(), _FakeEntry(options))


class TestSettings:
    def test_defaults_when_missing(self):
        store = _store()
        assert store.settings == DEFAULT_SETTINGS

    def test_partial_existing_settings_merge_onto_defaults(self):
        store = _store({"settings": {"debug_mode": True}})
        settings = store.settings
        assert settings["debug_mode"] is True
        assert settings["notification_cooldown_minutes"] == DEFAULT_SETTINGS["notification_cooldown_minutes"]

    def test_save_settings_merges_and_sets_suppress_flag(self):
        store = _store()
        store.save_settings({"debug_mode": True})
        assert store.settings["debug_mode"] is True
        assert store.settings["quiet_hours_enabled"] is True  # untouched default preserved
        assert store.suppress_next_reload() is True
        assert store.suppress_next_reload() is False  # consume-once


class TestAreaState:
    def test_defaults_when_area_missing(self):
        store = _store()
        assert store.area_state("Keuken") == DEFAULT_AREA_RUNTIME

    def test_save_area_state_replaces_only_named_subgroup(self):
        store = _store()
        store.save_area_state(
            "Keuken", {"guard": {"accepted_action": "OPEN", "pending_action": None,
                                  "pending_since": None, "lockout_until": None}}
        )
        state = store.area_state("Keuken")
        assert state["guard"]["accepted_action"] == "OPEN"
        assert state["notify"] == DEFAULT_AREA_RUNTIME["notify"]  # untouched

    def test_other_areas_unaffected(self):
        store = _store()
        store.save_area_state(
            "Keuken", {"diagnostics": {"misconfigured": True, "last_data_ok": None}}
        )
        assert store.area_state("Badkamer") == DEFAULT_AREA_RUNTIME


class TestMigration:
    def test_ensure_defaults_writes_once_for_legacy_entry(self):
        entry = _FakeEntry({"areas": [{"name": "Keuken"}]})
        store = RuntimeStore(_FakeHass(), entry)
        store.ensure_defaults()
        assert "settings" in entry.options
        assert "_runtime" in entry.options
        assert entry.options["areas"] == [{"name": "Keuken"}]  # untouched

    def test_ensure_defaults_is_noop_when_already_present(self):
        entry = _FakeEntry({"settings": {}, "_runtime": {"version": 1, "areas": {}}})
        store = RuntimeStore(_FakeHass(), entry)
        before = entry.options
        store.ensure_defaults()
        assert entry.options is before  # no write happened
