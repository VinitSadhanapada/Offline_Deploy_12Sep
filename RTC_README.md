# DS3231 RTC — Time Management for Raspberry Pi

This system keeps accurate time on the RPIs using a DS3231 Real-Time Clock module, even without internet or after power loss.

## Quick Reference

| Situation | Command |
|-----------|---------|
| **Time is wrong** | `sudo bash fix_time.sh` |
| **Check RTC health** | `bash rtc_health_check.sh` |
| **First-time setup** | `sudo bash rtc_setup.sh` → reboot |

## How It Works

```
BOOT (no internet) ──→ RTC sets system time automatically
BOOT (internet)    ──→ NTP sets system time, then writes to RTC
RUNTIME            ──→ time_sanitizer checks drift every 60s
POWER LOSS         ──→ RTC keeps ticking, system syncs on next boot
```

## Files

### Scripts (project root)

| File | Purpose | Run with |
|------|---------|----------|
| `fix_time.sh` | Fix time anytime — handles full NTP↔RTC flow | `sudo bash fix_time.sh` |
| `rtc_setup.sh` | One-time hardware setup (I2C, overlay, services) | `sudo bash rtc_setup.sh` |
| `rtc_health_check.sh` | 9-point diagnostic check | `bash rtc_health_check.sh` |
| `set_rtc.py` | Write current system time → RTC | `sudo python3 set_rtc.py` |

### Python Modules (src/utils/)

| File | Purpose |
|------|---------|
| `rtc_module.py` | DS3231 driver — auto-detects kernel/sysfs/I2C mode |
| `time_sanitizer.py` | Boot validation, drift correction, time jump logging |

These are imported by `meter_manager.py` automatically.

## First-Time Setup

### 1. Wiring

| DS3231 Pin | RPi Pin | GPIO |
|-----------|---------|------|
| VCC | Pin 1 | 3.3V |
| GND | Pin 6 | GND |
| SDA | Pin 3 | GPIO2 |
| SCL | Pin 5 | GPIO3 |

### 2. Software Setup

```bash
sudo bash rtc_setup.sh
# Follow prompts, reboot when asked
```

### 3. Verify

```bash
bash rtc_health_check.sh
# All checks should pass
```

### 4. Set Correct Time

```bash
sudo bash fix_time.sh
# Syncs NTP → system → RTC (if internet available)
# Or RTC → system (if no internet)
```

## Troubleshooting

### RTC not detected
```bash
sudo i2cdetect -y 1
# Should show 68 or UU at row 60, column 8
# If not: check wiring (VCC must be 3.3V, not 5V)
```

### Time is in UTC instead of IST
The RTC stores UTC internally. `rtc_module.py` converts to local time automatically. If you see UTC times, ensure you have the latest `rtc_module.py`.

### "hwclock not found"
```bash
sudo apt install util-linux
```

### Python says "smbus not available"
```bash
sudo apt install python3-smbus
```

### Module import errors
Ensure files are in the right locations:
```
project_root/
├── src/utils/rtc_module.py        ← I2C driver
├── src/utils/time_sanitizer.py    ← time integrity
├── fix_time.sh
├── set_rtc.py
├── rtc_setup.sh
└── rtc_health_check.sh
```

## How fix_time.sh Works

```
1. Check internet (ping 8.8.8.8)
   ├── YES → Enable NTP → Wait for sync → Write system time → RTC
   └── NO  → Read RTC → Set system time
2. Show final state (system time + RTC time)
```

## Events Logged to EVENTS.csv

The `time_sanitizer` logs these events automatically:

| Event Type | Meaning |
|-----------|---------|
| `TIME_CORRECTION` | System time corrected from RTC on boot |
| `BOOT_GAP` | Power was off for X minutes |
| `TIME_DRIFT` | Runtime drift > 5s detected and corrected |
| `TIME_JUMP` | > 1 hour jump between CSV readings |
| `RTC_BATTERY_FAIL` | RTC year < 2024 (battery dead) |
| `RTC_OSF_SET` | DS3231 oscillator stop flag (power lost to RTC chip) |
