import asyncio
import logging
from datetime import datetime, timezone
from .ntrip_client import NTRIPClient
from .const import DEFAULT_TIMEOUT, DEFAULT_UPDATE_INTERVAL, MAX_MESSAGE_TYPES

_LOGGER = logging.getLogger(__name__)


class RTCMCoordinator:
    """Manages one RTCM stream connection."""

    def __init__(self, hass, conf):
        self.hass = hass
        self.name = conf["name"]
        self.host = conf["host"]
        self.port = conf["port"]
        self.mountpoint = conf["mountpoint"]
        self.username = conf.get("username", "")
        self.password = conf.get("password", "")
        self.timeout = conf.get("timeout", DEFAULT_TIMEOUT)
        self.update_interval = conf.get("update_interval", DEFAULT_UPDATE_INTERVAL)

        self.connected = False
        self.last_message = None
        self.last_message_type = None
        self.message_types = []  # List to limit size
        self.message_count = 0
        self.last_update = None
        self.connection_time = None
        self.error_message = None
        
        # Satellite tracking
        self.satellite_count = 0
        self.gps_satellites = 0
        self.glonass_satellites = 0
        self.galileo_satellites = 0
        self.beidou_satellites = 0
        self.total_satellites = 0
        
        self.client = NTRIPClient(
            self.host, self.port, self.mountpoint, self.username, self.password
        )
        self.task = None
        self.update_task = None
        self._stop_event = asyncio.Event()
        self._listeners = []

    def register_listener(self, update_callback):
        """Register a callback to be called on state updates."""
        self._listeners.append(update_callback)

    def remove_listener(self, update_callback):
        """Remove a previously registered callback."""
        if update_callback in self._listeners:
            self._listeners.remove(update_callback)

    async def _notify_listeners(self):
        """Notify all registered listeners of state change."""
        for callback in self._listeners:
            callback()

    async def async_start(self):
        """Start connection coroutine."""
        if not self.task or self.task.done():
            self._stop_event.clear()
            self.task = asyncio.create_task(self._run())
            self.update_task = asyncio.create_task(self._periodic_update())

    async def async_stop(self):
        """Stop the coordinator and cleanup."""
        _LOGGER.info("[%s] Stopping coordinator", self.name)
        self._stop_event.set()
        
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
                
        if self.update_task and not self.update_task.done():
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

    async def _periodic_update(self):
        """Periodically notify listeners to update HA state."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.update_interval)
                await self._notify_listeners()
            except asyncio.CancelledError:
                break

    async def _run(self):
        """Keep connection alive and reconnect as needed."""
        while not self._stop_event.is_set():
            try:
                self.error_message = None
                async for msg_info in self.client.connect(timeout=self.timeout):
                    if self._stop_event.is_set():
                        break
                    
                    # Extract message info
                    msg_type = msg_info['id']
                    sat_count = msg_info.get('satellites')
                        
                    if not self.connected:
                        self.connected = True
                        self.connection_time = datetime.now(timezone.utc)
                        _LOGGER.info("[%s] Stream connected", self.name)
                        
                    self.last_update = datetime.now(timezone.utc)
                    self.last_message_type = msg_type
                    self.message_count += 1
                    
                    # Track unique message types with size limit
                    if msg_type not in self.message_types:
                        self.message_types.append(msg_type)
                        if len(self.message_types) > MAX_MESSAGE_TYPES:
                            self.message_types = self.message_types[-MAX_MESSAGE_TYPES:]
                    
                    # Update satellite counts by constellation
                    if sat_count:
                        # Legacy observation messages
                        if 1001 <= msg_type <= 1004:  # GPS legacy obs
                            self.gps_satellites = sat_count
                        elif 1009 <= msg_type <= 1012:  # GLONASS legacy obs
                            self.glonass_satellites = sat_count
                        # MSM messages
                        elif 1074 <= msg_type <= 1077:  # GPS MSM
                            self.gps_satellites = sat_count
                        elif 1084 <= msg_type <= 1087:  # GLONASS MSM
                            self.glonass_satellites = sat_count
                        elif 1094 <= msg_type <= 1097:  # Galileo MSM
                            self.galileo_satellites = sat_count
                        elif 1124 <= msg_type <= 1127:  # BeiDou MSM
                            self.beidou_satellites = sat_count
                        
                        # Update total (sum of all constellations)
                        self.total_satellites = (
                            self.gps_satellites +
                            self.glonass_satellites +
                            self.galileo_satellites +
                            self.beidou_satellites
                        )
                    
                    if sat_count:
                        self.last_message = f"RTCM {msg_type} ({sat_count} sats)"
                    else:
                        self.last_message = f"RTCM {msg_type}"
                    
            except asyncio.TimeoutError:
                _LOGGER.warning("[%s] Timeout - reconnecting", self.name)
                self.connected = False
                self.error_message = "Connection timeout"
                await self._notify_listeners()
            except (OSError, ConnectionError) as e:
                _LOGGER.error("[%s] Connection error: %s", self.name, e)
                self.connected = False
                self.error_message = str(e)
                await self._notify_listeners()
            except Exception as e:
                _LOGGER.error("[%s] Stream error: %s", self.name, e, exc_info=True)
                self.connected = False
                self.error_message = str(e)
                await self._notify_listeners()

            if not self._stop_event.is_set():
                await asyncio.sleep(5)
