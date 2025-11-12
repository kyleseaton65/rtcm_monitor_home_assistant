from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RTCM binary sensors from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RTCMConnectionBinarySensor(coordinator, entry.entry_id)])


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up RTCM binary sensors (legacy YAML support)."""
    if not discovery_info:
        return
    name = discovery_info["name"]
    coordinator = hass.data[DOMAIN][name]
    async_add_entities([RTCMConnectionBinarySensor(coordinator, name)])


class RTCMConnectionBinarySensor(BinarySensorEntity):
    """Binary sensor for RTCM stream connection status."""
    
    _attr_should_poll = False
    
    def __init__(self, coordinator, entry_id):
        """Initialize the binary sensor."""
        self.coordinator = coordinator
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_connected"
        self._attr_name = f"{coordinator.name} Connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_has_entity_name = True

    async def async_added_to_hass(self):
        """Register callbacks when entity is added."""
        self.coordinator.register_listener(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        self.coordinator.remove_listener(self._handle_coordinator_update)

    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Return True if stream is connected."""
        return self.coordinator.connected

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attrs = {
            "host": self.coordinator.host,
            "port": self.coordinator.port,
            "mountpoint": self.coordinator.mountpoint,
        }
        
        if self.coordinator.connection_time:
            attrs["connected_since"] = self.coordinator.connection_time.isoformat()
            
        if self.coordinator.error_message:
            attrs["last_error"] = self.coordinator.error_message
            
        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information to link this entity with a device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"RTCM Stream: {self.coordinator.name}",
            manufacturer="NTRIP",
            model="RTCM3 Stream",
            configuration_url=f"http://{self.coordinator.host}:{self.coordinator.port}/{self.coordinator.mountpoint}",
        )
