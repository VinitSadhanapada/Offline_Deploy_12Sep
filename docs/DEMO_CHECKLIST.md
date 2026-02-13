# Demo Checklist

## Desktop GUI (`simple_meter_ui.py`)
- [ ] **Manual Run** — trigger a meter reading, show it completes
- [ ] **Live Readings** — open live table, watch values update
- [ ] **Configure Devices** — add/edit/remove a meter
- [ ] **View/Edit Config** — open config.json, show editable settings
- [ ] **CSV Interval slider** — change slow-write interval, click Apply
- [ ] **WiFi AP toggle** — enable checkbox, show AP comes up
- [ ] **Setup Environment** — show venv + packages install
- [ ] **Enable Auto-Start** — install systemd services
- [ ] **Force Stop Logging** — kill a running read loop
- [ ] **Reboot System** — (mention, don't click mid-demo)

## Terminal UI (SSH: `terminal_meter_ui.py`)
- [ ] **1 — Live Meter Readings** — real-time polling over SSH
- [ ] **2 — Export CSV Data** — copies to ~/exports for SCP download
- [ ] **4 — System Status** — disk, services, uptime overview
- [ ] **5 — Configure Devices** — add/edit meters from terminal
- [ ] **6 — View Configuration** — show current config
- [ ] **0 — WiFi AP Control** — toggle hotspot on/off

## Web Download (phone on WiFi AP → `http://192.168.50.1:8080`)
- [ ] **Download ALL Data** — one-tap full CSV download
- [ ] **Date range filter** — pick start/end, download filtered ZIP

## Hardware / System
- [ ] **RS-485 Modbus** — show live data from a real Elmeasure meter
- [ ] **RTC (DS3231)** — mention time survives power loss
- [ ] **Offline install** — all packages in `packages_folder/`, no internet needed
- [ ] **Static Ethernet** — laptop plugs in, gets data via `192.168.137.100`
- [ ] **CSV rotation** — 14-day rolling, auto-archive to `data/csv/backup/`
- [ ] **EVENTS.csv** — show blackout/restart events logged automatically

---

## EVENTS.csv Demo — Trigger Every Event Type

Open a second terminal to watch events live:
```bash
tail -f ~/Desktop/offline-setup-12Sep/data/csv/EVENTS.csv
```

### Meter / Comm Events (from `meter_manager.py`)

| # | Event Type | How to physically trigger | Expected EVENTS.csv row |
|---|-----------|--------------------------|------------------------|
| 1 | `RPI_USB_COMM_ERROR` | **Unplug the USB-to-RS485 adapter** from the Pi while logging is running | `RPI_USB_COMM_ERROR, <meter_name>, Values contain -1: RPi cannot communicate with USB adapter` |
| 2 | `COMM_RESTORED` | **Plug the USB adapter back in** (may need to rebind: `echo "1-1.1:1.0" \| sudo tee /sys/bus/usb/drivers/ftdi_sio/bind`) | `COMM_RESTORED, <meter_name>, Communication restored (was RPI_USB_ERROR)` |
| 3 | `METER_COMM_ERROR` | **Disconnect the RS-485 wire** between USB adapter and meter (leave USB plugged into Pi) | `METER_COMM_ERROR, <meter_name>, All parameter values are 0: USB adapter cannot reach meter on RS-485 bus` |
| 4 | `COMM_RESTORED` | **Reconnect the RS-485 wire** to the meter | `COMM_RESTORED, <meter_name>, Communication restored (was METER_COMM_ERROR)` |
| 5 | `BLACKOUT_START` | **Switch off the MCB/breaker** feeding the meter's CT line (meter stays powered via separate supply) | `BLACKOUT_START, <meter_name>, Freq=0 with cumulative counters intact (Wh=..., OnHrs=...)` |
| 6 | `BLACKOUT_END` | **Switch the MCB/breaker back on** | `BLACKOUT_END, <meter_name>, Power restored. Started: <time>` |

### System / Time Events (from `time_sanitizer.py`)

| # | Event Type | How to physically trigger | Expected EVENTS.csv row |
|---|-----------|--------------------------|------------------------|
| 7 | `BOOT` | **Reboot the Pi** (`sudo reboot`), wait for it to come back | `BOOT, SYSTEM, {"type":"BOOT", "resumed_after_minutes":...}` |
| 8 | `TIME_CORRECTION` | **Set system clock wrong** before starting: `sudo date -s "2026-02-09 10:00:00"` then start the dashboard (RTC will correct it) | `TIME_CORRECTION, SYSTEM, {"type":"TIME_CORRECTION", "offset_sec":..., "action":"correcting_to_rtc"}` |
| 9 | `TIME_DRIFT_DETECTED` | **While logging, set system clock 2 min off**: `sudo date -s "+2 minutes"` — next CSV cycle detects drift vs RTC | `TIME_DRIFT_DETECTED, SYSTEM, {"type":"TIME_DRIFT_DETECTED", "drift_seconds":...}` |
| 10 | `TIME_JUMP` | **While logging, jump system clock 2 hours forward**: `sudo date -s "+2 hours"` — detected at next CSV write | `TIME_JUMP, SYSTEM, {"type":"TIME_JUMP", "direction":"forward", "hours":2.0}` |

**RTC auto-correction demo (step-by-step):**
```bash
# 1. Check current correct time (system + RTC should match)
date
python3 -c "import sys; sys.path.insert(0,'src'); from utils.rtc_module import get_rtc_time; print('RTC:', get_rtc_time())"

# 2. Disable NTP (otherwise it overrides date -s immediately)
sudo timedatectl set-ntp false

# 3. Set system clock to something obviously wrong
sudo date -s "2026-01-01 03:00:00"

# 4. Confirm it's wrong
date                  # → Thu Jan  1 03:00:00 IST 2026
python3 -c "import sys; sys.path.insert(0,'src'); from utils.rtc_module import get_rtc_time; print('RTC:', get_rtc_time())"
                      # → still shows correct time (Feb 9)

# 5. Start the dashboard (or it's already running — restart it)
sudo systemctl restart meter-dashboard

# 6. Wait ~5 seconds, then check — system clock should be auto-corrected by RTC
date                  # → should be back to correct Feb 9 time

# 7. Verify the correction was logged
tail -5 ~/Desktop/offline-setup-12Sep/data/csv/EVENTS.csv
# → expect TIME_CORRECTION row with offset_sec showing ~hours of difference

# 8. Re-enable NTP when done
sudo timedatectl set-ntp true
```
| 11 | `RTC_BATTERY_FAIL` | **Remove the coin cell** from the DS3231 module, power-cycle the Pi (RTC resets to year 2000) | `RTC_BATTERY_FAIL, SYSTEM, {"type":"RTC_BATTERY_FAIL", "rtc_year":2000}` |
| 12 | `RTC_UNAVAILABLE` | **Disconnect the I2C cable** to the DS3231 module, then restart the dashboard | `RTC_UNAVAILABLE, SYSTEM, {"type":"RTC_UNAVAILABLE", "warning":"Hardware RTC could not be read"}` |

### Data Management Events

| # | Event Type | How to trigger | Expected EVENTS.csv row |
|---|-----------|---------------|------------------------|
| 13 | `CSV_ROTATION` | **Let DATA_ALL.csv grow past 1MB** (or manually: grow it with test data), rotation triggers automatically | `CSV_ROTATION, SYSTEM, {"type":"CSV_ROTATION", "archive_file":"...", "size_mb":...}` |

### Suggested demo order (minimal disruption)
1. Start with system running normally — show live data ✅
2. **Unplug RS-485 wire** → #3 METER_COMM_ERROR → replug → #4 COMM_RESTORED
3. **Unplug USB adapter** → #1 RPI_USB_COMM_ERROR → replug+rebind → #2 COMM_RESTORED
4. **Switch off MCB** → #5 BLACKOUT_START → switch on → #6 BLACKOUT_END
5. **`sudo date -s "+2 hours"`** → #10 TIME_JUMP + #9 TIME_DRIFT_DETECTED (auto-corrected)
6. Open `EVENTS.csv` and walk through all the logged rows
