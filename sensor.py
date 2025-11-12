import logging
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RTCM sensors from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = [
        RTCMMessageTypesSensor(coordinator, entry.entry_id),
        RTCMLastMessageSensor(coordinator, entry.entry_id),
        RTCMMessageCountSensor(coordinator, entry.entry_id),
        RTCMSatelliteCountSensor(coordinator, entry.entry_id),
    ]
    
    _LOGGER.warning("Creating %d sensors for %s, including satellite sensor", len(sensors), coordinator.name)
    
    async_add_entities(sensors)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up RTCM sensors (legacy YAML support)."""
    if not discovery_info:
        return
    name = discovery_info["name"]
    coordinator = hass.data[DOMAIN][name]
    async_add_entities(
        [
            RTCMMessageTypesSensor(coordinator, name),
            RTCMLastMessageSensor(coordinator, name),
            RTCMMessageCountSensor(coordinator, name),
            RTCMSatelliteCountSensor(coordinator, name),
        ]
    )


class RTCMBaseSensor(SensorEntity):
    """Base class for RTCM sensors."""
    
    _attr_should_poll = False
    _attr_has_entity_name = True
    
    def __init__(self, coordinator, entry_id):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._entry_id = entry_id

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
    def device_info(self) -> DeviceInfo:
        """Return device information to link this entity with a device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"RTCM Stream: {self.coordinator.name}",
            manufacturer="NTRIP",
            model="RTCM3 Stream",
            configuration_url=f"http://{self.coordinator.host}:{self.coordinator.port}/{self.coordinator.mountpoint}",
        )


class RTCMMessageTypesSensor(RTCMBaseSensor):
    """Sensor showing RTCM message types received."""
    
    def __init__(self, coordinator, entry_id):
        """Initialize the sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_message_types"
        self._attr_name = f"{coordinator.name} Message Types"
        self._attr_icon = "mdi:message-text"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.message_types:
            return "None"
        return ",".join(str(t) for t in sorted(self.coordinator.message_types))

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        return {
            "message_types_list": sorted(self.coordinator.message_types),
            "unique_count": len(self.coordinator.message_types),
        }


class RTCMLastMessageSensor(RTCMBaseSensor):
    """Sensor showing last RTCM message received."""
    
    def __init__(self, coordinator, entry_id):
        """Initialize the sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_last_message"
        self._attr_name = f"{coordinator.name} Last Message"
        self._attr_icon = "mdi:message"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.last_message or "No data"

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attrs = {}
        
        if self.coordinator.last_message_type:
            attrs["message_type"] = self.coordinator.last_message_type
            
        if self.coordinator.last_update:
            attrs["last_update"] = self.coordinator.last_update.isoformat()
            
        return attrs


class RTCMMessageCountSensor(RTCMBaseSensor):
    """Sensor showing total message count."""
    
    def __init__(self, coordinator, entry_id):
        """Initialize the sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_message_count"
        self._attr_name = f"{coordinator.name} Message Count"
        self._attr_icon = "mdi:counter"
        self._attr_native_unit_of_measurement = "messages"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.message_count


class RTCMSatelliteCountSensor(RTCMBaseSensor):
    """Sensor showing satellite count from RTCM MSM messages."""
    
    def __init__(self, coordinator, entry_id):
        """Initialize the sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_satellite_count"
        self._attr_name = f"{coordinator.name} Satellites"
        self._attr_icon = "mdi:satellite-variant"
        self._attr_native_unit_of_measurement = "satellites"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        _LOGGER.warning("RTCMSatelliteCountSensor initialized: unique_id=%s, name=%s", 
                       self._attr_unique_id, self._attr_name)

    @property
    def native_value(self):
        """Return the total satellite count."""
        return self.coordinator.total_satellites

    @property
    def extra_state_attributes(self):
        """Return detailed satellite counts by constellation."""
        attrs = {
            "total_satellites": self.coordinator.total_satellites,
        }
        
        if self.coordinator.gps_satellites > 0:
            attrs["gps"] = self.coordinator.gps_satellites
            
        if self.coordinator.glonass_satellites > 0:
            attrs["glonass"] = self.coordinator.glonass_satellites
            
        if self.coordinator.galileo_satellites > 0:
            attrs["galileo"] = self.coordinator.galileo_satellites
            
        if self.coordinator.beidou_satellites > 0:
            attrs["beidou"] = self.coordinator.beidou_satellites
            
        return attrs
