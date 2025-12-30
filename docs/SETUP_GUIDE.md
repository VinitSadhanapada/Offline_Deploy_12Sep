# Setup Guide - All Methods

This document explains all the ways to set up and access your Raspberry Pi Meter Dashboard system.

## Quick Overview

There are **3 main entry points** depending on how you're accessing the Pi:

1. **Desktop (with mouse/keyboard)** → Double-click `MasterSetup_Admin.desktop`
2. **SSH/Terminal** → Run `./quick_setup.sh`
3. **Manual** → Run `sudo ./master_setup.sh`

---

## Method 1: Desktop Setup (First Time)

If you have a monitor, keyboard, and mouse connected:

### Step 1: Run Complete Setup
1. Navigate to Desktop → `offline-setup-12Sep` folder
2. Double-click **`MasterSetup_Admin.desktop`**
3. Follow prompts to configure:
   - Python environment
   - Static Ethernet IP (for laptop access)
   - Dashboard auto-start
   - WiFi AP mode (optional)
   - USB download server (optional)

### Step 2: Launch Dashboard UI
After setup completes:
- Double-click **`SimpleMeterUI_Admin.desktop`**
- Configure your meters
- Start data logging

---

## Method 2: SSH/Terminal Setup (Field Access)

If connecting via SSH from laptop:

### Step 1: Connect to Pi
```bash
# Via Ethernet (if static IP configured)
ssh pi@192.168.137.2

# Or via WiFi
ssh pi@<PI_WIFI_IP>

# Or via Pi's WiFi AP
ssh pi@192.168.50.1
```

### Step 2: Run Quick Setup Menu
```bash
cd ~/Desktop/offline-setup-12Sep
./quick_setup.sh
```

Then select:
- Option 1: Complete first-time setup
- Option 2: Launch Terminal UI (for viewing data)

### Alternative: Direct Master Setup
```bash
cd ~/Desktop/offline-setup-12Sep
sudo ./master_setup.sh
```

---

## Method 3: Manual Setup (Advanced)

Run individual setup scripts as needed:

### 1. Make Scripts Executable
```bash
cd ~/Desktop/offline-setup-12Sep
chmod +x *.sh
chmod +x usb_download_mvp/scripts/*.sh
```

### 2. Python Environment
```bash
./one_click_system_py313.sh
```

### 3. Static Ethernet IP (Optional)
```bash
sudo ./setup_static_ethernet.sh
```

### 4. Dashboard Auto-Start (Optional)
```bash
sudo ./enable_auto_start.sh
```

### 5. USB Download Server (Optional)
```bash
cd usb_download_mvp
sudo ./scripts/install_service.sh
```

---

## What Each Setup Script Does

### `master_setup.sh` (Comprehensive)
- ✅ Makes all scripts executable
- ✅ Creates necessary directories (data, logs, exports)
- ✅ Sets up Python virtual environment
- ✅ Configures static Ethernet IP
- ✅ Enables dashboard auto-start service
- ✅ Installs USB download server
- ✅ Configures WiFi AP mode
- ✅ Sets user permissions (dialout, i2c groups)
- ✅ Creates default config files

**When to use:** First-time Pi setup, complete system configuration

### `quick_setup.sh` (Menu-Driven)
- Interactive menu for common tasks
- Calls master_setup.sh or terminal_ui.sh
- Great for SSH access

**When to use:** Quick access to setup or Terminal UI via SSH

### `setup_static_ethernet.sh` (Ethernet Only)
- Configures eth0 with static IP `192.168.137.2`
- Allows direct laptop connection via Ethernet
- Does NOT affect WiFi

**When to use:** Enable laptop SSH access via Ethernet cable

### `enable_auto_start.sh` (Service Only)
- Creates systemd service for dashboard
- Enables auto-start on boot
- Sets up RTC (Real-Time Clock)

**When to use:** Production deployment, automatic data logging

### `one_click_system_py313.sh` (Python Only)
- Creates Python 3.13 virtual environment
- Installs all required packages from `packages_folder/`
- Runs smoke tests

**When to use:** Python environment setup or updates

---

## Desktop Files Reference

### `MasterSetup_Admin.desktop`
**Purpose:** One-click complete system setup  
**Requires:** Desktop environment, sudo password  
**Use for:** First-time setup

### `SimpleMeterUI_Admin.desktop`
**Purpose:** Launch graphical dashboard UI  
**Requires:** Desktop environment, Python configured  
**Use for:** Daily operations, meter configuration

---

## Configuration Files

After setup, configure your system:

### Main Config: `/home/pi/meter_config/config.json`
```json
{
  "SIMULATION_MODE": false,
  "READING_INTERVAL": 10,
  "ENABLE_MQTT": false,
  "PORT": "/dev/ttyUSB0"
}
```

### Device Config: `/home/pi/meter_config/device_config.json`
```json
[
  {
    "name": "Main Meter",
    "model": "LG6400",
    "address": 1,
    "location": "Building A"
  }
]
```

---

## Access Methods Summary

| Method | Entry Point | When to Use |
|--------|-------------|-------------|
| **Desktop GUI** | `MasterSetup_Admin.desktop` | First-time setup with monitor |
| **Desktop UI** | `SimpleMeterUI_Admin.desktop` | Daily operation with desktop |
| **SSH Quick Menu** | `./quick_setup.sh` | Field access via SSH |
| **SSH Terminal UI** | `./terminal_ui.sh` | View data/download via SSH |
| **Manual Setup** | `sudo ./master_setup.sh` | Complete automated setup |

---

## Common Workflows

### First Deployment (With Desktop)
1. Connect monitor/keyboard to Pi
2. Double-click `MasterSetup_Admin.desktop`
3. Configure all options (yes to all prompts)
4. Reboot
5. Use `SimpleMeterUI_Admin.desktop` for daily use

### First Deployment (SSH Only)
```bash
ssh pi@<PI_IP>
cd ~/Desktop/offline-setup-12Sep
sudo ./master_setup.sh
# Answer prompts
sudo reboot
```

### Field Data Retrieval (Laptop via Ethernet)
```bash
# On laptop
ssh pi@192.168.137.2
cd ~/Desktop/offline-setup-12Sep
./terminal_ui.sh
# Press 2 for Export, copy the scp command
# Exit and run scp command on laptop
```

### Remote Access (WiFi)
```bash
ssh pi@<PI_WIFI_IP>
./quick_setup.sh
# Select option 2 for Terminal UI
```

---

## Troubleshooting

### "Permission denied" when running scripts
```bash
cd ~/Desktop/offline-setup-12Sep
chmod +x *.sh
chmod +x usb_download_mvp/scripts/*.sh
```

### "Python not found"
```bash
./one_click_system_py313.sh
```

### "Service not starting"
```bash
sudo systemctl status meter-dashboard
sudo journalctl -u meter-dashboard -n 50
```

### Static Ethernet not working
```bash
sudo ./setup_static_ethernet.sh
# Verify:
ip addr show eth0
```

---

## Next Steps After Setup

1. **Configure meters:** Edit device_config.json or use Desktop UI
2. **Test reading:** `python3 simple_rpi_dashboard.py --run`
3. **View data:** Check `data/csv/readings_all.csv`
4. **Enable MQTT** (optional): Edit config.json, set `ENABLE_MQTT: true`

---

## Quick Reference

```bash
# Complete setup
sudo ./master_setup.sh

# Quick menu (SSH)
./quick_setup.sh

# Terminal UI
./terminal_ui.sh

# Desktop UI
python3 simple_meter_ui.py

# Check status
systemctl status meter-dashboard

# View logs
tail -f logs/*.log

# Manual reading
python3 simple_rpi_dashboard.py --run
```

---

For detailed documentation, see:
- SSH access: `QUICKSTART_SSH_UI.md`
- MQTT troubleshooting: `README_MQTT_TROUBLESHOOT.md`
- Complete guide: `README_QUICKSTART.md`
