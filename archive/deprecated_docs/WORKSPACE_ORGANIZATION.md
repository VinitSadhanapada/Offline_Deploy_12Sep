# Workspace Organization Guide

This document explains the clean, organized structure of this workspace.

## 📁 Directory Structure

### Root Directory
**Core application files** - main Python scripts and user-facing launchers
- `simple_rpi_dashboard.py` - Main dashboard application (auto-starts on boot)
- `simple_meter_ui.py` - GUI meter interface  
- `terminal_meter_ui.py` - **SSH terminal UI** for field access without desktop
- `meter_manager.py`, `meter_device.py` - Meter communication core
- `mqtt_client.py`, `cloud_sync.py` - MQTT/cloud functionality
- `elmeasure_*.py` - Device-specific meter drivers
- `terminal_ui.sh` - Quick launcher for terminal UI
- `one_click_system_py313.sh` - Python venv setup (used by master_setup and standalone)
- `download_meter_data.sh` - Laptop-side download helper
- `update_pull.sh` - Git update helper

### Convenience Symlinks (in root)
- `quick_start` → `setup_launchers/quick_setup.sh`
- `complete_setup` → `setup_launchers/master_setup.sh`
- `QUICKSTART.md` → `docs/SETUP_GUIDE.md`

### `setup_launchers/` - Setup & Desktop Launchers
**All setup scripts and desktop shortcuts consolidated here**
- `master_setup.sh` - **MAIN SETUP** - Runs all 8 setup steps automatically
- `quick_setup.sh` - Interactive menu for common tasks
- `enable_auto_start.sh` - Enable/disable systemd auto-start service
- `setup_static_ethernet.sh` - Configure static Ethernet IP for SSH access
- `MasterSetup_Admin.desktop` - Desktop shortcut for complete setup
- `SimpleMeterUI_Admin.desktop` - Desktop shortcut for GUI dashboard

### `docs/` - All Documentation
**Centralized documentation and guides**
- `SETUP_GUIDE.md` - **START HERE** - Complete setup walkthrough
- `QUICKSTART_SSH_UI.md` - Quick guide for SSH terminal UI access
- `README_SSH_TERMINAL_UI.md` - Detailed SSH setup and usage
- `TERMINAL_UI_SUMMARY.md` - Terminal UI feature summary
- `README_QUICKSTART.md` - Original quickstart (superseded by SETUP_GUIDE.md)
- `README_RUNTIME_FALLBACK.md` - Runtime fallback mechanisms
- `PRODUCTION_README.md` - Production deployment notes
- `FAST_DEPLOY_PI.md`, `UPGRADE_PYTHON_3.13.md` - Deployment guides
- `LEGACY_README_ENABLE_PERMISSION.txt` - Old permission setup (replaced by master_setup.sh)

### `data/csv/` - Meter Readings
- `readings_all.csv` - Combined readings from all meters
- Site-specific CSV files (e.g., `Mahamudra_2025-12-01.csv`)

### `logs/` - System Logs
- Setup logs, service logs, USB download logs

### `packages_folder/` - Offline Python Dependencies
- Wheel files for offline installation (pymodbus, paho-mqtt, pandas, etc.)

### `usb_download_mvp/` - USB Download Server
- Standalone Flask server for downloading data via USB Wi-Fi connection
- Complete with systemd services, dnsmasq config, and network scripts

### `compat/` - Compatibility Shims
- `pymodbus_compat.py` - Version compatibility layer

### `examples/` - Example Configuration Files
- `config1.jsonc`, `device_config1.jsonc` - Sample configs with comments

---

## 🚀 Quick Start Paths

### For Initial Setup
```bash
# Interactive menu (recommended for beginners)
./quick_start

# Or run complete automated setup
sudo ./complete_setup
```

### For SSH Terminal Access (Field Deployment)
```bash
# On the Raspberry Pi
./terminal_ui.sh

# Or directly
python3 terminal_meter_ui.py
```

### For Desktop GUI Access
Double-click desktop shortcuts:
- **MasterSetup_Admin.desktop** - Run complete setup
- **SimpleMeterUI_Admin.desktop** - Launch GUI dashboard

---

## 🔧 What Each Setup Script Does

### `master_setup.sh` (Complete Automated Setup)
Runs **8 steps** in order:
1. Makes all scripts executable
2. Creates required directories
3. Sets up Python venv with offline packages
4. Configures static Ethernet IP (192.168.137.2)
5. Enables systemd auto-start service
6. Sets up USB download server
7. Creates default config files
8. Adds user to dialout/gpio groups

**When to use**: First-time setup or complete reconfiguration

### `quick_setup.sh` (Interactive Menu)
Menu-driven interface with options:
1. Run complete setup (calls master_setup.sh)
2. Start terminal UI only
3. Start desktop UI only
4. Check system status
5. Exit

**When to use**: Quick access to specific tasks

### `enable_auto_start.sh`
Enables/disables systemd service for auto-starting dashboard on boot

**When to use**: Toggle auto-start behavior

### `setup_static_ethernet.sh`
Configures static Ethernet IP for laptop SSH access

**When to use**: Setting up field deployment with Ethernet cable

---

## 📊 Data Flow

```
Meters (Modbus RTU)
    ↓ RS485
Raspberry Pi
    ├→ CSV files (data/csv/)
    ├→ MQTT broker (mosquitto)
    └→ Dashboard UI (simple_rpi_dashboard.py)

SSH Access:
Laptop ←→ Ethernet ←→ Pi (192.168.137.2) → terminal_meter_ui.py

USB Download:
Laptop ←→ USB Wi-Fi ←→ Pi (AP mode 192.168.4.1) → USB Download Server
```

---

## 🗑️ Files Removed / Consolidated

The following legacy files have been **removed or superseded**:
- `README_ENABLE_PERMISSION` → Now automated by `master_setup.sh`
- Duplicate setup scripts → Consolidated into `setup_launchers/`

---

## 💡 Tips

1. **First time?** Run `./quick_start` for guided setup
2. **SSH access?** Read `docs/QUICKSTART_SSH_UI.md` first
3. **Field deployment?** Use `terminal_meter_ui.py` via SSH
4. **Desktop access?** Use desktop shortcuts or `simple_meter_ui.py`

---

## 🔗 Important Paths

| What | Where |
|------|-------|
| Main README | `README.md` |
| Complete setup | `setup_launchers/master_setup.sh` or `./complete_setup` |
| Quick setup menu | `setup_launchers/quick_setup.sh` or `./quick_start` |
| Setup guide | `docs/SETUP_GUIDE.md` or `./QUICKSTART.md` |
| SSH terminal UI | `terminal_meter_ui.py` |
| Desktop GUI | `simple_meter_ui.py` |
| Config files | `config.json`, `device_config.json` |
| CSV data | `data/csv/` |
| Logs | `logs/` |

