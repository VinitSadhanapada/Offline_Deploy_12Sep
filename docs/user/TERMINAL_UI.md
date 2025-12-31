# Terminal UI Guide

Complete guide for the SSH/Terminal interface for meter monitoring.

---

## Table of Contents
- [Overview](#overview)
- [Launching Terminal UI](#launching-terminal-ui)
- [Main Menu](#main-menu)
- [Features](#features)
- [Keyboard Navigation](#keyboard-navigation)
- [Screenshots](#screenshots)
- [Use Cases](#use-cases)
- [Tips & Tricks](#tips--tricks)

---

## Overview

The Terminal UI provides a full-featured interface for meter monitoring over SSH connections, perfect for:
- Field technicians accessing Pi remotely
- Headless Raspberry Pi installations
- Low-bandwidth connections
- Systems without desktop environment
- Quick status checks and data exports

**Key Features:**
- Real-time meter readings display
- CSV export with auto-generated SCP commands
- System status monitoring
- WiFi AP control
- Log viewer with color coding
- No desktop environment required

---

## Launching Terminal UI

### Method 1: Via Launcher Script (Recommended)

```bash
cd ~/Desktop/offline-setup-12Sep
sudo bash terminal_ui.sh
```

### Method 2: Direct Python

```bash
cd ~/Desktop/offline-setup-12Sep
python3 terminal_meter_ui.py
```

### Method 3: Via Quick Setup Menu

```bash
./setup_launchers/quick_setup.sh
# Select option 2 (Terminal UI)
```

### Method 4: Remote SSH One-Liner

```bash
# From your laptop
ssh -t pi@192.168.137.100 "cd ~/Desktop/offline-setup-12Sep && sudo bash terminal_ui.sh"
```

---

## Main Menu

```
═══ METER MONITORING SYSTEM - Terminal UI ═══
Host: raspberrypi | 2025-12-31 14:30:25
═════════════════════════════════════════════

MAIN MENU

 ► [1] Live Meter Readings      - View real-time meter data
   [2] Export CSV Data          - Copy CSV files for download
   [3] View Latest Readings     - Show last readings from CSV
   [4] System Status            - Check disk, services, and logs
   [5] View Configuration       - Display current config files
   [6] Start Manual Reading     - Run one-time meter reading
   [7] View Logs                - Display recent log entries
   [8] Help & Info              - SSH download instructions
   [9] WiFi AP Control          - Enable/disable WiFi Access Point
   [Q] Quit                     - Exit application

↑/↓: Navigate | ENTER: Select | Q: Quit
```

---

## Features

### 1. Live Meter Readings

Displays real-time data from all configured meters in a table format.

**What you see:**
```
LIVE METER READINGS

Device: Main Meter (LG6400)
Last Updated: 2025-12-31 14:30:45

Parameter              Value        Unit
─────────────────────────────────────────
Timestamp              14:30:45
Voltage_R              230.5        V
Current_R              5.2          A
Power_Total            1.18         kW
Frequency              50.0         Hz
Energy_Total           1234.5       kWh

Device: Sub Meter (LG5310)
Last Updated: 2025-12-31 14:30:45
...

R: Refresh | B: Back | Q: Quit
```

**Features:**
- Auto-refreshes every few seconds
- Shows all configured meters
- Color-coded values (green = normal, red = error)
- Timestamp for each reading

### 2. Export CSV Data

Prepares CSV files and shows exact download commands.

**What you see:**
```
EXPORT CSV DATA

✓ CSV files exported to: exports/
✓ Ready for download

Files exported:
  readings_all.csv (125.3 KB)
  MainMeter_2025-12-31.csv (45.2 KB)
  SubMeter_2025-12-31.csv (38.1 KB)

To download from your laptop, run:

  scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/exports/*.csv ./

Or download specific file:

  scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/exports/readings_all.csv ./

Press any key to continue...
```

### 3. View Latest Readings

Quick snapshot of last readings from CSV file.

**What you see:**
```
LATEST METER READINGS

File: readings_all.csv
Last 5 readings:

2025-12-31 14:30:45, Main Meter, 230.5, 5.2, 1.18, 50.0
2025-12-31 14:30:40, Main Meter, 230.3, 5.1, 1.17, 50.0
2025-12-31 14:30:35, Main Meter, 230.6, 5.3, 1.19, 50.0
...
```

### 4. System Status

Comprehensive system health check.

**What you see:**
```
SYSTEM STATUS

Disk Space:
Filesystem      Size  Used  Avail Use%
/dev/mmcblk0p2  29G   8.2G   19G  31%

Dashboard Service:
  ✓ Running
  Uptime: 2 days 14:32:15
  Readings: 12,456

USB Download Service:
  ✓ Running

WiFi AP:
  ✗ Stopped

Recent Log Files:
  meter_dashboard.log          45.2KB  2025-12-31 14:30
  usb_download.log              2.1KB  2025-12-31 10:15
  enable_auto_start.log         5.3KB  2025-12-29 08:00
```

### 5. View Configuration

Displays current system and device configuration.

**What you see:**
```
CONFIGURATION

System Config (config.json):
{
  "log_level": "INFO",
  "csv_dir": "data/csv",
  "reading_interval": 30,
  "mqtt_enabled": false
}

Device Config (device_config.json):
{
  "devices": [
    {
      "name": "Main Meter",
      "model": "LG6400",
      "address": 1,
      "parameters": ["Voltage_R", "Current_R", ...]
    }
  ]
}

USB Devices:
  /dev/ttyUSB0 - USB-RS485 Converter
```

### 6. Start Manual Reading

Triggers a one-time meter reading cycle.

**What you see:**
```
MANUAL METER READING

Starting reading cycle...

Reading Main Meter (LG6400)...
  ✓ Voltage_R: 230.5 V
  ✓ Current_R: 5.2 A
  ✓ Power_Total: 1.18 kW
  ✓ Frequency: 50.0 Hz

Reading Sub Meter (LG5310)...
  ✓ Voltage_R: 230.3 V
  ✓ Current_R: 3.1 A
  ...

✓ Reading complete
✓ Data saved to CSV
```

### 7. View Logs

Shows recent log entries with color coding.

**What you see:**
```
RECENT LOGS

Showing: meter_dashboard.log

2025-12-31 14:30:45 INFO  Dashboard started successfully
2025-12-31 14:30:40 INFO  Reading cycle #12456 completed
2025-12-31 14:30:35 INFO  All meters responding normally
2025-12-31 14:25:10 WARNING Device 2 timeout, retrying...
2025-12-31 14:25:05 ERROR  Device 2 not responding
2025-12-31 14:20:00 INFO  Reading cycle #12450 completed
...

Green  = INFO / success
Yellow = WARNING
Red    = ERROR / Failed
```

### 8. Help & Info

SSH download instructions with your Pi's IP automatically filled in.

**What you see:**
```
SSH DOWNLOAD GUIDE

CONNECTING TO THIS DEVICE:
  ssh pi@192.168.137.100

DOWNLOADING CSV DATA:
  scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./

DOWNLOADING LOGS:
  scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/logs/*.log ./logs/

DOWNLOADING ENTIRE DATA FOLDER:
  scp -r pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data ./

VIEWING LIVE DATA VIA SSH:
  1. SSH into the device
  2. Run this UI: python3 terminal_meter_ui.py
  3. Or tail CSV: tail -f data/csv/readings_all.csv

TIPS:
  • Use option 2 'Export CSV' for organized downloads
  • Default SSH password is 'raspberry' (change it!)
```

### 9. WiFi AP Control

Enable/disable WiFi Access Point.

**What you see:**
```
WiFi ACCESS POINT CONTROL

Current Status:
  ✓ WiFi AP is RUNNING
  ✓ Auto-start: ENABLED

SSID: SimpleMeter-raspberrypi
IP: 192.168.4.1

Available Actions:
  [1] Start AP (one-time)
  [2] Stop AP (one-time)
  [3] Enable AP auto-start on boot
  [4] Disable AP auto-start
  [B] Back to main menu

Select action (1-4, B):
```

**After action:**
```
Stopping WiFi AP...
✓ WiFi AP stopped successfully
```

---

## Keyboard Navigation

### Main Menu
- **↑ / ↓** - Navigate up/down through menu items
- **ENTER** - Select highlighted option
- **1-9** - Quick jump to menu option
- **Q** - Quit application

### Sub-Menus
- **B** - Back to main menu
- **R** - Refresh display (in live readings)
- **Q** - Quit to terminal

### Live Readings View
- **R** - Refresh readings
- **B** - Back to main menu
- **Q** - Quit application

### Text Views (Logs, Config)
- **↑ / ↓** - Scroll through content (if scrollable)
- **B** - Back to main menu
- **Q** - Quit

---

## Screenshots

### Main Menu
```
═══ METER MONITORING SYSTEM - Terminal UI ═══
Host: raspberrypi | 2025-12-31 14:30:25
═════════════════════════════════════════════

MAIN MENU

 ► [1] Live Meter Readings      - View real-time meter data
   [2] Export CSV Data          - Copy CSV files for download
   [3] View Latest Readings     - Show last readings from CSV
   ...
```

### Live Readings
```
═══ METER MONITORING SYSTEM - Terminal UI ═══
Host: raspberrypi | 2025-12-31 14:30:45
═════════════════════════════════════════════

LIVE METER READINGS

┌────────────────────────────────────────────┐
│ Main Meter (LG6400)                        │
├────────────────────────────────────────────┤
│ Voltage_R         230.5 V                  │
│ Current_R           5.2 A                  │
│ Power_Total        1.18 kW                 │
│ Frequency          50.0 Hz                 │
└────────────────────────────────────────────┘

R: Refresh | B: Back | Q: Quit
```

---

## Use Cases

### 1. Field Technician - Quick Status Check

**Scenario:** Check if meters are reading properly

```bash
# Connect via laptop ethernet
ssh pi@192.168.137.100

# Launch UI
cd ~/Desktop/offline-setup-12Sep && sudo bash terminal_ui.sh

# Select option 1 - Live Readings
# Press R to refresh
# Verify all meters showing data
# Press Q to quit
```

### 2. Data Collection - Download CSVs

**Scenario:** Weekly data download

```bash
# Connect via SSH
ssh pi@192.168.137.100

# Launch UI and export
cd ~/Desktop/offline-setup-12Sep && python3 terminal_meter_ui.py
# Select option 2 - Export CSV
# Copy the SCP command shown
# Exit UI with Q
# Exit SSH with 'exit'

# On laptop, paste SCP command:
scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/exports/*.csv ./weekly_data/
```

### 3. Troubleshooting - Check Logs

**Scenario:** Investigate why meter stopped responding

```bash
# SSH to Pi
ssh pi@192.168.137.100

# Launch UI
python3 ~/Desktop/offline-setup-12Sep/terminal_meter_ui.py

# Select option 7 - View Logs
# Look for ERROR or WARNING entries
# Note timestamps and error messages
# Select option 4 - System Status
# Check service status
```

### 4. WiFi AP Management

**Scenario:** Enable WiFi AP for wireless access

```bash
# SSH via ethernet
ssh pi@192.168.137.100

# Launch UI
sudo bash ~/Desktop/offline-setup-12Sep/terminal_ui.sh

# Select option 9 - WiFi AP Control
# Select 1 - Start AP
# Select 3 - Enable auto-start

# Now you can connect wirelessly to SimpleMeter network
```

### 5. Remote Monitoring

**Scenario:** Monitor from office via VPN

```bash
# SSH over VPN connection
ssh -t pi@<VPN_IP> "cd ~/Desktop/offline-setup-12Sep && python3 terminal_meter_ui.py"

# UI launches automatically
# Select option 1 for live view
# Watch real-time readings
```

---

## Tips & Tricks

### 1. One-Command Launch

Add to your laptop's `.bashrc` or `.bash_aliases`:
```bash
alias pi-meter='ssh -t pi@192.168.137.100 "cd ~/Desktop/offline-setup-12Sep && sudo bash terminal_ui.sh"'
```

Now just type:
```bash
pi-meter
```

### 2. Auto-Export Script

Create a script to export and download in one command:

```bash
#!/bin/bash
# save as: download_latest.sh

PI_IP="192.168.137.100"
ssh pi@$PI_IP "cd ~/Desktop/offline-setup-12Sep && python3 -c '
from pathlib import Path
import shutil
src = Path(\"data/csv\")
dst = Path(\"exports\")
dst.mkdir(exist_ok=True)
for f in src.glob(\"*.csv\"):
    shutil.copy2(f, dst)
print(\"Exported\")
'"

scp -r pi@$PI_IP:~/Desktop/offline-setup-12Sep/exports/*.csv ./$(date +%Y%m%d)/
echo "Downloaded to ./$(date +%Y%m%d)/"
```

### 3. Background Monitoring

Keep live readings view open in background:

```bash
# In a screen/tmux session
screen -S meter-monitor
ssh pi@192.168.137.100
python3 ~/Desktop/offline-setup-12Sep/terminal_meter_ui.py
# Select option 1

# Detach: Ctrl+A, D
# Reattach later: screen -r meter-monitor
```

### 4. CSV Tail View

Quick view without full UI:

```bash
ssh pi@192.168.137.100 "tail -f ~/Desktop/offline-setup-12Sep/data/csv/readings_all.csv"
```

### 5. Color Output Over SSH

If colors aren't working:

```bash
# Force color terminal
export TERM=xterm-256color
ssh pi@192.168.137.100
```

### 6. Quick System Status

Get status without entering UI:

```bash
ssh pi@192.168.137.100 "systemctl is-active meter-dashboard && df -h / && tail -5 ~/Desktop/offline-setup-12Sep/logs/*.log"
```

### 7. Remote Reboot

If system needs restart:

```bash
# From Terminal UI option 4 (System Status)
# Or directly:
ssh pi@192.168.137.100 "sudo reboot"
```

---

## Troubleshooting

### Terminal UI Won't Start

**Check Python:**
```bash
python3 --version
# Should show 3.11 or 3.13
```

**Check file exists:**
```bash
ls -l ~/Desktop/offline-setup-12Sep/terminal_meter_ui.py
```

**Check permissions:**
```bash
chmod +x ~/Desktop/offline-setup-12Sep/terminal_ui.sh
```

### Colors Not Showing

**Set terminal type:**
```bash
export TERM=xterm-256color
```

**Or use different terminal emulator** (iTerm2, Windows Terminal, etc.)

### Cursor Visible/Navigation Broken

**Exit cleanly:**
```bash
# Press Q to quit
# If stuck, press Ctrl+C
```

**Reset terminal:**
```bash
reset
```

### Permission Denied

**Use sudo:**
```bash
sudo bash terminal_ui.sh
```

**Or fix permissions:**
```bash
sudo chown -R pi:pi ~/Desktop/offline-setup-12Sep
```

### Screen Too Small

**Resize terminal:**
```
Minimum: 80 columns × 24 rows
Recommended: 100 columns × 30 rows
```

**Check size:**
```bash
tput cols  # Should be >= 80
tput lines # Should be >= 24
```

---

## Related Documentation

- **[SSH_ACCESS.md](SSH_ACCESS.md)** - SSH connection methods
- **[QUICKSTART.md](QUICKSTART.md)** - Installation guide
- **[DATA_EXPORT.md](DATA_EXPORT.md)** - Data download methods
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues

---

**Last Updated:** 31 December 2025  
**Terminal UI Version:** 2.0 (Reorganization Branch)
