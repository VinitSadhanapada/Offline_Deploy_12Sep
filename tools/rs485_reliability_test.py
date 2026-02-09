#!/usr/bin/env python3
"""
RS485 Adapter Reliability Test
===============================
Polls an Elmeasure LG6400 meter every second via Modbus RTU and logs
success/failure statistics. Designed to run for 2+ days continuously.

QUICK START
-----------
  # 1. Make sure olad / DMX services are not holding the USB port:
  sudo systemctl stop olad dmx-blue-fade.service
  fuser /dev/ttyUSB0            # should return nothing

  # 2. Run the test (use the project venv — has pymodbus + pyserial):
  cd /home/pi/Desktop/offline-setup-12Sep
  ./venv/bin/python -u tools/rs485_reliability_test.py --duration 48 --port /dev/ttyUSB0

  # 3. Run in background (survives terminal close):
  nohup ./venv/bin/python -u tools/rs485_reliability_test.py --duration 48 --port /dev/ttyUSB0 &

VIEWING LOGS
------------
  # Latest log file:
  ls -lt logs/rs485_reliability_*.csv | head -1

  # Follow live (tail):
  tail -f logs/rs485_reliability_5.csv

  # Count OK vs ERR:
  grep -c ',OK,'  logs/rs485_reliability_5.csv
  grep -c ',ERR,' logs/rs485_reliability_5.csv

  # Last 20 entries:
  tail -20 logs/rs485_reliability_5.csv

  # Check if still running:
  ps aux | grep rs485_reliability | grep -v grep

OPTIONS
-------
  --port PORT        Serial port          (default: /dev/ttyUSB0)
  --addr ADDR        Modbus slave address  (default: 1)
  --baud BAUD        Baud rate             (default: 9600)
  --interval SECS    Poll interval         (default: 1.0)
  --duration HOURS   Test duration         (default: 48)

TROUBLESHOOTING
---------------
  ModuleNotFoundError: No module named 'pymodbus'
      → Use the venv Python:  ./venv/bin/python -u tools/rs485_reliability_test.py ...

  FATAL: Could not open serial port
      → Check adapter: ls -la /dev/ttyUSB0
      → Kill olad:      sudo kill $(fuser /dev/ttyUSB0 2>/dev/null)
      → Rebind driver:  echo '1-1.1:1.0' | sudo tee /sys/bus/usb/drivers/ftdi_sio/bind

  USB adapter keeps disconnecting (dmesg shows attach then disconnect ~5s later)
      → The udev rule 99-dmx-restart.rules triggers olad which grabs the port.
        Fix:  sudo mv /etc/udev/rules.d/99-dmx-restart.rules{,.disabled}
              sudo udevadm control --reload-rules

Requires: pymodbus, pyserial  (both in venv)
"""

import argparse
import csv
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve project root
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# pymodbus import (works with 2.x and 3.x)
# ---------------------------------------------------------------------------
_PYMODBUS3 = False
try:
    from pymodbus.client import ModbusSerialClient          # pymodbus 3.x
    _PYMODBUS3 = True
except ImportError:
    from pymodbus.client.sync import ModbusSerialClient     # pymodbus 2.x

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_PORT     = "/dev/ttyUSB0"
DEFAULT_ADDR     = 1
DEFAULT_BAUD     = 9600
DEFAULT_PARITY   = "E"
DEFAULT_STOPBITS = 1
DEFAULT_BYTESIZE = 8
DEFAULT_TIMEOUT  = 0.5          # seconds per Modbus transaction
POLL_INTERVAL    = 1.0          # seconds between polls
DEFAULT_DURATION = 48           # hours

# LG6400 register to read (Voltage L-N average = register 140, 2 regs = 1 float32)
TEST_REGISTER    = 140
TEST_REG_COUNT   = 2

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
stop_flag = False


def handle_signal(signum, frame):
    global stop_flag
    stop_flag = True


def parse_args():
    ap = argparse.ArgumentParser(description="RS485 adapter reliability test")
    ap.add_argument("--port",     default=DEFAULT_PORT,     help=f"Serial port (default {DEFAULT_PORT})")
    ap.add_argument("--addr",     default=DEFAULT_ADDR,     type=int, help=f"Modbus slave address (default {DEFAULT_ADDR})")
    ap.add_argument("--baud",     default=DEFAULT_BAUD,     type=int, help=f"Baud rate (default {DEFAULT_BAUD})")
    ap.add_argument("--duration", default=DEFAULT_DURATION, type=float, help=f"Test duration in hours (default {DEFAULT_DURATION})")
    ap.add_argument("--interval", default=POLL_INTERVAL,    type=float, help=f"Poll interval in seconds (default {POLL_INTERVAL})")
    return ap.parse_args()


def decode_float32(regs):
    """Decode two 16-bit registers (word-swapped / CDAB byte order) to float32.

    The LG6400 sends the low word first (CDAB), so we swap before decoding.
    """
    from struct import unpack, pack
    raw = pack(">HH", regs[1], regs[0])   # word-swap: CDAB → ABCD
    return unpack(">f", raw)[0]


def connect(port, baud, parity, stopbits, bytesize, timeout):
    """Create and connect a Modbus RTU client. Returns (client, error_str|None)."""
    kwargs = dict(port=port, baudrate=baud, parity=parity,
                  stopbits=stopbits, bytesize=bytesize, timeout=timeout)
    if _PYMODBUS3:
        client = ModbusSerialClient(**kwargs)
    else:
        client = ModbusSerialClient(method="rtu", **kwargs)
    if not client.connect():
        return None, "Could not open serial port"
    return client, None


def poll_once(client, slave_addr):
    """
    Read TEST_REGISTER from the meter.
    Returns (value_float | None, error_string | None, latency_ms).
    """
    t0 = time.monotonic()
    try:
        result = client.read_holding_registers(TEST_REGISTER, TEST_REG_COUNT, unit=slave_addr)
    except Exception as e:
        latency = (time.monotonic() - t0) * 1000
        return None, f"Exception: {e}", latency

    latency = (time.monotonic() - t0) * 1000

    if result is None:
        return None, "No response (None)", latency

    if hasattr(result, "isError") and result.isError():
        return None, f"Modbus error: {result}", latency

    if not hasattr(result, "registers") or len(result.registers) < TEST_REG_COUNT:
        return None, f"Bad response: {result}", latency

    try:
        val = decode_float32(result.registers)
    except Exception as e:
        return None, f"Decode error: {e}", latency

    return val, None, latency


# ---------------------------------------------------------------------------
# Stats tracker
# ---------------------------------------------------------------------------
class Stats:
    def __init__(self):
        self.total = 0
        self.ok = 0
        self.errors = 0
        self.consecutive_errors = 0
        self.max_consecutive_errors = 0
        self.error_bursts = 0          # number of error "runs"
        self.latency_sum = 0.0
        self.latency_max = 0.0
        self.latency_min = float("inf")
        self.last_value = None
        self.last_error = None
        self.start_time = time.time()

    def record_ok(self, value, latency_ms):
        self.total += 1
        self.ok += 1
        if self.consecutive_errors > 0:
            self.consecutive_errors = 0
        self.last_value = value
        self.last_error = None
        self._record_latency(latency_ms)

    def record_error(self, error_str, latency_ms):
        self.total += 1
        self.errors += 1
        if self.consecutive_errors == 0:
            self.error_bursts += 1
        self.consecutive_errors += 1
        if self.consecutive_errors > self.max_consecutive_errors:
            self.max_consecutive_errors = self.consecutive_errors
        self.last_error = error_str
        self._record_latency(latency_ms)

    def _record_latency(self, ms):
        self.latency_sum += ms
        if ms > self.latency_max:
            self.latency_max = ms
        if ms < self.latency_min:
            self.latency_min = ms

    @property
    def error_rate(self):
        return (self.errors / self.total * 100) if self.total else 0.0

    @property
    def avg_latency(self):
        return (self.latency_sum / self.total) if self.total else 0.0

    @property
    def uptime_str(self):
        elapsed = time.time() - self.start_time
        h, rem = divmod(int(elapsed), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def summary(self):
        lines = [
            "",
            "=" * 60,
            "  RS485 RELIABILITY TEST — SUMMARY",
            "=" * 60,
            f"  Duration       : {self.uptime_str}",
            f"  Total polls    : {self.total}",
            f"  Successes      : {self.ok}",
            f"  Errors         : {self.errors}  ({self.error_rate:.2f}%)",
            f"  Error bursts   : {self.error_bursts}",
            f"  Max consec err : {self.max_consecutive_errors}",
            f"  Latency avg    : {self.avg_latency:.1f} ms",
            f"  Latency min    : {self.latency_min:.1f} ms" if self.latency_min != float("inf") else "  Latency min    : N/A",
            f"  Latency max    : {self.latency_max:.1f} ms",
            "=" * 60,
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV logger
# ---------------------------------------------------------------------------
def open_csv(log_dir):
    log_dir.mkdir(parents=True, exist_ok=True)
    # Find next available run number (rs485_reliability_1.csv, _2.csv, ...)
    existing = sorted(log_dir.glob("rs485_reliability_*.csv"))
    next_num = 1
    for p in existing:
        stem = p.stem  # e.g. "rs485_reliability_3"
        suffix = stem.replace("rs485_reliability_", "")
        if suffix.isdigit():
            next_num = max(next_num, int(suffix) + 1)
    fname = log_dir / f"rs485_reliability_{next_num}.csv"
    fh = open(fname, "w", newline="", buffering=1)   # line-buffered
    writer = csv.writer(fh)
    writer.writerow(["timestamp", "poll_num", "status", "value", "latency_ms", "error"])
    return fh, writer, fname


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    global stop_flag
    signal.signal(signal.SIGINT,  handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    args = parse_args()

    print()
    print("=" * 60)
    print("  RS485 Adapter Reliability Test")
    print("=" * 60)
    print(f"  Port     : {args.port}")
    print(f"  Address  : {args.addr}")
    print(f"  Baud     : {args.baud}")
    print(f"  Interval : {args.interval}s")
    print(f"  Duration : {args.duration}h")
    print(f"  Register : {TEST_REGISTER} (VLN avg, float32)")
    print("=" * 60)
    print()

    # Connect
    client, err = connect(args.port, args.baud, DEFAULT_PARITY,
                          DEFAULT_STOPBITS, DEFAULT_BYTESIZE, DEFAULT_TIMEOUT)
    if err:
        print(f"FATAL: {err}")
        print(f"  Check: ls -la {args.port}")
        print(f"  Check: sudo dmesg | tail -10")
        sys.exit(1)

    print(f"Connected to {args.port}")

    # CSV log
    log_dir = PROJECT_ROOT / "logs"
    fh, writer, csv_path = open_csv(log_dir)
    print(f"Logging to: {csv_path}")
    print()
    print("Polling... (Ctrl+C to stop early)")
    print()

    stats = Stats()
    end_time = time.time() + args.duration * 3600

    try:
        while not stop_flag and time.time() < end_time:
            ts = datetime.now()
            value, error, latency = poll_once(client, args.addr)

            if error:
                stats.record_error(error, latency)
                status = "ERR"
                val_str = ""
                err_str = error
            else:
                stats.record_ok(value, latency)
                status = "OK"
                val_str = f"{value:.2f}"
                err_str = ""

            # Write CSV row
            writer.writerow([
                ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                stats.total,
                status,
                val_str,
                f"{latency:.1f}",
                err_str,
            ])

            # Flush every 60 rows
            if stats.total % 60 == 0:
                fh.flush()

            # Console output (single line, overwrite)
            line = (
                f"\r  [{stats.uptime_str}]  "
                f"Poll #{stats.total:<6d}  "
                f"OK: {stats.ok}  "
                f"ERR: {stats.errors} ({stats.error_rate:.1f}%)  "
                f"Burst: {stats.error_bursts}  "
                f"MaxConsec: {stats.max_consecutive_errors}  "
                f"Lat: {latency:.0f}ms  "
            )
            if error:
                line += f"FAIL: {error[:40]}"
            else:
                line += f"V={value:.1f}V"

            sys.stdout.write(line.ljust(120))
            sys.stdout.flush()

            # Sleep until next poll
            elapsed = time.monotonic()
            time.sleep(max(0, args.interval - (latency / 1000)))

    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        fh.flush()
        fh.close()
        try:
            client.close()
        except Exception:
            pass

    print()
    print(stats.summary())
    print(f"\n  CSV log: {csv_path}\n")

    # Also append summary to the CSV file
    with open(csv_path, "a") as f:
        f.write("\n# " + stats.summary().replace("\n", "\n# ") + "\n")


if __name__ == "__main__":
    main()
