import asyncio
import base64
import logging
import sys

_LOGGER = logging.getLogger(__name__)

# Ensure debug logs are visible
_LOGGER.setLevel(logging.DEBUG)


class NTRIPClient:
    """Minimal async NTRIP v1 client for RTCM monitoring."""

    def __init__(self, host, port, mountpoint, username="", password=""):
        self.host = host
        self.port = port
        self.mountpoint = mountpoint
        self.username = username
        self.password = password

    async def connect(self, timeout=10):
        """Async generator yielding RTCM message types."""
        # Force log output
        print(f"[RTCM] Starting connection to {self.host}:{self.port}/{self.mountpoint}", file=sys.stderr)
        _LOGGER.warning("NTRIP Client: Starting connection to %s:%s/%s", self.host, self.port, self.mountpoint)
        
        auth = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        
        reader = None
        writer = None
        
        try:
            print(f"[RTCM] Opening TCP connection...", file=sys.stderr)
            _LOGGER.warning("Opening TCP connection to %s:%s", self.host, self.port)
            
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), 
                timeout=10
            )
            
            print(f"[RTCM] TCP connected successfully", file=sys.stderr)
            _LOGGER.warning("TCP connection established")
            
        except (OSError, asyncio.TimeoutError) as e:
            print(f"[RTCM] ERROR: Failed to connect: {e}", file=sys.stderr)
            _LOGGER.error("Failed to connect to %s:%s: %s", self.host, self.port, e)
            raise ConnectionError(f"Failed to connect to {self.host}:{self.port}: {e}")
        
        try:
            # Build NTRIP request (standard HTTP/1.0 format)
            request = (
                f"GET /{self.mountpoint} HTTP/1.0\r\n"
                f"User-Agent: NTRIP HomeAssistant\r\n"
                f"Accept: */*\r\n"
                f"Authorization: Basic {auth}\r\n"
                f"\r\n"
            )
            
            print(f"[RTCM] Sending NTRIP request", file=sys.stderr)
            _LOGGER.warning("Sending NTRIP request for mountpoint: %s", self.mountpoint)
            
            writer.write(request.encode('utf-8'))
            await writer.drain()
            
            print(f"[RTCM] Request sent, waiting for response...", file=sys.stderr)
            _LOGGER.warning("Request sent, waiting for HTTP response")
            
            # Read first chunk of response (may contain headers + data)
            try:
                # Read up to 8KB to get headers and possibly some data
                initial_data = await asyncio.wait_for(reader.read(8192), timeout=10)
                
                if not initial_data:
                    print(f"[RTCM] ERROR: No response from server", file=sys.stderr)
                    raise ConnectionError("Server closed connection without sending response")
                
                print(f"[RTCM] Received {len(initial_data)} bytes", file=sys.stderr)
                _LOGGER.warning("Received initial response: %d bytes", len(initial_data))
                
                # Try to parse HTTP response
                data_str = initial_data.decode('utf-8', errors='ignore')
                first_line = data_str.split('\n')[0].strip()
                
                print(f"[RTCM] First line: {first_line}", file=sys.stderr)
                _LOGGER.warning("HTTP Response: %s", first_line)
                
                # Check for success (HTTP 200 or ICY 200)
                if "200" not in first_line:
                    print(f"[RTCM] ERROR: Server rejected connection: {first_line}", file=sys.stderr)
                    raise ConnectionError(f"NTRIP server returned: {first_line}")
                
                print(f"[RTCM] Server accepted connection (200 OK)", file=sys.stderr)
                _LOGGER.warning("Server accepted connection")
                
                # Find end of headers (\r\n\r\n or \n\n)
                header_end = initial_data.find(b"\r\n\r\n")
                if header_end == -1:
                    header_end = initial_data.find(b"\n\n")
                    if header_end != -1:
                        header_end += 2
                else:
                    header_end += 4
                
                # Start buffer with data after headers
                if header_end > 0:
                    buffer = initial_data[header_end:]
                    print(f"[RTCM] Found {len(buffer)} bytes after headers", file=sys.stderr)
                    _LOGGER.warning("Headers complete, %d bytes of data in buffer", len(buffer))
                else:
                    # No clear header end, treat everything as data
                    buffer = initial_data
                    print(f"[RTCM] No header delimiter found, treating all as data", file=sys.stderr)
                    _LOGGER.warning("No clear header end, using all data as buffer")
                    
            except asyncio.TimeoutError:
                print(f"[RTCM] ERROR: Timeout waiting for response", file=sys.stderr)
                _LOGGER.error("Timeout waiting for HTTP response from server")
                raise ConnectionError("Timeout waiting for HTTP response (10s)")
            
            print(f"[RTCM] Starting data stream reading...", file=sys.stderr)
            _LOGGER.warning("Connected, starting RTCM data reading loop")
            
            message_count = 0
            
            while True:
                # Process any data in buffer first
                if buffer:
                    buffer, messages = self._process_buffer(buffer)
                    
                    for msg_info in messages:
                        message_count += 1
                        msg_id = msg_info['id']
                        sat_count = msg_info.get('satellites')
                        
                        if sat_count:
                            print(f"[RTCM] Message #{message_count}: RTCM type {msg_id} ({sat_count} satellites)", file=sys.stderr)
                            _LOGGER.warning("Parsed RTCM message: type=%d (count=%d, satellites=%d)", msg_id, message_count, sat_count)
                        else:
                            print(f"[RTCM] Message #{message_count}: RTCM type {msg_id}", file=sys.stderr)
                            _LOGGER.warning("Parsed RTCM message: type=%d (count=%d)", msg_id, message_count)
                        
                        yield msg_info
                
                # Read more data
                try:
                    data = await asyncio.wait_for(reader.read(4096), timeout=timeout)
                except asyncio.TimeoutError:
                    print(f"[RTCM] WARNING: Read timeout after {timeout}s", file=sys.stderr)
                    _LOGGER.warning("Timeout reading data from stream (timeout=%ds)", timeout)
                    raise
                    
                if not data:
                    print(f"[RTCM] ERROR: Server closed connection", file=sys.stderr)
                    _LOGGER.error("Server closed connection")
                    raise ConnectionError("Stream closed by server")
                
                buffer += data
                    
        finally:
            if writer:
                print(f"[RTCM] Closing connection", file=sys.stderr)
                writer.close()
                await writer.wait_closed()
                _LOGGER.warning("Connection closed")

    def _process_buffer(self, buffer):
        """Process buffer, extract message IDs and satellite info, return remaining buffer and message info."""
        original_len = len(buffer)
        
        # Trim invalid bytes from start (keep valid RTCM framing 0xD3 start)
        trimmed = 0
        while buffer and buffer[0] != 0xD3:
            buffer = buffer[1:]
            trimmed += 1
        
        if trimmed > 0:
            _LOGGER.debug("Trimmed %d non-RTCM bytes from buffer start", trimmed)
        
        messages = []  # List of dicts with message info
        idx = 0
        
        while len(buffer) - idx >= 6:
            if buffer[idx] != 0xD3:
                idx += 1
                continue
                
            # Extract message length from RTCM header
            msg_len = ((buffer[idx + 1] & 0x03) << 8) | buffer[idx + 2]
            
            # Check if we have complete message (header + payload + CRC)
            total_msg_len = msg_len + 6
            if len(buffer) - idx < total_msg_len:
                _LOGGER.debug("Incomplete message: have %d bytes, need %d", len(buffer) - idx, total_msg_len)
                break
                
            # Extract message ID (12 bits)
            msg_id = (buffer[idx + 3] << 4) | (buffer[idx + 4] >> 4)
            
            # Parse satellite count for MSM messages
            sat_count = self._parse_msm_satellite_count(buffer[idx:idx+total_msg_len], msg_id)
            
            message_info = {
                'id': msg_id,
                'length': msg_len,
                'satellites': sat_count
            }
            
            messages.append(message_info)
            _LOGGER.debug("Found RTCM message: ID=%d, length=%d bytes, satellites=%s", 
                         msg_id, msg_len, sat_count if sat_count else 'N/A')
            idx += total_msg_len
        
        # Return remaining buffer and extracted messages
        remaining_buffer = buffer[idx:]
        _LOGGER.debug("Buffer processing: original=%d, remaining=%d, messages=%d", 
                     original_len, len(remaining_buffer), len(messages))
        return remaining_buffer, messages
    
    def _parse_msm_satellite_count(self, message, msg_id):
        """Parse observation messages to extract satellite count."""
        # Legacy RTCM3 observation messages (contain satellite count directly)
        legacy_obs_messages = {
            1001: 'gps',    # GPS L1 RTK
            1002: 'gps',    # GPS L1 Extended RTK
            1003: 'gps',    # GPS L1&L2 RTK
            1004: 'gps',    # GPS L1&L2 Extended RTK
            1009: 'glonass', # GLONASS L1 RTK
            1010: 'glonass', # GLONASS L1 Extended RTK
            1011: 'glonass', # GLONASS L1&L2 RTK
            1012: 'glonass', # GLONASS L1&L2 Extended RTK
        }
        
        # Check if it's a legacy observation message
        if msg_id in legacy_obs_messages:
            return self._parse_legacy_obs_satellite_count(message, msg_id)
        
        # MSM message types: 1074-1077 (GPS), 1084-1087 (GLONASS), 
        # 1094-1097 (Galileo), 1124-1127 (BeiDou), 1114-1117 (QZSS)
        msm_ranges = [
            (1074, 1077),  # GPS MSM4-7
            (1084, 1087),  # GLONASS MSM4-7
            (1094, 1097),  # Galileo MSM4-7
            (1114, 1117),  # QZSS MSM4-7
            (1124, 1127),  # BeiDou MSM4-7
        ]
        
        is_msm = any(start <= msg_id <= end for start, end in msm_ranges)
        
        if not is_msm or len(message) < 14:
            return None
        
        try:
            # MSM header structure (after message ID):
            # - 12 bits: Message ID (already extracted)
            # - 12 bits: Station ID
            # - 30 bits: Epoch time
            # - 1 bit: Multiple message bit
            # - 3 bits: Issue of Data Station
            # - 7 bits: Reserved
            # - 2 bits: Clock steering
            # - 2 bits: External clock
            # - 1 bit: Divergence-free smoothing
            # - 3 bits: Smoothing interval
            # - 64 bits: Satellite mask (which satellites are included)
            # - 32 bits: Signal mask (which signals per satellite)
            
            # Byte offset in message: skip 3 bytes of header, then message-specific header
            # We need to get to the 64-bit satellite mask
            # Header: 3 bytes, Message ID already used in first 12 bits of payload
            
            # For MSM: payload starts at byte 3 (after preamble, reserved, length)
            # First 12 bits of payload are message ID (already extracted)
            # Next 12 bits: Station ID
            # Next 30 bits: Epoch time
            # ... other fields ...
            # At bit position ~69 from start of payload: 64-bit satellite mask
            
            # Simplified parsing: Read bytes 11-18 which should contain satellite mask
            # This is approximate - exact position varies by message type
            if len(message) < 20:
                return None
            
            # Extract satellite mask (64 bits starting around byte 11)
            # Note: This is a simplified approach
            sat_mask_bytes = message[11:19]
            sat_mask = int.from_bytes(sat_mask_bytes, byteorder='big')
            
            # Count number of 1 bits in the mask
            sat_count = bin(sat_mask).count('1')
            
            return sat_count if sat_count > 0 else None
            
        except Exception as e:
            _LOGGER.debug("Error parsing MSM satellite count for message %d: %s", msg_id, e)
            return None
    
    def _parse_legacy_obs_satellite_count(self, message, msg_id):
        """Parse legacy RTCM3 observation messages (1001-1004, 1009-1012) for satellite count."""
        try:
            # Legacy observation message structure:
            # Bytes 0-2: RTCM header (0xD3, reserved+length)
            # Byte 3+: Payload
            #
            # GPS messages (1001-1004):
            #   - 12 bits: Message number
            #   - 12 bits: Reference Station ID  
            #   - 30 bits: GPS Epoch Time
            #   - 1 bit: Synchronous GNSS Flag
            #   - 5 bits: Number of GPS satellites
            #
            # GLONASS messages (1009-1012):
            #   - 12 bits: Message number
            #   - 12 bits: Reference Station ID  
            #   - 27 bits: GLONASS Epoch Time (DIFFERENT!)
            #   - 1 bit: Synchronous GNSS Flag
            #   - 5 bits: Number of GLONASS satellites
            
            if len(message) < 10:
                return None
            
            # Determine if GPS or GLONASS to know bit positions
            is_glonass = 1009 <= msg_id <= 1012
            
            # Calculate bit position of satellite count
            if is_glonass:
                # GLONASS: 12 + 12 + 27 + 1 = 52 bits before sat count
                bits_before_sat_count = 52
            else:
                # GPS: 12 + 12 + 30 + 1 = 55 bits before sat count
                bits_before_sat_count = 55
            
            # Create a bit array from bytes 3-10 (should be enough)
            payload_bytes = message[3:11]
            if len(payload_bytes) < 8:
                return None
            
            # Convert to integer (big endian)
            bit_stream = int.from_bytes(payload_bytes, byteorder='big')
            
            # We have 64 bits (8 bytes)
            # Skip bits_before_sat_count, then read 5 bits
            shift_amount = 64 - bits_before_sat_count - 5
            sat_count = (bit_stream >> shift_amount) & 0x1F  # 0x1F = 0b11111
            
            constellation = "GLONASS" if is_glonass else "GPS"
            print(f"[RTCM] Legacy {constellation} message {msg_id}: bits_before={bits_before_sat_count}, shift={shift_amount}, sat_count={sat_count}", file=sys.stderr)
            _LOGGER.warning("Legacy %s message %d: satellite count=%d", constellation, msg_id, sat_count)
            
            if 0 <= sat_count <= 64:  # Sanity check (allow 0)
                return sat_count if sat_count > 0 else None
            
            return None
            
        except Exception as e:
            _LOGGER.debug("Error parsing legacy obs satellite count for message %d: %s", msg_id, e)
            return None
