"""Config flow for RTCM Stream Monitor integration."""
import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, DEFAULT_TIMEOUT, DEFAULT_UPDATE_INTERVAL
from .ntrip_client import NTRIPClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("host"): cv.string,
        vol.Required("port", default=2101): cv.port,
        vol.Required("mountpoint"): cv.string,
        vol.Optional("username", default=""): cv.string,
        vol.Optional("password", default=""): cv.string,
        vol.Optional("timeout", default=DEFAULT_TIMEOUT): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=60)
        ),
        vol.Optional("update_interval", default=DEFAULT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=300)
        ),
    }
)


async def validate_connection(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the connection to NTRIP server."""
    client = NTRIPClient(
        data["host"],
        data["port"],
        data["mountpoint"],
        data.get("username", ""),
        data.get("password", ""),
    )

    _LOGGER.info("Validating connection to %s:%s/%s", data["host"], data["port"], data["mountpoint"])
    
    try:
        # Try to connect and get at least one message with a timeout
        async def test_connection():
            """Test connection and get one message."""
            # Use a longer timeout (30s) during validation since some servers are slow
            connection_gen = client.connect(timeout=30)
            try:
                # Get the first message with longer timeout for validation
                _LOGGER.debug("Waiting for first RTCM message...")
                msg_info = await connection_gen.__anext__()
                msg_type = msg_info['id']
                sat_count = msg_info.get('satellites')
                if sat_count:
                    _LOGGER.info("Successfully validated connection, received RTCM message type %s (%d satellites)", msg_type, sat_count)
                else:
                    _LOGGER.info("Successfully validated connection, received RTCM message type %s", msg_type)
                return {"title": data["name"]}
            except StopAsyncIteration:
                _LOGGER.error("Connection generator stopped without yielding data")
                raise ConnectionError("Connection closed without receiving data")
            except Exception as e:
                _LOGGER.error("Error getting message from connection: %s", e, exc_info=True)
                raise
            finally:
                # Properly close the async generator
                try:
                    await connection_gen.aclose()
                    _LOGGER.debug("Connection generator closed successfully")
                except Exception as e:
                    _LOGGER.warning("Error closing connection generator: %s", e)
        
        # Wrap the entire validation in a longer timeout (45 seconds total)
        return await asyncio.wait_for(test_connection(), timeout=45.0)
        
    except asyncio.TimeoutError:
        _LOGGER.error("Connection validation timed out after 45 seconds")
        raise CannotConnect("Connection timeout - no RTCM data received within 45 seconds. Check if server is sending RTCM3 data.")
    except ConnectionError as err:
        _LOGGER.error("Connection error during validation: %s", err)
        raise CannotConnect(f"Connection failed: {err}")
    except Exception as err:
        _LOGGER.exception("Unexpected error during validation")
        raise CannotConnect(f"Unexpected error: {err}")


class RTCMMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RTCM Stream Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check for duplicate name
            await self.async_set_unique_id(user_input["name"].lower().replace(" ", "_"))
            self._abort_if_unique_id_configured()

            try:
                info = await validate_connection(self.hass, user_input)
            except CannotConnect as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Connection validation failed: %s", err)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return RTCMMonitorOptionsFlowHandler(config_entry)


class RTCMMonitorOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for RTCM Stream Monitor."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge with existing config for validation
            test_data = {**self.config_entry.data, **user_input}
            
            try:
                await validate_connection(self.hass, test_data)
            except CannotConnect as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Connection validation failed: %s", err)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during validation")
                errors["base"] = "unknown"
            else:
                # Update the config entry with new data
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, **user_input},
                )
                return self.async_create_entry(title="", data={})

        current_data = self.config_entry.data
        
        options_schema = vol.Schema(
            {
                vol.Required("host", default=current_data.get("host")): cv.string,
                vol.Required("port", default=current_data.get("port", 2101)): cv.port,
                vol.Required("mountpoint", default=current_data.get("mountpoint")): cv.string,
                vol.Optional("username", default=current_data.get("username", "")): cv.string,
                vol.Optional("password", default=current_data.get("password", "")): cv.string,
                vol.Optional(
                    "timeout", 
                    default=current_data.get("timeout", DEFAULT_TIMEOUT)
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Optional(
                    "update_interval", 
                    default=current_data.get("update_interval", DEFAULT_UPDATE_INTERVAL)
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

