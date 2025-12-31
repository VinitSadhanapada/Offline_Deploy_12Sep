# Code Structure & Organization

Quick reference for navigating the codebase.

---

## Directory Layout

```
offline-setup-12Sep/
├── src/                    ← All Python source code
│   ├── dashboard/          ← UI components
│   ├── devices/            ← Meter drivers & device logic
│   ├── network/            ← Cloud sync, MQTT, network monitoring
│   ├── utils/              ← Utilities & helpers
│   └── compat/             ← Compatibility layers
│
├── scripts/                ← Executable scripts
│   ├── setup/              ← Installation & configuration
│   ├── launchers/          ← UI launchers & desktop shortcuts
│   └── system/             ← Maintenance & system tools
│
├── tests/                  ← Testing framework
├── config/                 ← Configuration files
├── data/                   ← Runtime data (CSV files)
├── logs/                   ← Log files
├── docs/                   ← Documentation
└── usb_download_mvp/       ← USB download server subsystem
```

---

## Source Code (src/)

### dashboard/ - User Interfaces

| File | Purpose | Entry Point |
|------|---------|-------------|
| `simple_rpi_dashboard.py` | Main dashboard engine, runs reading cycles | Yes - systemd service |
| `simple_meter_ui.py` | Desktop GUI (Tkinter), meter configuration | Yes - double-click .desktop |
| `terminal_meter_ui.py` | Terminal/SSH UI (curses), remote access | Yes - via terminal_ui.sh |

**Key Classes:**
- `Dashboard` - Main orchestrator
- `TerminalMeterUI` - Curses interface manager

### devices/ - Meter Drivers & Logic

| File | Purpose | Called By |
|------|---------|-----------|
| `meter_device.py` | MeterDevice class - abstraction for individual meters | Dashboard |
| `meter_manager.py` | CSV management, file organization | Dashboard, MeterDevice |
| `elmeasure_LG6400.py` | Driver for LG6400 meter model | MeterDevice |
| `elmeasure_LG5310.py` | Driver for LG5310 meter model | MeterDevice |
| `elmeasure_LG5220.py` | Driver for LG5220 meter model | MeterDevice |
| `elmeasure_EN8410.py` | Driver for EN8410 meter model | MeterDevice |
| `elmeasure_iELR300.py` | Driver for iELR300 meter model | MeterDevice |

**Key Classes:**
- `MeterDevice` - Single meter abstraction with simulation support

**Driver Interface:**
```python
def ReadMeterData(client, deviceID, Parameters, errorFile):
    """Read data from specific meter model via Modbus"""
    # Returns: List of parameter values
```

### network/ - Network Components

| File | Purpose | Used When |
|------|---------|-----------|
| `cloud_sync.py` | Cloud synchronization logic | Optional - if MQTT enabled |
| `mqtt_client.py` | MQTT publishing client | Optional - cloud sync |
| `netwatch_trigger.py` | Network monitoring & triggers | Background monitoring |

### utils/ - Utilities

| File | Purpose | Used By |
|------|---------|---------|
| `macros.py` | Constants, device types, parameter lists | All modules |
| `paths.py` | Path management utilities | All modules |
| `venv_utils.py` | Virtual environment setup | Setup scripts |
| `rpi_status_led.py` | Raspberry Pi status LED control | Dashboard |
| `configure_device.py` | Device configuration CLI tool | Setup |
| `sitecustomize.py` | Python environment customization | Python runtime |
| `set_rtc_from_system.py` | RTC synchronization | System maintenance |

**Important Constants (macros.py):**
```python
DEV_ELM_LG6400 = "LG6400"
DEV_ELM_LG5310 = "LG+5310"
# ... other device types

PARAMETERS = [
    "Timestamp", "Voltage_R", "Current_R", "Power_Total",
    "Frequency", "Energy_Total", ...
]
```

### compat/ - Compatibility

| File | Purpose |
|------|---------|
| `pymodbus_compat.py` | Handles pymodbus 2.x vs 3.x differences |

---

## Scripts (scripts/)

### setup/ - Installation Scripts

| Script | Purpose | Requires Sudo |
|--------|---------|---------------|
| `master_setup.sh` | Complete automated setup | Yes |
| `quick_setup.sh` | Interactive setup menu | No (launches with sudo) |
| `enable_auto_start.sh` | Install systemd services | Yes |
| `setup_static_ethernet.sh` | Configure static IP | Yes |
| `one_click_system_py313.sh` | Python 3.13 venv setup | No |

### launchers/ - UI Launchers

| File | Purpose |
|------|---------|
| `terminal_ui.sh` | Launch Terminal UI with proper environment |
| `MasterSetup_Admin.desktop` | Desktop shortcut for complete setup |
| `SimpleMeterUI_Admin.desktop` | Desktop shortcut for GUI |

### system/ - Maintenance

| Script | Purpose |
|--------|---------|
| `update_pull.sh` | Git pull updates |
| `download_meter_data.sh` | Helper for SCP downloads |
| `usb_csv_auto_copy.py` | USB auto-copy daemon |

---

## Configuration Files

### Main Configuration

**config.json** - System configuration
```json
{
  "log_level": "INFO",
  "csv_dir": "data/csv",
  "reading_interval": 30,
  "mqtt_enabled": false,
  "mqtt_broker": "localhost",
  "mqtt_port": 1883
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

### Example Configurations

Located in `config/examples/`:
- `config1.jsonc` - System config with comments
- `device_config1.jsonc` - Device config with comments

---

## Data Organization

### CSV Files (data/csv/)

**File Naming:**
- `readings_all.csv` - Combined readings from all meters
- `<MeterName>_<YYYY-MM-DD>.csv` - Daily per-meter files

**CSV Format:**
```csv
Timestamp,Voltage_R,Current_R,Power_Total,Frequency,...
2025-12-31 14:30:00,230.5,5.2,1.18,50.0,...
```

### Logs (logs/)

**Log Files:**
- `meter_dashboard.log` - Main dashboard logs
- `enable_auto_start_<timestamp>.log` - Setup logs
- Service logs also in `journalctl -u meter-dashboard`

---

## Import Paths

### Current (Root-based)
```python
# Original files still in root for compatibility
from meter_device import MeterDevice
from macros import PARAMETERS
```

### Future (src/-based)
```python
# When migrating to src/ imports
import sys
sys.path.insert(0, 'src')
from devices.meter_device import MeterDevice
from utils.macros import PARAMETERS
```

**Note:** Symlinks maintain backward compatibility:
- `terminal_ui.sh` → `scripts/launchers/terminal_ui.sh`
- `test_complete_setup.sh` → `tests/test_complete_setup.sh`

---

## Dependencies

### Python Packages

**Core:**
- `pymodbus` (2.5.3 or 3.11.3) - Modbus communication
- `pyserial` - Serial port access

**UI:**
- `tkinter` - Desktop GUI (usually pre-installed)
- `curses` - Terminal UI (pre-installed)

**Optional:**
- `paho-mqtt` - MQTT client
- `pandas` - CSV processing
- `flask` - USB download server
- `smbus2` - I2C communication (RTC)

**All available offline** in `packages_folder/`

### System Packages

- `hostapd` - WiFi Access Point
- `dnsmasq` - DHCP/DNS for AP
- NetworkManager or dhcpcd - Network management

---

## Testing Structure

### Test Scripts (tests/)

| Script | Purpose | Runtime |
|--------|---------|---------|
| `test_complete_setup.sh` | Full system validation | 5-10 min |
| `quick_test.sh` | Quick sanity check | <1 min |
| `preflight_check.sh` | Pre-installation check | <1 min |

**Test Categories** (in test_complete_setup.sh):
1. Directory structure
2. Python environment
3. Core files present
4. Scripts executable
5. Config files valid
6. Network configuration
7. Service installation
8. USB device detection
9. CSV data generation
10. Log file creation
... (20 total)

---

## Common Workflows

### Add New Meter
1. Edit `config/device_config.json`
2. Add device entry with model, address, parameters
3. Restart dashboard: `sudo systemctl restart meter-dashboard`

### Debug Meter Communication
1. Check USB: `ls -l /dev/ttyUSB*`
2. Check logs: `journalctl -u meter-dashboard -f`
3. Test manually: `python3 meter_device.py` (with test code)

### Update System
1. Pull updates: `./update_pull.sh`
2. Restart services: `sudo systemctl restart meter-dashboard`
3. Verify: Check Terminal UI or logs

### Export Data
1. Terminal UI option 2 (shows SCP command)
2. Or direct: `scp pi@<IP>:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./`

---

## File Size Reference

**Source Code:**
- `simple_rpi_dashboard.py`: ~50KB (1,200 lines)
- `terminal_meter_ui.py`: ~40KB (900 lines)
- `meter_device.py`: ~8KB (150 lines)
- Device drivers: ~6-9KB each (200-250 lines)

**Total Project Size:** ~15MB (excluding venv)

---

## Coding Conventions

### Python
- PEP 8 style (mostly)
- Docstrings for classes and functions
- Type hints minimal (legacy codebase)
- Error handling with try/except and logging

### Bash
- POSIX-compatible where possible
- `set -eo pipefail` for error handling
- Functions return 0 for success
- Logging to files and stdout

### Configuration
- JSON for machine-readable configs
- JSONC (JSON with comments) for examples
- Environment variables for overrides

---

## Quick File Lookup

**Need to modify...** | **Edit this file...**
---|---
Reading interval | `config.json` → `reading_interval`
Meter list | `device_config.json` → `devices`
Dashboard logic | `simple_rpi_dashboard.py`
Terminal UI features | `terminal_meter_ui.py`
Desktop GUI | `simple_meter_ui.py`
CSV format | `meter_manager.py`
New meter driver | Create `elmeasure_NEWMODEL.py`
Service config | `/etc/systemd/system/meter-dashboard.service`
Setup process | `scripts/setup/master_setup.sh`
Network config | `scripts/setup/setup_static_ethernet.sh`

---

**Last Updated:** 31 December 2025  
**For architecture overview:** See [ARCHITECTURE.md](ARCHITECTURE.md)
