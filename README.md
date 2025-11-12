# RTCM Stream Monitor for Home Assistant

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.8+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

Monitor NTRIP RTCM3 streams in Home Assistant with real-time connection status, message tracking, and **satellite counts by constellation**.

## ✨ Features

### Core Monitoring
- 🛰️ **Satellite Tracking** - Real-time GPS, GLONASS, Galileo, and BeiDou satellite counts
- 📡 **Connection Monitoring** - Live connection status with automatic reconnection
- 📊 **Message Analysis** - Tracks all RTCM message types received
- 📈 **Statistics** - Message counts and stream health monitoring
- 🔄 **Auto-Reconnect** - Automatic reconnection on failures with error logging

### Integration Features
- 🎛️ **UI Configuration** - Easy setup through Home Assistant web interface
- ✅ **Connection Validation** - Tests NTRIP connection before saving
- 📱 **Device Support** - Each stream appears as a device with grouped entities
- 🔔 **Rich Attributes** - Detailed state information for automations
- ⚡ **Live Updates** - Push-based updates (no polling)
- 🌐 **Multi-Stream** - Monitor multiple NTRIP streams simultaneously

### RTCM Format Support
- Legacy observation messages: 1001-1004 (GPS), 1009-1012 (GLONASS)
- MSM messages: 1074-1077 (GPS), 1084-1087 (GLONASS), 1094-1097 (Galileo), 1124-1127 (BeiDou)
- Station information: 1005-1006, 1008, 1033
- All standard RTCM3 message types

## 📥 Installation

### Method 1: Manual Installation (Current)

1. **Download** this repository
2. **Copy** the `rtcm_monitor` folder to `<config_dir>/custom_components/`
3. **Restart** Home Assistant
4. **Add integration** via UI (Settings → Devices & Services → Add Integration)

### Method 2: HACS (Coming Soon)

1. Open **HACS**
2. Go to **Integrations**
3. Click **⋮** → **Custom repositories**
4. Add: `https://github.com/YOUR_USERNAME/rtcm_monitor`
5. Click **Install**
6. Restart Home Assistant

### Verification

After installation, "RTCM Stream Monitor" should appear in:
**Settings → Devices & Services → Add Integration** (search for "RTCM")

## Quick Start - UI Configuration (Recommended) ⭐

The easiest way to set up RTCM Stream Monitor:

1. Go to **Settings** → **Devices & Services**
2. Click **+ ADD INTEGRATION**
3. Search for "**RTCM Stream Monitor**"
4. Fill in your stream details:
   - Stream Name (e.g., "Base Station 1")
   - NTRIP Server Host
   - Port (usually 2101)
   - Mountpoint
   - Username/Password (if required)
5. Click **Submit**

The integration will test the connection and create entities automatically!

## Configuration via YAML (Legacy)

> **Note:** YAML configuration is deprecated. Please use UI configuration above.

Add the following to your `configuration.yaml`:

```yaml
rtcm_monitor:
  streams:
    - name: "Base Station 1"
      host: "ntrip.example.com"
      port: 2101
      mountpoint: "MOUNT1"
      username: "your_username"  # Optional
      password: "your_password"  # Optional
      timeout: 10  # Optional, default 10 seconds
      update_interval: 30  # Optional, default 30 seconds
    
    - name: "Base Station 2"
      host: "192.168.1.100"
      port: 2101
      mountpoint: "BASE"
```

### Configuration Variables

- **name** (*Required*): Friendly name for the stream
- **host** (*Required*): NTRIP caster hostname or IP address
- **port** (*Required*): NTRIP caster port (usually 2101)
- **mountpoint** (*Required*): NTRIP mountpoint name
- **username** (*Optional*): Authentication username
- **password** (*Optional*): Authentication password
- **timeout** (*Optional*): Connection timeout in seconds (default: 10)
- **update_interval** (*Optional*): How often to push state updates to HA in seconds (default: 30)

## 📊 Entities Created

For each configured stream, **5 entities** are created under a single device:

### Binary Sensor
| Entity | Description | Attributes |
|--------|-------------|------------|
| **[Name] Connected** | Connection status (On/Off) | `host`, `port`, `mountpoint`, `connected_since`, `last_error` |

### Sensors
| Entity | Description | Attributes |
|--------|-------------|------------|
| **[Name] Satellites** | 🛰️ Total satellite count | `total_satellites`, `gps`, `glonass`, `galileo`, `beidou` |
| **[Name] Message Types** | Comma-separated RTCM message types | `message_types_list`, `unique_count` |
| **[Name] Last Message** | Most recent RTCM message | `message_type`, `last_update` |
| **[Name] Message Count** | Total messages received | *(none)* |

### Example Values

```yaml
# Binary Sensor
binary_sensor.base_station_connected: on

# Satellite Sensor (NEW!)
sensor.base_station_satellites: 22
  attributes:
    total_satellites: 22
    gps: 12
    glonass: 10
    galileo: 0
    beidou: 0

# Other Sensors
sensor.base_station_message_types: "1004,1006,1008,1012,1033"
sensor.base_station_last_message: "RTCM 1012 (10 sats)"
sensor.base_station_message_count: 45678
```

## 📱 Example Usage

### Dashboard Card

```yaml
type: entities
title: RTCM Base Station
entities:
  - entity: binary_sensor.base_station_connected
    name: Connection
    secondary_info: last-changed
  - entity: sensor.base_station_satellites
    name: Satellites Tracked
    icon: mdi:satellite-variant
  - entity: sensor.base_station_message_count
    name: Messages
  - entity: sensor.base_station_message_types
    name: Message Types
  - type: attribute
    entity: sensor.base_station_satellites
    attribute: gps
    name: GPS Satellites
  - type: attribute
    entity: sensor.base_station_satellites
    attribute: glonass
    name: GLONASS Satellites
```

### Automations

#### Alert on Connection Loss
```yaml
automation:
  - alias: "RTCM Stream Disconnected"
    trigger:
      - platform: state
        entity_id: binary_sensor.base_station_connected
        to: "off"
        for: "00:05:00"
    action:
      - service: notify.notify
        data:
          message: "RTCM stream disconnected for 5 minutes!"
```

#### Alert on Low Satellite Count
```yaml
automation:
  - alias: "Low Satellite Count"
    trigger:
      - platform: numeric_state
        entity_id: sensor.base_station_satellites
        below: 8
        for: "00:05:00"
    action:
      - service: notify.notify
        data:
          message: >
            Only {{ states('sensor.base_station_satellites') }} satellites tracked!
            GPS: {{ state_attr('sensor.base_station_satellites', 'gps') }}
            GLONASS: {{ state_attr('sensor.base_station_satellites', 'glonass') }}
```

#### Daily Status Report
```yaml
automation:
  - alias: "Daily RTCM Report"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: notify.notify
        data:
          message: >
            📡 RTCM Stream Status:
            Connected: {{ states('binary_sensor.base_station_connected') }}
            Satellites: {{ states('sensor.base_station_satellites') }}
            Messages: {{ states('sensor.base_station_message_count') }}
            Types: {{ states('sensor.base_station_message_types') }}
```

### Template Sensors

#### Message Rate
```yaml
template:
  - sensor:
      - name: "RTCM Message Rate"
        unit_of_measurement: "msg/min"
        state: >
          {% set count = states('sensor.base_station_message_count') | int %}
          {% set since = state_attr('binary_sensor.base_station_connected', 'connected_since') %}
          {% if since %}
            {% set minutes = (as_timestamp(now()) - as_timestamp(since)) / 60 %}
            {{ (count / minutes) | round(1) if minutes > 0 else 0 }}
          {% else %}
            0
          {% endif %}
```

#### GPS Satellite Count
```yaml
template:
  - sensor:
      - name: "GPS Satellites"
        unit_of_measurement: "satellites"
        icon: mdi:satellite-variant
        state: "{{ state_attr('sensor.base_station_satellites', 'gps') | default(0) }}"
```

## Troubleshooting

### Check Logs
Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.rtcm_monitor: debug
```

### Common Issues

1. **Connection Refused**
   - Check host, port, and mountpoint are correct
   - Verify network connectivity from Home Assistant to NTRIP server
   - Check firewall rules

2. **Authentication Failed**
   - Verify username and password
   - Some servers require authentication, others don't
   - Check if credentials are correct on NTRIP caster website

3. **No Satellite Count Showing**
   - Satellite sensor shows `0` → Stream isn't sending observation messages
   - Check `message_types` sensor - should include 1001-1004, 1009-1012, or 1074-1127
   - Some casters only send station info (1005, 1006, 1008, 1033) without observations
   - Enable debug logging to see parsed satellite counts in logs

4. **Wrong Satellite Count**
   - Compare with NTRIP caster's display
   - Check logs for: `Legacy GPS/GLONASS message XXXX: satellite count=N`
   - Report discrepancies with RTCM message type and caster info

5. **Entities Not Showing**
   - Restart Home Assistant after installation
   - Check **Settings → Devices & Services → Devices** for the device
   - Look for disabled entities

## 🔧 How It Works

### Connection & Parsing
1. **Connects** to NTRIP caster using HTTP/1.0 protocol
2. **Validates** HTTP response and skips headers
3. **Reads** binary RTCM3 stream (0xD3 frame sync)
4. **Parses** each RTCM3 message:
   - Extracts message type ID (12-bit field)
   - For observation messages: extracts satellite count (5-bit field)
   - Handles both legacy (1001-1004, 1009-1012) and MSM (1074-1127) formats
5. **Updates** Home Assistant entities every 30 seconds (configurable)
6. **Reconnects** automatically on disconnection with 5-second retry

### Satellite Parsing

The integration parses satellite counts from RTCM observation messages:

| Message Type | Constellation | Format | Satellite Field |
|--------------|---------------|--------|----------------|
| 1001-1004 | GPS | Legacy | 5-bit count after 55 bits of header |
| 1009-1012 | GLONASS | Legacy | 5-bit count after 52 bits of header* |
| 1074-1077 | GPS | MSM | 64-bit satellite mask |
| 1084-1087 | GLONASS | MSM | 64-bit satellite mask |
| 1094-1097 | Galileo | MSM | 64-bit satellite mask |
| 1124-1127 | BeiDou | MSM | 64-bit satellite mask |

***Note:** GLONASS messages use a 27-bit epoch time field (vs 30-bit for GPS), resulting in different bit positions.

### Resource Usage

- **Memory**: ~4.5 KB per stream (constant, doesn't grow)
- **Message types**: Limited to 50 unique types (prevents unbounded growth)
- **Updates**: Push-based via callbacks (no polling)
- **Network**: Minimal - only RTCM data stream


## 🤝 Contributing

Found a bug or want to contribute? 

1. Check existing issues or create a new one
2. Fork the repository
3. Make your changes
4. Submit a pull request

### Reporting Issues

When reporting issues, please include:
- Home Assistant version
- RTCM Monitor version
- NTRIP caster type (if known)
- RTCM message types from your stream
- Relevant log entries with debug logging enabled

## ⭐ Support

If you find this integration useful:
- ⭐ **Star this repository**
- 🐛 **Report bugs** via GitHub Issues
- 💡 **Suggest features** via GitHub Issues
- 📖 **Improve documentation** via Pull Requests

## 📋 Requirements

- **Home Assistant**: 2023.8 or newer
- **NTRIP Access**: Valid NTRIP caster credentials (if required)
- **Network**: Home Assistant must be able to reach NTRIP server

## 🔒 License

MIT License - see [LICENSE](LICENSE) file for details.

This project is provided as-is for use with Home Assistant.

## 📝 Version History

### 2.0.0 (Current)
- ✨ **NEW**: Satellite tracking by constellation (GPS, GLONASS, Galileo, BeiDou)
- ✨ **NEW**: UI configuration with config flow
- ✨ **NEW**: Connection validation before saving
- ✨ **NEW**: Options flow for reconfiguration
- ✨ Proper device support with grouped entities
- ✨ Legacy RTCM3 format support (1001-1004, 1009-1012)
- ✨ MSM format support (1074-1127)
- 🐛 Fixed buffer parsing issues
- 🐛 Fixed GLONASS satellite count parsing (27-bit epoch vs 30-bit)
- 🔧 Better error handling and logging
- 🔧 Automatic reconnection with error tracking
- 🔧 Push-based updates (no polling)
- 🔧 Memory-efficient design

### 1.1.0
- Initial public release
- Basic RTCM stream monitoring
- YAML configuration only

## 🙏 Acknowledgments

- RTCM Standard Committee for RTCM3 protocol specification
- Home Assistant community for integration guidelines
- NTRIP protocol implementers and documentation

---

**Made with ❤️ for the GNSS/RTK community**

