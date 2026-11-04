"""Tests for notification_text: localized notification message building."""

from custom_components.smart_ventilation.notification_text import (
    build_advisory_message,
    build_confirmation_message,
    translate_action,
    translate_reason,
    ui_label,
)


class TestTranslateAction:
    def test_english_passthrough(self):
        assert translate_action("OPEN", "en") == "open"
        assert translate_action("CLOSE", "en") == "close"
        assert translate_action("VENTILATE", "en") == "ventilate briefly"
        assert translate_action("NONE", "en") == "no action"

    def test_dutch(self):
        assert translate_action("OPEN", "nl") == "openen"
        assert translate_action("CLOSE", "nl") == "sluiten"

    def test_unknown_action_falls_back_to_the_raw_value(self):
        assert translate_action("SOMETHING_NEW", "nl") == "SOMETHING_NEW"

    def test_unknown_language_falls_back_to_english(self):
        assert translate_action("OPEN", "fr") == "open"


class TestTranslateReason:
    def test_known_reason_translates_to_dutch(self):
        assert translate_reason("Elevated CO2", "nl") == "Verhoogde CO2"

    def test_known_reason_english_matches_calculator_text(self):
        assert translate_reason("Elevated CO2", "en") == "Elevated CO2"

    def test_unknown_reason_falls_back_to_the_raw_value(self):
        assert translate_reason("Some future reason text", "nl") == "Some future reason text"

    def test_every_calculator_reason_string_has_a_dutch_translation(self):
        # Mirrors the exact set of literal strings calculator.py's
        # get_ventilation_reason() can return — if a new one is ever added
        # there without updating this table, it would silently fall back to
        # English-only; this test catches that at the table level.
        reasons = [
            "Storm warning", "Adverse weather", "Dangerously high CO2",
            "Condensation risk", "Outdoor PM2.5 too high", "Outdoor air too hot",
            "High CO2 level", "Elevated CO2", "High indoor humidity",
            "Indoor too warm", "Good ventilation conditions",
            "Cooling conditions favorable", "Weather conditions deteriorating soon",
            "Outdoor humidity too high", "Outdoor air too cold",
            "Conditions balanced", "Good air quality",
        ]
        for reason in reasons:
            translated = translate_reason(reason, "nl")
            assert translated != reason, f"{reason!r} has no Dutch translation"


class TestUiLabel:
    def test_confirm_dismiss(self):
        assert ui_label("confirm", "en") == "Confirm"
        assert ui_label("dismiss", "en") == "Dismiss"
        assert ui_label("confirm", "nl") == "Bevestigen"
        assert ui_label("dismiss", "nl") == "Afwijzen"


class TestBuildAdvisoryMessage:
    def test_english(self):
        message = build_advisory_message("Keuken", "OPEN", "Elevated CO2", "en")
        assert message == "Keuken: open — Elevated CO2"

    def test_dutch(self):
        message = build_advisory_message("Keuken", "OPEN", "Elevated CO2", "nl")
        assert message == "Keuken: openen — Verhoogde CO2"


class TestBuildConfirmationMessage:
    def test_english_open(self):
        message = build_confirmation_message("Keuken", "OPEN", "en")
        assert "open the window" in message
        assert "Keuken" in message

    def test_dutch_close(self):
        message = build_confirmation_message("Keuken", "CLOSE", "nl")
        assert "het raam sluiten" in message
        assert "Keuken" in message
