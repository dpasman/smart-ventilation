"""Config flow for Smart Ventilation integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_INDOOR_CO2,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_PM25,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMP,
    CONF_OUTDOOR_TEMP_MAX_24H,
    CONF_WIND_AVG,
    CONF_WIND_MAX,
    DOMAIN,
)

CONF_AREA = "area"
CONF_INDOOR_TEMP = "indoor_temperature"
CONF_INDOOR_HUMIDITY = "indoor_humidity"
CONF_OUTDOOR_TEMP = "outdoor_temperature"
CONF_OUTDOOR_HUMIDITY = "outdoor_humidity"


class SmartVentilationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Ventilation."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

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
                        selector.EntitySelectorConfig(),
                    ),
                    vol.Required(CONF_OUTDOOR_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(),
                    ),
                    vol.Optional(CONF_OUTDOOR_TEMP_MAX_24H): selector.EntitySelector(
                        selector.EntitySelectorConfig(),
                    ),
                    vol.Optional(CONF_WIND_AVG): selector.EntitySelector(
                        selector.EntitySelectorConfig(),
                    ),
                    vol.Optional(CONF_WIND_MAX): selector.EntitySelector(
                        selector.EntitySelectorConfig(),
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "outdoor_temp": "Outdoor Temperature",
                "outdoor_humidity": "Outdoor Humidity",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Smart Ventilation."""

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Manage the options."""
        areas = self.config_entry.data.get("areas", [])

        if not areas:
            return await self.async_step_add_area()

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="add"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="add", label="Add Area"),
                                selector.SelectOptionDict(value="remove", label="Remove Area"),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_menu(self, user_input: dict | None = None) -> FlowResult:
        """Handle menu selection."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_area()
            if action == "remove":
                return await self.async_step_remove_area()

        return await self.async_step_init()

    async def async_step_add_area(self, user_input: dict | None = None) -> FlowResult:
        """Handle adding a new area."""
        if user_input is not None:
            areas = self.config_entry.data.get("areas", [])
            areas.append(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, "areas": areas},
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        areas = self.hass.config_entries.async_get_areas()
        area_options = [
            selector.SelectOptionDict(value=area["area_id"], label=area["name"])
            for area in areas
        ]

        return self.async_show_form(
            step_id="add_area",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AREA): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=area_options, mode=selector.SelectSelectorMode.DROPDOWN)
                    ),
                    vol.Required(CONF_INDOOR_TEMP): selector.EntitySelector(
                        selector.EntitySelectorConfig(),
                    ),
                    vol.Required(CONF_INDOOR_HUMIDITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(),
                    ),
                    vol.Optional(CONF_INDOOR_CO2): selector.EntitySelector(
                        selector.EntitySelectorConfig(),
                    ),
                    vol.Optional(CONF_INDOOR_PM25): selector.EntitySelector(
                        selector.EntitySelectorConfig(),
                    ),
                }
            ),
            description_placeholders={
                "area": "Select Home Assistant Area",
                "indoor_temp": "Indoor Temperature Sensor",
                "indoor_humidity": "Indoor Humidity Sensor",
            },
        )

    async def async_step_remove_area(self, user_input: dict | None = None) -> FlowResult:
        """Handle removing an area."""
        areas = self.config_entry.data.get("areas", [])

        if user_input is not None:
            area_id = user_input.get("area_to_remove")
            areas = [a for a in areas if a.get(CONF_AREA) != area_id]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, "areas": areas},
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        options = [
            selector.SelectOptionDict(value=a.get(CONF_AREA, a.get("name", "")), label=a.get("name", "Unknown"))
            for a in areas
        ]

        return self.async_show_form(
            step_id="remove_area",
            data_schema=vol.Schema(
                {
                    vol.Required("area_to_remove"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return OptionsFlowHandler()


# END OF FILE
