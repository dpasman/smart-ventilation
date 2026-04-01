"""Config flow for Smart Ventilation integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar, selector

from .const import (
    CONF_AREA_NAME,
    CONF_INDOOR_CO2,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_PM25,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_ABS_HUMIDITY,
    CONF_OUTDOOR_DEW_POINT,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_PM25,
    CONF_OUTDOOR_TEMP,
    CONF_OUTDOOR_TEMP_MAX_24H,
    CONF_WIND_AVG,
    CONF_WIND_MAX,
    DOMAIN,
)


def _area_schema() -> vol.Schema:
    """Shared schema for add and edit area forms."""
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

    def _resolve_area(self, area_id: str) -> str:
        """Return the human-readable area name from the HA area registry."""
        entry = ar.async_get(self.hass).async_get_area(area_id)
        return entry.name if entry else area_id

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Show area management menu, or go straight to add if no areas exist."""
        if not self._get_areas():
            return await self.async_step_add_area()

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="add"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="add", label="Add Area"),
                                selector.SelectOptionDict(value="edit", label="Edit Area"),
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
        """Route menu selection to add, edit or remove step."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_area()
            if action == "edit":
                return await self.async_step_edit_area_select()
            if action == "remove":
                return await self.async_step_remove_area()
        return await self.async_step_init()

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
            return self.async_create_entry(title="", data={"areas": areas})

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
            return self.async_create_entry(title="", data={"areas": new_areas})

        suggested: dict = {}
        if current:
            suggested = {
                CONF_AREA_NAME: current.get("area_id", ""),
                CONF_INDOOR_TEMP: current.get(CONF_INDOOR_TEMP),
                CONF_INDOOR_HUMIDITY: current.get(CONF_INDOOR_HUMIDITY),
                CONF_INDOOR_CO2: current.get(CONF_INDOOR_CO2),
                CONF_INDOOR_PM25: current.get(CONF_INDOOR_PM25),
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
            return self.async_create_entry(title="", data={"areas": new_areas})

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
