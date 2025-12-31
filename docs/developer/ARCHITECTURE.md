# System Architecture

Quick reference for developers maintaining this system.

---

## System Overview

```
Raspberry Pi Meter Monitoring System
├── Hardware Layer: RS485 → USB → Raspberry Pi
├── Driver Layer: Elmeasure device-specific drivers
├── Business Layer: MeterDevice, MeterManager
├── UI Layer: Desktop GUI, Terminal UI
└── Service Layer: systemd auto-start, WiFi AP
```

---

## Component Architecture

### 1. Core Components

**Dashboard Engine** (`simple_rpi_dashboard.py`)
- Main orchestrator for meter reading cycles
- Manages CSV logging and data persistence
- Runs as systemd service (`meter-dashboard.service`)
- Handles meter communication scheduling

**MeterDevice** (`src/devices/meter_device.py`)
- Abstraction for individual meters
- Supports simulation mode for testing
- Handles Modbus communication via device-specific drivers
- Returns standardized reading arrays

**MeterManager** (`src/devices/meter_manager.py`)
- CSV file management and formatting
- Date-based file organization
- Data validation and sanitization

### 2. Device Drivers

Located in `src/devices/elmeasure_*.py`:
- **LG6400**: High-precision multifunction meter
- **LG5310/LG5220**: Standard multifunction meters
- **EN8410**: Energy meter variant
- **iELR300**: Compact relay meter

Each driver implements:
- `ReadMeterData(client, deviceID, Parameters, errorFile)` - Main data reading
- Register mapping for Modbus addresses
- Data unpacking and conversion

### 3. User Interfaces

**Desktop GUI** (`simple_meter_ui.py`)
- Tkinter-based configuration interface
- Meter setup and parameter selection
- Real-time monitoring dashboard
- Service control (start/stop dashboard)

**Terminal UI** (`terminal_meter_ui.py`)
- Curses-based SSH interface
- Live readings viewer
- CSV export with SCP commands
- WiFi AP control
- System status monitoring

### 4. Network Components

**WiFi Access Point** (`usb_download_mvp/`)
- Creates SimpleMeter-<hostname> network
- Provides 192.168.4.1 access point
- Controlled via `usb_ap.service`
- Uses hostapd + dnsmasq

**Static Ethernet** (192.168.137.100)
- NetworkManager or dhcpcd configuration
- Laptop connectivity for field access
- Dual-interface with WiFi AP

**Cloud Sync** (`cloud_sync.py`, `mqtt_client.py`)
- Optional MQTT publishing
- Network monitoring with fallback
- Configurable endpoints

---

## Data Flow

```
┌─────────────────┐
│  Elmeasure      │
│  Meters         │
│  (Modbus RTU)   │
└────────┬────────┘
         │ RS485
         ↓
┌─────────────────┐
│  USB-RS485      │
│  Converter      │
│  /dev/ttyUSB0   │
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────┐
│  Device Driver                  │
│  (elmeasure_LG6400.py, etc.)    │
│  - Reads Modbus registers       │
│  - Unpacks binary data          │
│  - Returns parameter arrays     │
└────────┬────────────────────────┘
         │
         ↓
┌─────────────────────────────────┐
│  MeterDevice                    │
│  - Abstraction layer            │
│  - Simulation mode support      │
│  - Error handling               │
└────────┬────────────────────────┘
         │
         ↓
┌─────────────────────────────────┐
│  Dashboard Engine               │
│  (simple_rpi_dashboard.py)      │
│  - Reading cycle scheduler      │
│  - Multi-meter orchestration    │
└────────┬────────────────────────┘
         │
         ↓
┌─────────────────────────────────┐
│  MeterManager                   │
│  - CSV formatting               │
│  - File organization            │
│  - Data validation              │
└────────┬────────────────────────┘
         │
         ↓
┌─────────────────────────────────┐
│  Data Storage                   │
│  data/csv/readings_all.csv      │
│  data/csv/<MeterName>_<Date>.csv│
└─────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────┐
│  Access Methods                 │
│  - Desktop UI (monitor)         │
│  - Terminal UI (SSH)            │
│  - SCP/RSYNC download           │
│  - USB auto-copy                │
└─────────────────────────────────┘
```

---

## Service Architecture

### systemd Services

**meter-dashboard.service**
- Runs: `simple_rpi_dashboard.py --run`
- User: pi
- Auto-restart on failure
- Logs to journalctl

**usb_ap.service** (optional)
- Enables WiFi Access Point
- Runs: `enforce_ap_mode.sh`
- Dependencies: hostapd, dnsmasq

**usb-download-server** (optional)
- Web interface on port 8000
- USB auto-mount and file copy
- Flask-based server

---

## Configuration System

**config.json** - System settings
```json
{
  "log_level": "INFO",
  "csv_dir": "data/csv",
  "reading_interval": 30,
  "mqtt_enabled": false
}
```

**device_config.json** - Meter definitions
```json
{
  "devices": [
    {
      "name": "Main Meter",
      "model": "LG6400",
      "address": 1,
      "parameters": ["Voltage_R", "Current_R", "Power_Total"]
    }
  ]
}
```

**Modbus Configuration**
- Port: `/dev/ttyUSB0` (auto-detected)
- Baudrate: 9600
- Parity: Even
- Protocol: Modbus RTU

---

## Key Design Patterns

### 1. Simulation Mode
- All components support running without hardware
- Generates realistic dummy data for testing
- Controlled via `simulation_mode` flag

### 2. Backward Compatibility
- Symlinks in root for common scripts
- Dual config path support (root and config/)
- Original files preserved during reorganization

### 3. Error Handling
- Graceful degradation on meter timeout
- Retry logic with exponential backoff
- Error logging to files and journalctl

### 4. Modular Architecture
- Device drivers are independent modules
- Easy to add new meter models
- UI components separate from business logic

---

## Adding New Meter Models

1. **Create driver file**: `src/devices/elmeasure_NEWMODEL.py`
2. **Implement functions**:
   - `ReadMeterData(client, deviceID, Parameters, errorFile)`
   - Register address mapping
   - Data unpacking logic
3. **Update macros**: Add model constant to `src/utils/macros.py`
4. **Update MeterDevice**: Add model to dispatch logic in `meter_device.py`
5. **Test**: Use simulation mode first, then hardware

---

## Debugging

**Check service status:**
```bash
systemctl status meter-dashboard
journalctl -u meter-dashboard -n 50
```

**Check USB device:**
```bash
ls -l /dev/ttyUSB*
dmesg | grep ttyUSB
```

**Test meter communication:**
```bash
python3 -c "
from meter_device import MeterDevice
import macros
device = MeterDevice('Test', 'LG6400', macros.PARAMETERS, simulation_mode=False)
print(device.read_data())
"
```

**Check CSV output:**
```bash
tail -f data/csv/readings_all.csv
```

---

## Critical Files

| File | Purpose | Notes |
|------|---------|-------|
| `simple_rpi_dashboard.py` | Main dashboard engine | Runs as service |
| `meter_device.py` | Meter abstraction | Core business logic |
| `device_config.json` | Meter configuration | User-editable |
| `terminal_meter_ui.py` | SSH interface | Field access |
| `/etc/systemd/system/meter-dashboard.service` | Service definition | System-level |

---

## Performance Notes

- **Reading Interval**: Default 30s, configurable
- **CSV File Size**: ~1MB per meter per month
- **Memory Usage**: ~50MB for dashboard service
- **CPU Usage**: <5% on RPi 4
- **Network**: WiFi AP + Ethernet simultaneous operation supported

---

**Last Updated:** 31 December 2025  
**For detailed code reference:** See [CODE_STRUCTURE.md](CODE_STRUCTURE.md)
