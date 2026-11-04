"""Config flow for Smart Ventilation integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar, selector

from .const import (
    CONF_ACTION_HOLD_MINUTES,
    CONF_ACTION_LOCKOUT_MINUTES,
    CONF_AREA_NAME,
    CONF_CONFIRMATION_REQUIRED,
    CONF_DEBUG_MODE,
    CONF_DIAGNOSTIC_NOTIFICATION_LEVEL,
    CONF_INDOOR_CO2,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_PM25,
    CONF_INDOOR_TEMP,
    CONF_NOTIFICATION_COOLDOWN_MINUTES,
    CONF_NOTIFICATION_DEVICE_IDS,
    CONF_NOTIFICATIONS_ENABLED,
    CONF_OUTDOOR_ABS_HUMIDITY,
    CONF_OUTDOOR_DEW_POINT,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_PM25,
    CONF_OUTDOOR_TEMP,
    CONF_OUTDOOR_TEMP_MAX_24H,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    CONF_SEASON_BIAS,
    CONF_STABILITY_WINDOW_MINUTES,
    CONF_START_ENTITY,
    CONF_STOP_ENTITY,
    CONF_WEATHER_ENTITY,
    CONF_WIND_AVG,
    CONF_WIND_MAX,
    CONF_WINDOW_SENSORS,
    DEFAULT_ACTION_HOLD_MINUTES,
    DEFAULT_ACTION_LOCKOUT_MINUTES,
    DEFAULT_CONFIRMATION_REQUIRED,
    DIAGNOSTIC_LEVEL_OPTIONS,
    DOMAIN,
    SEASON_BIAS_OPTIONS,
)
from .runtime import RuntimeStore


def _area_schema() -> vol.Schema:
    """Shared schema for add and edit area forms.

    The actuation/automation fields below are all optional — an area with
    none of them configured stays exactly as advisory-only as it is today.
    """
    return vol.Schema(
        {
            vol.Required(CONF_AREA_NAME): selector.AreaSelector(),
            vol.Required(CONF_INDOOR_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="temperature"
                ),
            ),
            vol.Required(CONF_INDOOR_HUMIDITY): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="humidity"
                ),
            ),
            vol.Optional(CONF_INDOOR_CO2): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor"),
            ),
            vol.Optional(CONF_INDOOR_PM25): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor"),
            ),
            vol.Optional(CONF_START_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="automation"),
            ),
            vol.Optional(CONF_STOP_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="automation"),
            ),
            vol.Optional(CONF_WINDOW_SENSORS): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", multiple=True),
            ),
            vol.Optional(
                CONF_ACTION_HOLD_MINUTES, default=DEFAULT_ACTION_HOLD_MINUTES
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=120, step=1, mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Optional(
                CONF_ACTION_LOCKOUT_MINUTES, default=DEFAULT_ACTION_LOCKOUT_MINUTES
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=360, step=1, mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Optional(
                CONF_CONFIRMATION_REQUIRED, default=DEFAULT_CONFIRMATION_REQUIRED
            ): selector.BooleanSelector(),
        }
    )


def _global_settings_schema() -> vol.Schema:
    """Schema for the options flow's "Global Settings" step."""
    return vol.Schema(
        {
            vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather"),
            ),
            vol.Optional(CONF_NOTIFICATION_DEVICE_IDS): selector.DeviceSelector(
                selector.DeviceSelectorConfig(integration="mobile_app", multiple=True),
            ),
            vol.Optional(CONF_NOTIFICATIONS_ENABLED): selector.BooleanSelector(),
            vol.Optional(CONF_QUIET_HOURS_ENABLED): selector.BooleanSelector(),
            vol.Optional(CONF_QUIET_HOURS_START): selector.TimeSelector(),
            vol.Optional(CONF_QUIET_HOURS_END): selector.TimeSelector(),
            vol.Optional(CONF_NOTIFICATION_COOLDOWN_MINUTES): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=360, step=1, mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Optional(CONF_STABILITY_WINDOW_MINUTES): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=120, step=1, mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Optional(CONF_SEASON_BIAS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=SEASON_BIAS_OPTIONS, mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
            vol.Optional(CONF_DIAGNOSTIC_NOTIFICATION_LEVEL): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=DIAGNOSTIC_LEVEL_OPTIONS, mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
            vol.Optional(CONF_DEBUG_MODE): selector.BooleanSelector(),
        }
    )


class SmartVentilationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Ventilation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — outdoor sensor configuration."""
        if user_input is not None:
            return self.async_create_entry(
                title="Smart Ventilation",
                data={**user_input},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OUTDOOR_TEMP): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="temperature"
                        ),
                    ),
                    vol.Optional(CONF_OUTDOOR_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="humidity"
                        ),
                    ),
                    vol.Optional(CONF_OUTDOOR_ABS_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_DEW_POINT): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_TEMP_MAX_24H): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_WIND_AVG): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_WIND_MAX): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_PM25): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Smart Ventilation — manage areas.

    Areas are stored in entry.options so that async_create_entry triggers
    exactly one reload. Do NOT define __init__ here (HA 2024.x+).
    """

    def _get_areas(self) -> list:
        """Return current areas from options (preferred) or data (legacy)."""
        return list(
            self.config_entry.options.get("areas")
            or self.config_entry.data.get("areas", [])
        )

    def _write_options(self, patch: dict) -> ConfigFlowResult:
        """Create an options entry, preserving every existing top-level key.

        async_create_entry's `data` REPLACES entry.options wholesale, so any
        call site that only passes e.g. {"areas": areas} would silently wipe
        "settings"/"_runtime" the moment those keys exist. Always go through
        this helper instead of calling async_create_entry directly.
        """
        return self.async_create_entry(
            title="", data={**self.config_entry.options, **patch}
        )

    def _resolve_area(self, area_id: str) -> str:
        """Return the human-readable area name from the HA area registry."""
        entry = ar.async_get(self.hass).async_get_area(area_id)
        return entry.name if entry else area_id

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Show the top-level menu: manage areas, or global settings."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["areas", "global_settings"],
        )

    async def async_step_areas(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Show the area-management menu, or go straight to add on first use."""
        if not self._get_areas():
            return await self.async_step_add_area()

        return self.async_show_menu(
            step_id="areas",
            # "edit_area_select", not "edit_area" — a menu option routes
            # directly to async_step_<value>(), and editing needs the
            # area-selection step first, not the edit form itself.
            menu_options=["add_area", "edit_area_select", "remove_area"],
        )

    async def async_step_global_settings(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """View/edit global settings (weather entity, quiet hours, notifications, etc.).

        Goes through _write_options() (full reload) like area add/edit/
        remove — this is a deliberate, infrequent configuration action
        submitted via a form, not a live dashboard tweak, so the
        suppress-reload path (RuntimeStore.save_settings(), used by the
        live number/time/switch entities for this same "settings" key) is
        the wrong tool here and would just race against this step's own
        async_create_entry.
        """
        current_settings = RuntimeStore(self.hass, self.config_entry).settings
        if user_input is not None:
            return self._write_options({"settings": {**current_settings, **user_input}})

        return self.async_show_form(
            step_id="global_settings",
            data_schema=self.add_suggested_values_to_schema(
                _global_settings_schema(), current_settings
            ),
        )

    async def async_step_add_area(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Add a new area with its indoor sensors."""
        if user_input is not None:
            area_id = user_input[CONF_AREA_NAME]
            area_name = self._resolve_area(area_id)
            area_data = {**user_input, CONF_AREA_NAME: area_name, "area_id": area_id}
            areas = self._get_areas()
            areas.append(area_data)
            return self._write_options({"areas": areas})

        return self.async_show_form(step_id="add_area", data_schema=_area_schema())

    async def async_step_edit_area_select(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Select which area to edit."""
        areas = self._get_areas()

        if user_input is not None:
            self._editing_area_name = user_input["area_to_edit"]
            return await self.async_step_edit_area()

        return self.async_show_form(
            step_id="edit_area_select",
            data_schema=vol.Schema(
                {
                    vol.Required("area_to_edit"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=a[CONF_AREA_NAME], label=a[CONF_AREA_NAME]
                                )
                                for a in areas
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_area(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Edit an existing area."""
        areas = self._get_areas()
        editing_name = getattr(self, "_editing_area_name", None)
        current = next((a for a in areas if a[CONF_AREA_NAME] == editing_name), None)

        if user_input is not None:
            area_id = user_input[CONF_AREA_NAME]
            area_name = self._resolve_area(area_id)
            area_data = {**user_input, CONF_AREA_NAME: area_name, "area_id": area_id}
            new_areas = [
                area_data if a[CONF_AREA_NAME] == editing_name else a for a in areas
            ]
            return self._write_options({"areas": new_areas})

        suggested: dict = {}
        if current:
            suggested = {
                CONF_AREA_NAME: current.get("area_id", ""),
                CONF_INDOOR_TEMP: current.get(CONF_INDOOR_TEMP),
                CONF_INDOOR_HUMIDITY: current.get(CONF_INDOOR_HUMIDITY),
                CONF_INDOOR_CO2: current.get(CONF_INDOOR_CO2),
                CONF_INDOOR_PM25: current.get(CONF_INDOOR_PM25),
                CONF_START_ENTITY: current.get(CONF_START_ENTITY),
                CONF_STOP_ENTITY: current.get(CONF_STOP_ENTITY),
                CONF_WINDOW_SENSORS: current.get(CONF_WINDOW_SENSORS),
                CONF_ACTION_HOLD_MINUTES: current.get(
                    CONF_ACTION_HOLD_MINUTES, DEFAULT_ACTION_HOLD_MINUTES
                ),
                CONF_ACTION_LOCKOUT_MINUTES: current.get(
                    CONF_ACTION_LOCKOUT_MINUTES, DEFAULT_ACTION_LOCKOUT_MINUTES
                ),
                CONF_CONFIRMATION_REQUIRED: current.get(
                    CONF_CONFIRMATION_REQUIRED, DEFAULT_CONFIRMATION_REQUIRED
                ),
            }

        return self.async_show_form(
            step_id="edit_area",
            data_schema=self.add_suggested_values_to_schema(_area_schema(), suggested),
        )

    async def async_step_remove_area(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Remove an existing area."""
        areas = self._get_areas()

        if user_input is not None:
            area_name = user_input.get("area_to_remove")
            new_areas = [a for a in areas if a[CONF_AREA_NAME] != area_name]
            return self._write_options({"areas": new_areas})

        return self.async_show_form(
            step_id="remove_area",
            data_schema=vol.Schema(
                {
                    vol.Required("area_to_remove"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=a[CONF_AREA_NAME], label=a[CONF_AREA_NAME]
                                )
                                for a in areas
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
