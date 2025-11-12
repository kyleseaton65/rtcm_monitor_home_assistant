import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform

from .const import DOMAIN
from .coordinator import RTCMCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up RTCM Monitor from YAML (legacy support)."""
    hass.data.setdefault(DOMAIN, {})
    
    # Check if there's YAML configuration
    conf = config.get(DOMAIN, {})
    streams = conf.get("streams", [])

    if not streams:
        # No YAML config, that's fine - user will use UI
        return True

    _LOGGER.warning(
        "YAML configuration is deprecated. Please migrate to UI configuration via "
        "Settings > Devices & Services > Add Integration > RTCM Stream Monitor"
    )

    for stream_conf in streams:
        name = stream_conf["name"]
        
        # Validate required fields
        required_fields = ["host", "port", "mountpoint"]
        missing_fields = [field for field in required_fields if field not in stream_conf]
        if missing_fields:
            _LOGGER.error(
                "Stream '%s' missing required fields: %s", 
                name, 
                ", ".join(missing_fields)
            )
            continue
        
        coordinator = RTCMCoordinator(hass, stream_conf)
        hass.data[DOMAIN][name] = coordinator
        await coordinator.async_start()
        _LOGGER.info("Started RTCM stream monitor (YAML): %s", name)

        # Register entities using legacy discovery
        hass.async_create_task(
            discovery.async_load_platform(hass, "sensor", DOMAIN, {"name": name}, config)
        )
        hass.async_create_task(
            discovery.async_load_platform(hass, "binary_sensor", DOMAIN, {"name": name}, config)
        )

    async def cleanup(event):
        """Cleanup all coordinators on shutdown."""
        _LOGGER.info("Shutting down RTCM Monitor")
        for key, coordinator in list(hass.data[DOMAIN].items()):
            if isinstance(coordinator, RTCMCoordinator):
                await coordinator.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RTCM Stream Monitor from a config entry (UI)."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create coordinator
    coordinator = RTCMCoordinator(hass, entry.data)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Start the coordinator
    await coordinator.async_start()
    _LOGGER.info("Started RTCM stream monitor (UI): %s", entry.data["name"])
    
    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register update listener for options flow
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading RTCM stream monitor: %s", entry.data["name"])
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Stop and remove coordinator
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
