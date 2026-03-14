"""Config flow for Smart Ventilation integration."""

import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_AREA_NAME,
    CONF_INDOOR_CO2,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_PM25,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SmartVentilationConfigFlow(ConfigFlow):
    """Handle a config flow for Smart Ventilation."""

    VERSION = 1
    domain = DOMAIN

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        _LOGGER.debug("async_step_user called with input: %s", user_input)

        if user_input is not None:
            return self.async_create_entry(
                title="Smart Ventilation",
                data={**user_input, "areas": []},
            )

        schema = vol.Schema({
            vol.Required(CONF_OUTDOOR_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig()
            ),
            vol.Required(CONF_OUTDOOR_HUMIDITY): selector.EntitySelector(
                selector.EntitySelectorConfig()
            ),
        })

        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return SmartVentilationOptionsFlow()


class SmartVentilationOptionsFlow(OptionsFlow):
    """Handle options flow for Smart Ventilation."""

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Manage the options."""
        areas = self.config_entry.data.get("areas", [])

        if not areas:
            return await self.async_step_add_area()

        return await self.async_step_menu()

    async def async_step_menu(self, user_input: dict | None = None) -> FlowResult:
        """Handle menu selection."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_area()
            if action == "remove":
                return await self.async_step_remove_area()

        schema = vol.Schema({
            vol.Required("action", default="add"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="add", label="Add Area"),
                        selector.SelectOptionDict(value="remove", label="Remove Area"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })
        return self.async_show_form(step_id="menu", data_schema=schema)

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

        schema = vol.Schema({
            vol.Required(CONF_AREA_NAME): str,
            vol.Required(CONF_INDOOR_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig()
            ),
            vol.Required(CONF_INDOOR_HUMIDITY): selector.EntitySelector(
                selector.EntitySelectorConfig()
            ),
            vol.Optional(CONF_INDOOR_CO2): selector.EntitySelector(
                selector.EntitySelectorConfig()
            ),
            vol.Optional(CONF_INDOOR_PM25): selector.EntitySelector(
                selector.EntitySelectorConfig()
            ),
        })
        return self.async_show_form(step_id="add_area", data_schema=schema)

    async def async_step_remove_area(self, user_input: dict | None = None) -> FlowResult:
        """Handle removing an area."""
        areas = self.config_entry.data.get("areas", [])

        if user_input is not None:
            area_name = user_input.get("area_to_remove")
            areas = [a for a in areas if a[CONF_AREA_NAME] != area_name]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, "areas": areas},
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        options = [
            selector.SelectOptionDict(value=a[CONF_AREA_NAME], label=a[CONF_AREA_NAME])
            for a in areas
        ]

        schema = vol.Schema({
            vol.Required("area_to_remove"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
        })
        return self.async_show_form(step_id="remove_area", data_schema=schema)
