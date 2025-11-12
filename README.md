# RTCM Stream Monitor for Home Assistant

Monitor NTRIP RTCM3 streams in Home Assistant. This custom component connects to NTRIP casters and monitors the stream status and RTCM message types.

## Features

- ✅ **UI Configuration** - Add/configure streams through the web interface
- ✅ **Connection Validation** - Tests connection before saving
- ✅ Monitors NTRIP RTCM3 streams
- ✅ Connection status tracking
- ✅ RTCM message type detection
- ✅ Message counter
- ✅ Automatic reconnection
- ✅ Each stream appears as a device with multiple entities
- ✅ Rich state attributes for detailed monitoring
- ✅ Live updates without polling

## Installation

1. Copy this folder to `<config_dir>/custom_components/rtcm_monitor/`
2. Restart Home Assistant
3. **Configure via UI** (recommended) or YAML

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

📖 **[Full UI Configuration Guide](UI_CONFIGURATION_GUIDE.md)**

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

## Entities Created

For each configured stream, the following entities are created under a single device:

### Binary Sensor
- **[Name] Connected** - Shows if the stream is currently connected
  - Attributes: host, port, mountpoint, connected_since, last_error

### Sensors
- **[Name] Message Types** - Comma-separated list of received RTCM message types
  - Attributes: message_types_list, unique_count
  
- **[Name] Last Message** - The last RTCM message received
  - Attributes: message_type, last_update
  
- **[Name] Message Count** - Total number of messages received

## Example Usage

### Automation to Alert on Connection Loss

```yaml
automation:
  - alias: "RTCM Stream Disconnected"
    trigger:
      - platform: state
        entity_id: binary_sensor.base_station_1_connected
        to: "off"
        for: "00:01:00"
    action:
      - service: notify.mobile_app
        data:
          message: "RTCM stream Base Station 1 has disconnected"
```

### Template to Check Message Rate

```yaml
sensor:
  - platform: template
    sensors:
      rtcm_message_rate:
        friendly_name: "RTCM Message Rate"
        unit_of_measurement: "msg/s"
        value_template: >
          {{ (states('sensor.base_station_1_message_count') | float / 
              (as_timestamp(now()) - as_timestamp(state_attr('binary_sensor.base_station_1_connected', 'connected_since')) | default(1))) | round(2) }}
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

1. **Connection Refused**: Check that the host, port, and mountpoint are correct
2. **Authentication Failed**: Verify username and password
3. **No Message Types Showing**: Stream may not be sending RTCM3 data, or the data format is not recognized
4. **Entities Not Showing**: Restart Home Assistant after adding the integration

## How It Works

The component:
1. Connects to the NTRIP caster using HTTP/1.0 protocol
2. Parses the binary RTCM3 stream (0xD3 frame sync)
3. Extracts message type IDs from each RTCM3 message
4. Updates Home Assistant entities periodically
5. Automatically reconnects if the connection is lost

## License

This project is provided as-is for use with Home Assistant.

## Version History

- **2.0.0** - Complete rewrite with proper device support, better error handling, and modern HA patterns
- **1.1.0** - Initial version

