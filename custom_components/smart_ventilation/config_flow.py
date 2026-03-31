"""Config flow for Smart Ventilation integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AREA_NAME,
    CONF_INDOOR_ABS_HUMIDITY,
    CONF_INDOOR_CO2,
    CONF_INDOOR_DEW_POINT,
    CONF_INDOOR_HEAT_INDEX,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_PM25,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_ABS_HUMIDITY,
    CONF_OUTDOOR_DEW_POINT,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMP,
    CONF_OUTDOOR_TEMP_MAX_24H,
    CONF_WIND_AVG,
    CONF_WIND_MAX,
    DOMAIN,
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
                data={**user_input, "areas": []},
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
                    vol.Required(CONF_OUTDOOR_ABS_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_DEW_POINT): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_TEMP_MAX_24H): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_OUTDOOR_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="humidity"
                        ),
                    ),
                    vol.Optional(CONF_WIND_AVG): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_WIND_MAX): selector.EntitySelector(
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

    Note: self.config_entry is set automatically by the OptionsFlow base class
    in HA 2024.x+. Do NOT define __init__ here.
    """

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Show area management menu, or go straight to add if no areas exist."""
        if not self.config_entry.data.get("areas"):
            return await self.async_step_add_area()

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="add"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="add", label="Add Area"),
                                selector.SelectOptionDict(
                                    value="remove", label="Remove Area"
                                ),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_menu(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Route menu selection to add or remove step."""
        if user_input is not None:
            if user_input.get("action") == "add":
                return await self.async_step_add_area()
            if user_input.get("action") == "remove":
                return await self.async_step_remove_area()
        return await self.async_step_init()

    async def async_step_add_area(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Add a new area with its indoor sensors."""
        if user_input is not None:
            areas = list(self.config_entry.data.get("areas", []))
            areas.append(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, "areas": areas},
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_area",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AREA_NAME): str,
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
                    vol.Optional(CONF_INDOOR_ABS_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_INDOOR_DEW_POINT): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_INDOOR_HEAT_INDEX): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_INDOOR_CO2): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_INDOOR_PM25): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                }
            ),
        )

    async def async_step_remove_area(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Remove an existing area."""
        areas = self.config_entry.data.get("areas", [])

        if user_input is not None:
            area_name = user_input.get("area_to_remove")
            new_areas = [a for a in areas if a[CONF_AREA_NAME] != area_name]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, "areas": new_areas},
            )
            return self.async_create_entry(title="", data={})

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
