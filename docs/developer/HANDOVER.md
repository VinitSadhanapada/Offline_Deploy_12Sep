# Engineer Handover — SimpleMeter Pi

> **One-page rule:** Every feature, button, and behaviour maps to a file + function + line number.
> If you need to change something, Ctrl-F this doc.

---

## 1. System in 2 Minutes

```
┌──────────────┐   RS-485 / Modbus RTU   ┌─────────────────────┐
│  Elmeasure   │◄────────────────────────►│   Raspberry Pi 5    │
│  Meters ×N   │   via /dev/ttyUSB0       │                     │
└──────────────┘                          │  Python 3.13 venv   │
                                          │  systemd services   │
┌──────────────┐   I2C bus 1              │                     │
│  DS3231 RTC  │◄────────────────────────►│  Offline-first      │
└──────────────┘                          │  No internet needed  │
                                          └──┬──────┬──────┬────┘
                                             │      │      │
                              ┌──────────────┘      │      └──────────────┐
                              ▼                      ▼                    ▼
                     eth0 (static)           wlan0 (WiFi AP)       Desktop GUI
                     192.168.137.100         192.168.50.1           (Tkinter)
                     for laptop SCP          SSID: SimpleMeter-*
                                             Pass: iotlabsdev
                                             → Flask web download
                                               http://192.168.50.1:8080
```

**Data flow:** Meters → `meter_device.py` → `meter_manager.py` → `data/csv/DATA_ALL.csv` (+ MQTT if enabled)

**Three user interfaces:**
| Interface       | When to use                 | Entry point                                      |
|-----------------|-----------------------------|--------------------------------------------------|
| Desktop GUI     | Technician at Pi with HDMI  | `src/dashboard/simple_meter_ui.py`               |
| Terminal UI     | SSH session                 | `src/dashboard/terminal_meter_ui.py`             |
| Web Download    | Phone/laptop on WiFi AP     | `usb_download_mvp/server.py` → port 8080        |

---

## 2. "I Need to Change…" Lookup Table

> **This is the core of the doc.** Find what you want to change, go to the file.

### Reading / Polling

| I need to…                              | File                                          | Function / Line          |
|-----------------------------------------|-----------------------------------------------|--------------------------|
| Change reading interval (seconds)       | `config/config.json` → `READING_INTERVAL`     | Default: 10              |
| Change CSV write interval               | `config/config.json` → `CSV_LOG_INTERVAL`     | Default: 60              |
| Change inter-device delay               | `config/config.json` → `INTER_DEVICE_DELAY`   | Default: 0.1             |
| Change serial port                      | `config/config.json` → `PORT`                 | Default: /dev/ttyUSB0    |
| Add a new meter                         | `config/device_config.json`                    | Add JSON object to array |
| Change which registers are read         | `src/utils/macros.py`                          | `PARAMETERS` L86, `REG_ADDRESSES` L110 |
| Add a new meter model                   | `src/devices/elmeasure_*.py` (new file) + `src/devices/meter_device.py` L147–159 (dispatch) + `src/utils/macros.py` L44–50 (constant) |
| Change how a specific model is read     | `src/devices/elmeasure_LG6400.py` (or LG5220, LG5310, EN8410, iELR300) |
| Fix Modbus read error handling          | `src/devices/meter_device.py` → `read_data()` L101 |
| Change CSV retention (days kept)        | `src/devices/meter_manager.py` → `DEFAULT_RETENTION_DAYS` L81 (= 14) |
| Change CSV file rotation logic          | `src/devices/meter_manager.py` → `_perform_safe_rotation()` L957 |
| Fix CSV corruption repair               | `src/devices/meter_manager.py` → `_detect_and_repair_corruption()` L782 |
| Change CSV column format/rounding       | `src/devices/meter_manager.py` → `format_csv_value()` L21 |
| Change CSV header                       | `src/devices/meter_manager.py` → `create_formatted_csv_header()` L50 |
| Change slow-write (CSV interval) logic  | `src/devices/meter_manager.py` → `_write_slow_csv()` L751 |

### Time / RTC

| I need to…                              | File                                          | Function / Line          |
|-----------------------------------------|-----------------------------------------------|--------------------------|
| Enable/disable RTC                      | `config/config.json` → `ENABLE_RTC`           | true / false             |
| Fix RTC hardware communication          | `src/utils/rtc_module.py` → `DS3231` class L31 |                          |
| Change time validation / drift logic    | `src/utils/time_sanitizer.py` → `RTCTimeSanitizer` L33 |                   |
| Fix time-jump detection                 | `src/utils/time_sanitizer.py` → `check_discontinuity()` L397 |             |
| Set RTC from system clock               | `src/utils/set_rtc_from_system.py`            |                          |

### MQTT / Cloud

| I need to…                              | File                                          | Function / Line          |
|-----------------------------------------|-----------------------------------------------|--------------------------|
| Enable/disable MQTT                     | `config/config.json` → `ENABLE_MQTT`          | true / false             |
| Change MQTT broker/topic/QoS            | `src/network/mqtt_client.py` → `_load_mqtt_config()` L47 |                 |
| Change MQTT payload format              | `src/network/mqtt_client.py` → `_construct_payload()` L179 |               |
| Change cloud sync method                | `src/network/cloud_sync.py` → `do_sync()` L247 (dispatches to rclone/rsync/scp) |
| Change cloud sync schedule              | `scripts/setup/enable_auto_start.sh` → L111–137 (timer unit) |             |
| Change cloud sync config                | `config/config.json` → add `cloud_sync` section |                          |

### Network / WiFi AP

| I need to…                              | File                                          | Function / Line          |
|-----------------------------------------|-----------------------------------------------|--------------------------|
| Change static IP address                | `scripts/setup/setup_static_ethernet.sh` → L15 (`STATIC_IP`) |             |
| Change WiFi AP SSID or password         | `usb_download_mvp/network/` config files      |                          |
| Start/stop WiFi AP manually             | `usb_download_mvp/scripts/enforce_ap_mode.sh` → `start)` L29, `stop)` L93 |
| Toggle AP from Desktop GUI              | `src/dashboard/simple_meter_ui.py` → `on_toggle_ap()` L484 |               |
| Toggle AP from Terminal UI              | `src/dashboard/terminal_meter_ui.py` → `toggle_wifi_ap()` L1008 |          |

### Systemd Services

| I need to…                              | File                                          | Function / Line          |
|-----------------------------------------|-----------------------------------------------|--------------------------|
| Change which services get installed     | `scripts/setup/enable_auto_start.sh`           | Full file (~210 lines)   |
| Change the dashboard service definition | `src/dashboard/simple_rpi_dashboard.py` → `create_systemd_service()` L606 |
| Change the web download service         | `usb_download_mvp/systemd/` service unit files |                          |
| Change cloud sync timer                 | `scripts/setup/enable_auto_start.sh` → L111–137 |                          |

### Setup / Installation

| I need to…                              | File                                          | Function / Line          |
|-----------------------------------------|-----------------------------------------------|--------------------------|
| Change the full master setup            | `scripts/setup/master_setup.sh`                | 8 steps, starts L109     |
| Change Python/venv setup                | `scripts/setup/one_click_system_py313.sh`      | `prepare_venv()` L162    |
| Change offline package install          | `scripts/setup/one_click_system_py313.sh`      | `offline_install()` L179 |
| Change the SSH quick-setup menu         | `scripts/setup/quick_setup.sh`                 |                          |
| Add/remove offline wheel packages       | `packages_folder/`                             | Drop .whl files in       |

---

## 3. Terminal UI — Menu → Code Map

File: `src/dashboard/terminal_meter_ui.py` — class `TerminalMeterUI` (L34)

| Key | Menu Label           | Method                  | Line  | What it does                         |
|-----|----------------------|-------------------------|-------|--------------------------------------|
| 1   | Live Meter Readings  | `show_live_readings()`  | L151  | Real-time polling display            |
| 2   | Export CSV Data       | `export_csv_data()`     | L238  | Copy CSVs to ~/exports for SCP      |
| 3   | View Latest Readings | (part of live readings) |       | Shows last-read values               |
| 4   | System Status        | `show_system_status()`  | L558  | Disk, services, logs overview        |
| 5   | Configure Devices    | `configure_devices()`   | L1168 | Add/edit/delete meters interactively |
| 6   | View Configuration   | `show_configuration()`  | L637  | Display current config files         |
| 7   | Service Control      | (sub-menu)              |       | Start/stop/restart systemd           |
| 8   | View Logs            | `view_logs()`           | L949  | Recent journal log entries           |
| 9   | Help & Info          | `show_help()`           | L723  | SSH download instructions            |
| 0   | WiFi AP Control      | `toggle_wifi_ap()`      | L1008 | Enable/disable WiFi hotspot          |
| Q   | Quit                 | exits `run()` loop      | L1414 |                                      |

---

## 4. Desktop GUI — Button → Code Map

File: `src/dashboard/simple_meter_ui.py` — class `SimpleMeterUI` (L75)

All buttons are created in `create_widgets()` starting at L518:

| Button Label          | Handler method            | Line  | What it does                          |
|-----------------------|---------------------------|-------|---------------------------------------|
| Setup Environment     | `setup_env()`             | L816  | Run venv + package setup script       |
| Configure Devices     | `configure_devices()`     | L99   | Opens `DeviceConfigUI` popup          |
| View/Edit Config      | `edit_config()`           | L79   | Opens config.json in text editor      |
| Enable Auto-Start     | `auto_start()`            | L112  | Install systemd services              |
| Apply (CSV interval)  | `_on_csv_interval_change()` | L337 | Save new CSV write interval           |
| Enable (AP checkbox)  | `on_toggle_ap()`          | L484  | Toggle WiFi AP on/off                 |
| Refresh (AP status)   | `_update_ap_service_status()` | L469 | Check current AP state              |
| Manual Run            | `manual_run()`            | L821  | One-shot meter reading                |
| Live Readings         | `live_readings()`         | L833  | Opens `LiveReadingsWindow` popup      |
| Force Stop Logging    | `force_stop_logging()`    | L635  | Kill running logging subprocess       |
| Reboot System         | `reboot_system()`         | L76   | `sudo reboot`                         |
| Exit                  | `destroy()`               | (Tk)  | Close application                     |

**Device config popup:** `src/utils/configure_device.py` → `DeviceConfigUI` (L101)
**Live readings popup:** `src/dashboard/simple_meter_ui.py` → `LiveReadingsWindow` (L838)

---

## 5. Web Download UI — Route → Code Map

File: `usb_download_mvp/server.py`

| Route / Element          | Function            | Line  | What it does                          |
|--------------------------|---------------------|-------|---------------------------------------|
| `GET /`                  | `index()`           | L191  | Render main download page             |
| `GET /available_dates`   | `available_dates()` | L197  | Return date range of available data   |
| `POST /download_data`    | `download_data()`   | L223  | Download filtered CSV as ZIP          |

Template: `usb_download_mvp/templates/index.html`

| UI Element                   | Line  | JS Function / Action                     |
|------------------------------|-------|------------------------------------------|
| "Download ALL Data" button   | L40   | `downloadAllData()` → fetch all CSV      |
| Date range form              | L53   | Start/end date inputs                    |
| "Download Selected" button   | L78   | `form.onsubmit` → POST `/download_data`  |

**WiFi AP config:** `usb_download_mvp/network/` — hostapd + dnsmasq config
**AP service control:** `usb_download_mvp/scripts/enforce_ap_mode.sh`

---

## 6. Configuration Reference

### config/config.json

| Key                   | Type    | Default        | Purpose                                   |
|-----------------------|---------|----------------|-------------------------------------------|
| `SIMULATION_MODE`     | bool    | `false`        | Use fake data (no hardware needed)        |
| `READING_INTERVAL`    | int     | `10`           | Seconds between meter polls               |
| `CSV_LOG_INTERVAL`    | int     | `60`           | Seconds between CSV row writes            |
| `INTER_DEVICE_DELAY`  | float   | `0.1`          | Delay between polling each meter (sec)    |
| `PORT`                | string  | `/dev/ttyUSB0` | RS-485 serial port path                   |
| `ENABLE_MQTT`         | bool    | `false`        | Publish readings to MQTT broker           |
| `ENABLE_RTC`          | bool    | `true`         | Use DS3231 RTC for time validation        |
| `LOG_LEVEL`           | string  | `INFO`         | Python logging level                      |

> Config supports `//` comments (JSONC). Parser: `src/utils/config_loader.py`

### config/device_config.json

Array of meter devices. Each entry:

```json
{
  "name":     "BikeParking",     // Human label (appears in CSV header)
  "address":  1,                 // Modbus slave address (1–247)
  "model":    "LG6400",          // Must match a DEV_ELM_* constant
  "location": "Mahamudra"        // Optional site label
}
```

**Supported models:** `LG6400`, `LG+5220`, `LG+5310`, `EN8400`, `EN8100`, `EN8410`, `ELR300`
(Models defined in `src/utils/macros.py` L44–50)

---

## 7. Systemd Services

| Service                    | What it does                            | Installed by                      |
|----------------------------|-----------------------------------------|-----------------------------------|
| `meter-dashboard.service`  | Main polling loop (reads meters → CSV)  | `enable_auto_start.sh` L68       |
| `download-server.service`  | Flask web server on port 8080           | `usb_download_mvp/systemd/`      |
| `usb_ap.service`           | WiFi AP (hostapd + dnsmasq)             | `usb_download_mvp/systemd/`      |
| `cloud_sync.timer`         | Periodic cloud sync trigger             | `enable_auto_start.sh` L111      |
| `cloud_sync.service`       | Cloud sync one-shot (called by timer)   | `enable_auto_start.sh` L111      |
| `netwatch-trigger.service` | Network-change watcher for cloud sync   | `enable_auto_start.sh` L167      |

**Common commands:**
```bash
sudo systemctl status meter-dashboard
sudo systemctl restart meter-dashboard
sudo journalctl -u meter-dashboard -n 50 --no-pager
```

---

## 8. Data Files

### CSV Files

| File                       | Location              | Written by               | Format                           |
|----------------------------|-----------------------|--------------------------|----------------------------------|
| `DATA_ALL.csv`             | `data/csv/`           | `meter_manager.py` L361  | timestamp + per-meter parameters |
| `EVENTS.csv`               | `data/csv/`           | `meter_manager.py` L584  | timestamp, type, message         |
| `readings_all.csv`         | `data/csv/`           | (legacy alias)           |                                  |
| Archived CSVs              | `data/csv/backup/`    | `meter_manager.py` L957  | Auto-rotated by date             |

- **Retention:** 14 days (`DEFAULT_RETENTION_DAYS` in `meter_manager.py` L81)
- **Rotation:** `_perform_safe_rotation()` at L957 — archives old file, creates new one
- **Corruption repair:** `_detect_and_repair_corruption()` at L782

### State Files

| File                  | Location      | Purpose                                  |
|-----------------------|---------------|------------------------------------------|
| `rtc_state.json`      | `data/`       | Last-known-good time for drift detection |

### Exports

| File              | Location    | Purpose                            |
|-------------------|-------------|------------------------------------|
| `DATA_*.csv`      | `exports/`  | Copies made by Terminal UI export  |
| `DATA_ALL.csv`    | `exports/`  | Full data export                   |
| `EVENTS.csv`      | `exports/`  | Event log export                   |

---

## 9. Setup & Deployment

Three setup paths depending on access method:

### Path A — Full Master Setup (fresh Pi, HDMI + keyboard)
```bash
cd /home/pi/Desktop/offline-setup-12Sep
sudo bash scripts/setup/master_setup.sh
```
Runs 8 steps: permissions → directories → Python venv → static IP → services → WiFi AP → config → user groups.
See `scripts/setup/master_setup.sh` for details.

### Path B — One-Click Python Setup (just the software)
```bash
bash scripts/setup/one_click_system_py313.sh --enable-services
```
Installs Python 3.13, creates venv, installs offline wheels, enables systemd services.

### Path C — SSH Quick Setup Menu
```bash
bash scripts/setup/quick_setup.sh
```
Interactive 5-option menu: Master Setup / Enable Services / Start UI / System Test / Exit.

### Desktop GUI Setup
Double-click `scripts/launchers/MasterSetup_Admin.desktop` or `SimpleMeterUI_Admin.desktop`.

---

## 10. Testing

```bash
# Quick test (file existence, syntax, config)
bash tests/test_system.sh

# Full test (+ venv, services, network, groups)
bash tests/test_system.sh --full
```

| Section | What it checks                     | Line in test_system.sh |
|---------|------------------------------------|------------------------|
| 1       | Environment (Python, venv exists)  | L123                   |
| 2       | Directory structure                | L158                   |
| 3       | Core Python files exist + syntax   | L170, L188             |
| 4       | Setup & launcher scripts exist     | L200                   |
| 5       | Configuration files valid JSON     | L216                   |
| 6       | Offline packages present           | L224                   |
| 7       | Documentation files                | L237                   |
| 8*      | Python venv health                 | L259                   |
| 9*      | Systemd services status            | L279                   |
| 10*     | Network (IP, interfaces)           | L302                   |
| 11*     | User groups (gpio, i2c, dialout)   | L316                   |

\* = `--full` only

---

## 11. Supported Meter Models

| Model Constant | Display Name | Driver File                       | Dispatch Line (meter_device.py) |
|----------------|-------------|------------------------------------|---------------------------------|
| `LG6400`       | LG6400      | `src/devices/elmeasure_LG6400.py`  | L147                            |
| `EN8400`       | EN8400      | (uses LG6400 driver)              | L149                            |
| `EN8100`       | EN8100      | (uses LG6400 driver)              | L151                            |
| `LG+5220`      | LG+5220     | `src/devices/elmeasure_LG5220.py`  | L153                            |
| `LG+5310`      | LG+5310     | `src/devices/elmeasure_LG5310.py`  | L155                            |
| `EN8410`       | EN8410      | `src/devices/elmeasure_EN8410.py`  | L157                            |
| `ELR300`       | ELR300      | `src/devices/elmeasure_iELR300.py` | L159                            |

**To add a new model:**
1. Create `src/devices/elmeasure_NEWMODEL.py` with a `ReadMeterData(client, addr)` function
2. Add `DEV_ELM_NEWMODEL` constant to `src/utils/macros.py` (after L50)
3. Add import to `src/utils/macros.py` (after L30)
4. Add dispatch case to `src/devices/meter_device.py` `read_data()` (after L159)

---

## 12. Network Access Quick Reference

| Method          | Address              | When                                         |
|-----------------|----------------------|----------------------------------------------|
| Ethernet (SCP)  | `192.168.137.100`    | Laptop plugged in via Ethernet cable          |
| WiFi AP (HTTP)  | `http://192.168.50.1:8080` | Phone/laptop connected to SimpleMeter WiFi |
| WiFi AP (SSH)   | `ssh pi@192.168.50.1`     | SSH over WiFi for terminal access          |
| Ethernet (SSH)  | `ssh pi@192.168.137.100`  | SSH over Ethernet                          |

**SCP download example:**
```bash
scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/exports/DATA_ALL.csv .
```

---

## Appendix: Complete File Index

```
offline-setup-12Sep/
│
├── config/
│   ├── config.json              — Main system configuration
│   ├── device_config.json       — Meter device list (name, address, model)
│   └── examples/                — Example config files
│
├── data/
│   ├── rtc_state.json           — RTC time-sanitizer state
│   └── csv/
│       ├── DATA_ALL.csv         — Active data log (14-day rolling)
│       ├── EVENTS.csv           — System event log
│       └── backup/              — Archived rotated CSVs
│
├── src/
│   ├── dashboard/
│   │   ├── simple_rpi_dashboard.py  — Engine: systemd service, Modbus polling loop (1196 lines)
│   │   ├── terminal_meter_ui.py     — Terminal/SSH curses UI (1518 lines)
│   │   └── simple_meter_ui.py       — Desktop Tkinter GUI (1016 lines)
│   │
│   ├── devices/
│   │   ├── meter_manager.py         — Central meter + CSV orchestrator (1066 lines)
│   │   ├── meter_device.py          — Single meter abstraction + model dispatch
│   │   ├── elmeasure_LG6400.py      — LG6400/EN8400/EN8100 Modbus driver
│   │   ├── elmeasure_LG5220.py      — LG+5220 Modbus driver
│   │   ├── elmeasure_LG5310.py      — LG+5310 Modbus driver
│   │   ├── elmeasure_EN8410.py      — EN8410 Modbus driver
│   │   └── elmeasure_iELR300.py     — iELR300 Modbus driver
│   │
│   ├── utils/
│   │   ├── config_loader.py         — Shared JSONC parser (used everywhere)
│   │   ├── paths.py                 — Project root + config dir resolution
│   │   ├── macros.py                — Constants: PARAMETERS, REG_ADDRESSES, model names
│   │   ├── rtc_module.py            — DS3231 RTC I2C hardware driver
│   │   ├── time_sanitizer.py        — Time validation + drift/jump detection
│   │   ├── configure_device.py      — Tkinter device-config editor popup
│   │   ├── set_rtc_from_system.py   — One-shot: set RTC from system clock
│   │   └── venv_utils.py            — Venv activation helpers
│   │
│   ├── network/
│   │   ├── mqtt_client.py           — MQTT publisher for meter readings
│   │   └── cloud_sync.py            — Cloud sync (rclone/rsync/scp) + network watcher
│   │
│   └── services/                    — (empty after cleanup)
│
├── scripts/
│   ├── setup/
│   │   ├── master_setup.sh          — Full 8-step system setup
│   │   ├── one_click_system_py313.sh — Python 3.13 + venv + packages
│   │   ├── enable_auto_start.sh     — Install all systemd services
│   │   ├── setup_static_ethernet.sh — Configure eth0 static IP
│   │   └── quick_setup.sh           — SSH interactive setup menu
│   │
│   ├── launchers/
│   │   ├── MasterSetup_Admin.desktop  — Desktop shortcut: master setup
│   │   ├── SimpleMeterUI_Admin.desktop — Desktop shortcut: GUI
│   │   └── terminal_ui.sh           — Launch terminal UI in venv
│   │
│   └── system/
│       ├── download_meter_data.sh   — SCP-based data download helper
│       └── update_pull.sh           — Git pull updater
│
├── usb_download_mvp/
│   ├── server.py                    — Flask web download server
│   ├── templates/index.html         — Download page HTML/JS
│   ├── config.json                  — Web server config
│   ├── scripts/
│   │   └── enforce_ap_mode.sh       — WiFi AP start/stop
│   ├── network/                     — hostapd + dnsmasq configs
│   ├── systemd/                     — download-server + usb_ap service units
│   └── dnsmasq/                     — DNS config for captive portal
│
├── tests/
│   ├── test_system.sh               — Main system test (quick + full)
│   ├── TEST_05_HARDWARE_dual_rate.py
│   ├── TEST_11_physical_time_change.sh
│   ├── TEST_14_physical_rotation.sh
│   ├── TEST_18_physical_blackout.sh
│   └── TEST_99_full_system_hardware.py
│
├── packages_folder/                 — Offline .whl packages for pip
├── exports/                         — CSV exports for download
├── logs/                            — RS-485 reliability test logs
├── docs/                            — Documentation
│   ├── developer/                   — This file + dev docs
│   └── user/                        — User-facing docs
│
└── archive/                         — Deprecated scripts & old versions
```

---

*Generated: auto — line numbers verified against current codebase.*
