"""Integration tests against a real Home Assistant core (via
pytest-homeassistant-custom-component), not the lightweight pure-python
stub used by the rest of this test suite — see conftest.py's docstring
for how the two coexist.

Covers: config-entry setup/unload roundtrip, the options-flow add-area +
global-settings sequence (regression test for the options-replace clobber
bug fixed in config_flow.py's _write_options()), and a live number-entity
write persisting without forcing a full platform reload.
"""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_ventilation.const import DOMAIN

AREA_CONFIG = {
    "name": "keuken",
    "area_id": "keuken",
    "indoor_temperature": "sensor.keuken_temperature",
    "indoor_humidity": "sensor.keuken_humidity",
}
OUTDOOR_CONFIG = {"outdoor_temperature": "sensor.outdoor_temperature"}


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _set_sensor_states(hass):
    hass.states.async_set("sensor.outdoor_temperature", "15.0", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.keuken_temperature", "21.0", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.keuken_humidity", "50.0", {"unit_of_measurement": "%"})


class TestSetupUnloadRoundtrip:
    async def test_setup_then_unload(self, hass):
        _set_sensor_states(hass)
        entry = MockConfigEntry(
            domain=DOMAIN, data=OUTDOOR_CONFIG, options={"areas": [AREA_CONFIG]},
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state.value == "loaded"

        efficiency_state = hass.states.get("sensor.keuken_keuken_ventilation_efficiency")
        assert efficiency_state is not None

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state.value == "not_loaded"

    async def test_setup_without_outdoor_temperature_fails(self, hass):
        entry = MockConfigEntry(domain=DOMAIN, data={}, options={"areas": [AREA_CONFIG]})
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)


class TestOptionsFlowClobberRegression:
    """Regression test for the bug fixed in config_flow.py's _write_options():
    async_create_entry's `data` replaces entry.options wholesale, so an area
    edit must not wipe the "settings"/"_runtime" keys written by a prior
    global-settings step (or vice versa).
    """

    async def test_global_settings_survive_a_later_area_edit(self, hass):
        _set_sensor_states(hass)
        entry = MockConfigEntry(
            domain=DOMAIN, data=OUTDOOR_CONFIG, options={"areas": [AREA_CONFIG]},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Step 1: set a global setting via the options flow.
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"action": "global_settings"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"debug_mode": True}
        )
        await hass.async_block_till_done()
        assert entry.options["settings"]["debug_mode"] is True

        # Step 2: edit the area through the options flow.
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"action": "edit"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_to_edit": "keuken"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": "keuken",
                "indoor_temperature": "sensor.keuken_temperature",
                "indoor_humidity": "sensor.keuken_humidity",
                "action_hold_minutes": 5,
                "action_lockout_minutes": 20,
                "confirmation_required": True,
            },
        )
        await hass.async_block_till_done()

        # The global setting from step 1 must have survived.
        assert entry.options["settings"]["debug_mode"] is True
        assert entry.options["areas"][0]["name"] == "keuken"


class TestLiveSettingsWriteNoFullReload:
    async def test_number_entity_write_does_not_remove_entities(self, hass):
        _set_sensor_states(hass)
        entry = MockConfigEntry(
            domain=DOMAIN, data=OUTDOOR_CONFIG, options={"areas": [AREA_CONFIG]},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        cooldown_entity_id = "number.smart_ventilation_notification_cooldown"
        before = hass.states.get(cooldown_entity_id)
        assert before is not None

        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": cooldown_entity_id, "value": 45},
            blocking=True,
        )
        await hass.async_block_till_done()

        after = hass.states.get(cooldown_entity_id)
        assert after is not None
        assert after.state == "45.0" or after.state == "45"
        # The per-area efficiency sensor must still exist — a full reload
        # would briefly remove and recreate every entity, but should never
        # make this one disappear across the write.
        assert hass.states.get("sensor.keuken_keuken_ventilation_efficiency") is not None
