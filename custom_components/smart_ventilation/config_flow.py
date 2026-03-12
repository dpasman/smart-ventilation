import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import (
    DOMAIN,
    CONF_INDOOR_TEMP,
    CONF_INDOOR_HUM,
    CONF_OUTDOOR_TEMP,
    CONF_OUTDOOR_HUM,
    CONF_CO2,
    CONF_PM25_IN,
    CONF_PM25_OUT,
    CONF_WIND,
    CONF_HEAT_INDEX,
)

class SmartVentilationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Smart Ventilation."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Step for adding a new room."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("room_name"): str,
                    vol.Required(CONF_INDOOR_TEMP): selector.entity_selector({
                        selector.EntitySelectorFilter.INTEGRATION: "sensor",
                        selector.EntitySelectorFilter.DEVICE_CLASS: "temperature",
                    }),
                    vol.Required(CONF_INDOOR_HUM): selector.entity_selector({
                        selector.EntitySelectorFilter.INTEGRATION: "sensor",
                        selector.EntitySelectorFilter.DEVICE_CLASS: "humidity",
                    }),
                    vol.Optional(CONF_OUTDOOR_TEMP): selector.entity_selector({
                        selector.EntitySelectorFilter.INTEGRATION: "sensor",
                        selector.EntitySelectorFilter.DEVICE_CLASS: "temperature",
                    }),
                    vol.Optional(CONF_OUTDOOR_HUM): selector.entity_selector({
                        selector.EntitySelectorFilter.INTEGRATION: "sensor",
                        selector.EntitySelectorFilter.DEVICE_CLASS: "humidity",
                    }),
                    vol.Optional(CONF_CO2): selector.entity_selector({
                        selector.EntitySelectorFilter.INTEGRATION: "sensor",
                        selector.EntitySelectorFilter.DEVICE_CLASS: "carbon_dioxide",
                    }),
                    vol.Optional(CONF_PM25_IN): selector.entity_selector({
                        selector.EntitySelectorFilter.INTEGRATION: "sensor",
                        selector.EntitySelectorFilter.DEVICE_CLASS: "pm25",
                    }),
                    vol.Optional(CONF_PM25_OUT): selector.entity_selector({
                        selector.EntitySelectorFilter.INTEGRATION: "sensor",
                        selector.EntitySelectorFilter.DEVICE_CLASS: "pm25",
                    }),
                    vol.Optional(CONF_WIND): selector.entity_selector({
                        selector.EntitySelectorFilter.INTEGRATION: "sensor",
                        selector.EntitySelectorFilter.DEVICE_CLASS: "wind_speed",
                    }),
                    vol.Optional(CONF_HEAT_INDEX): selector.entity_selector({
                        selector.EntitySelectorFilter.INTEGRATION: "sensor",
                        selector.EntitySelectorFilter.DEVICE_CLASS: "temperature",
                    }),
                })
            )

        return self.async_create_entry(
            title=user_input["room_name"],
            data=user_input
        )