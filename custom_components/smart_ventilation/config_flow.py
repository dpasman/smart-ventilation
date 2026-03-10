import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
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
            # Show the form
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("room_name"): str,
                    vol.Required(CONF_INDOOR_TEMP): str,
                    vol.Required(CONF_INDOOR_HUM): str,
                    vol.Optional(CONF_OUTDOOR_TEMP): str,
                    vol.Optional(CONF_OUTDOOR_HUM): str,
                    vol.Optional(CONF_CO2): str,
                    vol.Optional(CONF_PM25_IN): str,
                    vol.Optional(CONF_PM25_OUT): str,
                    vol.Optional(CONF_WIND): str,
                    vol.Optional(CONF_HEAT_INDEX): str,
                })
            )

        # Validate that the required sensors exist
        hass = self.hass
        errors = {}
        for sensor_key in [CONF_INDOOR_TEMP, CONF_INDOOR_HUM]:
            sensor_id = user_input.get(sensor_key)
            if not hass.states.get(sensor_id):
                errors[sensor_key] = "invalid_sensor"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("room_name"): str,
                    vol.Required(CONF_INDOOR_TEMP): str,
                    vol.Required(CONF_INDOOR_HUM): str,
                    vol.Optional(CONF_OUTDOOR_TEMP): str,
                    vol.Optional(CONF_OUTDOOR_HUM): str,
                    vol.Optional(CONF_CO2): str,
                    vol.Optional(CONF_PM25_IN): str,
                    vol.Optional(CONF_PM25_OUT): str,
                    vol.Optional(CONF_WIND): str,
                    vol.Optional(CONF_HEAT_INDEX): str,
                }),
                errors=errors,
            )

        # Create a config entry for this room
        return self.async_create_entry(
            title=user_input["room_name"],
            data=user_input
        )