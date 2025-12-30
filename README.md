# Raspberry Pi Meter Dashboard System

> **Fresh Install?** Clone this repo and run: `sudo bash test_complete_setup.sh`  
> **Quick Start:** See [`FRESH_PI_TEST_INSTRUCTIONS.md`](FRESH_PI_TEST_INSTRUCTIONS.md) for complete testing guide

## 📥 Clone This Repository

```bash
cd ~/Desktop
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git offline-setup-12Sep
cd offline-setup-12Sep
```

## 🧪 Automated Testing (Fresh Pi)

```bash
# Run complete test suite (validates and sets up everything)
sudo bash test_complete_setup.sh

# Or run quick check first
bash quick_test.sh
```

For detailed testing instructions, see [`FRESH_PI_TEST_INSTRUCTIONS.md`](FRESH_PI_TEST_INSTRUCTIONS.md)

---

## Directory Structure

```
offline-setup-12Sep/
├── README.md                          ← You are here
├── setup_launchers/                   ← All setup scripts and desktop shortcuts
│   ├── MasterSetup_Admin.desktop      ← Double-click for complete setup (desktop)
│   ├── SimpleMeterUI_Admin.desktop    ← Double-click to launch UI (desktop)
│   ├── master_setup.sh                ← Complete automated setup (terminal/SSH)
│   ├── quick_setup.sh                 ← Interactive setup menu (terminal/SSH)
│   ├── setup_static_ethernet.sh       ← Configure Ethernet for laptop access
│   └── enable_auto_start.sh           ← Enable auto-start service
├── docs/                              ← All documentation
│   ├── SETUP_GUIDE.md                 ← **START HERE** - Complete setup guide
│   ├── QUICKSTART_SSH_UI.md           ← SSH/Terminal UI quick guide
│   ├── README_SSH_TERMINAL_UI.md      ← Detailed SSH access documentation
│   ├── README_QUICKSTART.md           ← Original quick start guide
│   └── ... (other docs)
├── simple_meter_ui.py                 ← Desktop GUI application
├── terminal_meter_ui.py               ← Terminal/SSH UI application
├── terminal_ui.sh                     ← Terminal UI launcher
├── simple_rpi_dashboard.py            ← Core dashboard engine
├── one_click_system_py313.sh          ← Python environment setup
├── data/csv/                          ← Meter reading data
├── logs/                              ← System logs
├── exports/                           ← Prepared files for download
└── usb_download_mvp/                  ← USB download server & WiFi AP
```

## Quick Access

### First-Time Setup

**With Desktop (Mouse/Keyboard):**
```bash
# Double-click this file:
setup_launchers/MasterSetup_Admin.desktop
```

**Via SSH/Terminal:**
```bash
cd ~/Desktop/offline-setup-12Sep
./setup_launchers/quick_setup.sh
# Or directly:
sudo ./setup_launchers/master_setup.sh
```

### Daily Usage

**Desktop UI:**
```bash
# Double-click:
setup_launchers/SimpleMeterUI_Admin.desktop
# Or run:
python3 simple_meter_ui.py
```

**Terminal UI (SSH):**
```bash
./terminal_ui.sh
# Or:
python3 terminal_meter_ui.py
```

## Core Components

### Setup Scripts (`setup_launchers/`)

| File | Purpose | When to Use |
|------|---------|-------------|
| `master_setup.sh` | Complete automated setup | First-time Pi setup |
| `quick_setup.sh` | Interactive menu | SSH access, quick tasks |
| `setup_static_ethernet.sh` | Static IP for eth0 | Enable laptop Ethernet access |
| `enable_auto_start.sh` | systemd service | Production deployment |

### UI Applications

| File | Purpose | Access Method |
|------|---------|---------------|
| `simple_meter_ui.py` | Graphical UI | Desktop with mouse/keyboard |
| `terminal_meter_ui.py` | Text-based UI | SSH/Terminal |
| `simple_rpi_dashboard.py` | Core engine | Backend (auto-started) |

### Utilities

| File | Purpose |
|------|---------|
| `one_click_system_py313.sh` | Python environment setup |
| `terminal_ui.sh` | Terminal UI wrapper |
| `download_meter_data.sh` | Laptop-side download helper |
| `update_pull.sh` | Git update script |

## Documentation

- **[Setup Guide](docs/SETUP_GUIDE.md)** - Complete setup for all scenarios
- **[SSH Quick Start](docs/QUICKSTART_SSH_UI.md)** - 5-minute SSH guide
- **[SSH Details](docs/README_SSH_TERMINAL_UI.md)** - Full SSH documentation
- **[MQTT Troubleshooting](README_MQTT_TROUBLESHOOT.md)** - MQTT diagnostics
- **[Production Deployment](docs/PRODUCTION_README.md)** - Field deployment guide

## Common Tasks

### Configure Meters
```bash
# Desktop:
python3 configure_device.py
# Or edit manually:
nano ~/meter_config/device_config.json
```

### View Live Data
```bash
# Terminal UI:
./terminal_ui.sh

# Desktop UI:
python3 simple_meter_ui.py

# Direct CSV:
tail -f data/csv/readings_all.csv
```

### Download Data (from laptop)
```bash
# Via SCP:
scp pi@<PI_IP>:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./

# Or use helper:
./download_meter_data.sh <PI_IP>
```

### Check Status
```bash
systemctl status meter-dashboard
tail -f logs/*.log
```

## System Services

After running `master_setup.sh`, these services may be installed:

- **meter-dashboard** - Auto-start dashboard on boot
- **usb-download-server** - USB file download service
- **ap-mode-enforcer** - WiFi AP mode watchdog

Check status: `systemctl status <service-name>`

## Configuration

Main config files (created during setup):

- `~/meter_config/config.json` - System configuration
- `~/meter_config/device_config.json` - Meter devices
- `config.json` - Legacy local config (use ~/meter_config instead)

## Network Access

### SSH via Ethernet (after setup)
```bash
ssh pi@192.168.137.2
```

### SSH via WiFi
```bash
ssh pi@<PI_WIFI_IP>
```

### SSH via Pi WiFi AP
```bash
ssh pi@192.168.50.1
```

## Troubleshooting

### Services not starting
```bash
sudo ./setup_launchers/master_setup.sh
```

### Permission errors
```bash
cd ~/Desktop/offline-setup-12Sep/setup_launchers
chmod +x *.sh *.desktop
```

### Python errors
```bash
./one_click_system_py313.sh
```

### MQTT not connecting
See [`README_MQTT_TROUBLESHOOT.md`](README_MQTT_TROUBLESHOOT.md)

## Support Files

- `packages_folder/` - Offline Python packages
- `examples/` - Example configurations
- `tools/` - Utility scripts
- `compat/` - Compatibility layers
- `venv/` - Python virtual environment (auto-created)

## Development

- **Repository:** VinitSadhanapada/Offline_Deploy_12Sep
- **Branch:** temp-usb-copy-fixes-2025-12-03
- **Update:** `./update_pull.sh`

## Version Info

- **System:** Electrical IoT UI 1.0.0
- **Python:** 3.13+ (auto-installed)
- **Supported Meters:** LG6400, LG5220, LG5310, EN8410, ELR300, EN8400, EN8100

---

**Need Help?** Start with [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) or run `./setup_launchers/quick_setup.sh`
