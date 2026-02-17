#!/usr/bin/env python3
"""
Time Sanitizer — RTC-based System Time Integrity
=================================================
Keeps system time accurate using DS3231 hardware RTC.

Lifecycle:
  BOOT (no internet):  RTC → System   (validate_and_correct)
  RUNTIME:             RTC vs System   (check_drift, every CSV cycle)
  NTP AVAILABLE:       System → RTC    (handled by fix_time.sh or set_rtc.py)
  POWER LOSS:          Detects boot gap from state file

All events are logged to EVENTS.csv via meter_manager callbacks.
"""
import os
import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("time_sanitizer")

# Import RTC module (same package or standalone)
RTC_MODULE_AVAILABLE = False
try:
    from src.utils.rtc_module import get_rtc, is_rtc_available
    RTC_MODULE_AVAILABLE = True
except ImportError:
    try:
        from rtc_module import get_rtc, is_rtc_available
        RTC_MODULE_AVAILABLE = True
    except ImportError:
        pass


def _get_uptime_seconds():
    """Read system uptime from /proc/uptime (Linux only)."""
    try:
        with open('/proc/uptime', 'r') as f:
            return float(f.readline().split()[0])
    except Exception:
        return 0.0


class RTCTimeSanitizer:
    """
    Manages system time integrity using DS3231 RTC as reference.
    
    Args:
        state_file_path: Path to JSON file for persistent state.
                         Defaults to <project>/data/rtc_state.json
    """

    # Thresholds
    BOOT_CORRECTION_THRESHOLD = 2      # seconds — correct system time if off by more than this
    DRIFT_THRESHOLD = 5                # seconds — runtime drift alarm
    DISCONTINUITY_THRESHOLD = 3600     # seconds — 1 hour jump between CSV writes
    BATTERY_FAIL_YEAR = 2024           # If RTC year < this, battery is dead
    
    def __init__(self, state_file_path=None):
        if state_file_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            state_file_path = str(project_root / "data" / "rtc_state.json")
        
        self.state_file = Path(state_file_path)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Check RTC availability
        self.rtc_available = False
        self.rtc = None
        if RTC_MODULE_AVAILABLE:
            try:
                # Create RTC with fallback DISABLED — we want to know if it fails
                self.rtc = get_rtc(fallback_to_system=False)
                self.rtc_available = self.rtc.is_available()
            except Exception as e:
                logger.debug(f"RTC init failed: {e}")
        
        if self.rtc_available:
            logger.info("DS3231 RTC detected and responding")
        else:
            logger.info("RTC not available — time integrity relies on NTP/manual")
        
        # Load persistent state
        self.state = self._load_state()
        self.last_rtc_check = None
    
    # ── State persistence ───────────────────────────────────────────
    
    def _load_state(self):
        """Load state from JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load state: {e}")
        
        return {
            "last_known_good_time": None,
            "rtc_battery_ok": True,
            "last_boot_time": None
        }
    
    def _save_state(self):
        """Save state with fsync (survives power loss)."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    # ── RTC access (with explicit failure detection) ────────────────
    
    def _read_rtc_time(self):
        """
        Read RTC time, returning None on failure.
        Unlike rtc.get_time() which may fallback to system time,
        this method explicitly returns None if RTC can't be read.
        """
        if not self.rtc_available or self.rtc is None:
            return None
        
        try:
            if not self.rtc.is_available():
                self.rtc_available = False
                return None
            # fallback_to_system=False means this raises on failure
            return self.rtc.get_time()
        except Exception as e:
            logger.debug(f"RTC read failed: {e}")
            return None
    
    def _correct_system_time(self, target_time):
        """
        Set system clock to target_time.
        Disables NTP first so correction isn't overwritten.
        """
        try:
            # Disable NTP temporarily
            subprocess.run(
                ['sudo', 'timedatectl', 'set-ntp', 'false'],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
        
        try:
            time_str = target_time.strftime("%Y-%m-%d %H:%M:%S")
            result = subprocess.run(
                ['sudo', 'date', '-s', time_str],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                logger.info(f"System time corrected to: {time_str}")
                return True
            else:
                logger.error(f"date -s failed: {result.stderr.decode().strip()}")
                return False
        except Exception as e:
            logger.error(f"Time correction failed: {e}")
            return False
    
    # ── Main validation (call on boot) ──────────────────────────────
    
    def validate_and_correct(self):
        """
        Boot-time validation. Call once when meter service starts.
        
        Flow:
          1. Read RTC time
          2. If RTC year < 2024 → battery dead → restore from state file + uptime
          3. If System vs RTC offset > 2s → correct system from RTC
          4. Detect boot gap (time since last shutdown)
        
        Returns:
            tuple: (is_valid: bool, events: list[dict])
        """
        events = []
        system_now = datetime.now()
        
        # ── No RTC: just update state and return OK ──
        if not self.rtc_available:
            logger.debug("No RTC — skipping validation")
            self.state["last_known_good_time"] = system_now.isoformat()
            self._save_state()
            return True, events
        
        # ── Read RTC ──
        rtc_now = self._read_rtc_time()
        
        if rtc_now is None:
            events.append({
                "type": "RTC_READ_FAIL",
                "timestamp": system_now.isoformat(),
                "warning": "Could not read DS3231 — I2C error"
            })
            return False, events
        
        # ── Check 1: Battery failure (year < 2024) ──
        if rtc_now.year < self.BATTERY_FAIL_YEAR:
            self.state["rtc_battery_ok"] = False
            events.append({
                "type": "RTC_BATTERY_FAIL",
                "rtc_reading": rtc_now.isoformat(),
                "rtc_year": rtc_now.year
            })
            logger.warning(f"RTC battery fail: year={rtc_now.year}")
            
            # Try to restore from state + system uptime
            if self.state.get("last_known_good_time"):
                try:
                    last_good = datetime.fromisoformat(self.state["last_known_good_time"])
                    uptime = _get_uptime_seconds()
                    restored = last_good + timedelta(seconds=uptime)
                    
                    self._correct_system_time(restored)
                    events.append({
                        "type": "TIME_RESTORED",
                        "restored_to": restored.isoformat(),
                        "source": "state_file + uptime",
                        "uptime_seconds": round(uptime, 1)
                    })
                except Exception as e:
                    logger.error(f"Restore failed: {e}")
            else:
                events.append({
                    "type": "NO_HISTORY",
                    "warning": "RTC dead and no state file — set time manually!"
                })
            
            self._save_state()
            return False, events
        
        # ── RTC is valid ──
        self.state["rtc_battery_ok"] = True
        
        # ── Check 2: System vs RTC offset ──
        offset = (system_now - rtc_now).total_seconds()
        abs_offset = abs(offset)
        
        if abs_offset > self.BOOT_CORRECTION_THRESHOLD:
            events.append({
                "type": "TIME_CORRECTION",
                "system_was": system_now.isoformat(),
                "rtc_is": rtc_now.isoformat(),
                "offset_seconds": round(offset, 2),
                "action": "correcting_system_to_rtc"
            })
            logger.info(f"Boot correction: system off by {offset:+.1f}s, setting from RTC")
            self._correct_system_time(rtc_now)
        
        # ── Check 3: Boot gap detection ──
        last_good_str = self.state.get("last_known_good_time")
        if last_good_str:
            try:
                last_good = datetime.fromisoformat(last_good_str)
                gap = (rtc_now - last_good).total_seconds()
                
                if gap > 60:  # > 1 minute gap = was powered off
                    events.append({
                        "type": "BOOT_GAP",
                        "offline_seconds": round(gap),
                        "offline_minutes": round(gap / 60, 1),
                        "last_seen": last_good_str,
                        "resumed_at": rtc_now.isoformat()
                    })
                    logger.info(f"Boot gap: offline for {gap/60:.1f} minutes")
            except (ValueError, TypeError):
                pass
        
        # ── Check 4: Oscillator stop flag ──
        osf = self.rtc.check_oscillator_stopped()
        if osf:
            events.append({
                "type": "RTC_OSF_SET",
                "warning": "DS3231 oscillator was stopped — time may be inaccurate",
                "action": "flag_cleared"
            })
            self.rtc.clear_oscillator_flag()
            logger.warning("DS3231 OSF flag was set — cleared")
        
        # ── Update state ──
        self.state["last_known_good_time"] = rtc_now.isoformat()
        self.state["last_boot_time"] = rtc_now.isoformat()
        self._save_state()
        self.last_rtc_check = rtc_now
        
        return True, events
    
    # ── Runtime drift check (call every CSV cycle ~60s) ─────────────
    
    def check_drift(self):
        """
        Compare system clock vs RTC. If drift > 5s, correct and return event.
        
        Returns:
            dict: Event if drift detected, else None
        """
        system_now = datetime.now()
        
        # No RTC — just persist state
        if not self.rtc_available:
            self.state["last_known_good_time"] = system_now.isoformat()
            self._save_state()
            return None
        
        if not self.state.get("rtc_battery_ok", True):
            return None
        
        rtc_now = self._read_rtc_time()
        if rtc_now is None:
            return None
        
        drift = abs((system_now - rtc_now).total_seconds())
        
        if drift > self.DRIFT_THRESHOLD:
            event = {
                "type": "TIME_DRIFT",
                "drift_seconds": round(drift, 2),
                "system_time": system_now.isoformat(),
                "rtc_time": rtc_now.isoformat(),
                "action": "corrected"
            }
            logger.warning(f"Drift detected: {drift:.1f}s — correcting from RTC")
            self._correct_system_time(rtc_now)
            self.state["last_known_good_time"] = rtc_now.isoformat()
            self._save_state()
            return event
        
        # No drift — update state
        self.state["last_known_good_time"] = system_now.isoformat()
        self._save_state()
        return None
    
    # ── Discontinuity check (between CSV timestamps) ────────────────
    
    def check_discontinuity(self, current_timestamp_str, last_timestamp_str):
        """
        Detect time jumps > 1 hour between CSV readings.
        
        Args:
            current_timestamp_str: "YYYY-MM-DD HH:MM:SS"
            last_timestamp_str: "YYYY-MM-DD HH:MM:SS"
            
        Returns:
            dict if jump > 1 hour, else None
        """
        if not last_timestamp_str or not current_timestamp_str:
            return None
        
        try:
            current = datetime.strptime(current_timestamp_str, "%Y-%m-%d %H:%M:%S")
            last = datetime.strptime(last_timestamp_str, "%Y-%m-%d %H:%M:%S")
            diff = (current - last).total_seconds()
            abs_diff = abs(diff)
            
            if abs_diff > self.DISCONTINUITY_THRESHOLD:
                return {
                    "type": "TIME_JUMP",
                    "direction": "forward" if diff > 0 else "backward",
                    "hours": round(abs_diff / 3600, 2),
                    "from": last_timestamp_str,
                    "to": current_timestamp_str
                }
        except (ValueError, TypeError):
            pass
        
        return None
    
    # ── Diagnostics ─────────────────────────────────────────────────
    
    def get_status(self):
        """Get current status for health check display."""
        system_now = datetime.now()
        rtc_now = self._read_rtc_time() if self.rtc_available else None
        
        status = {
            "rtc_available": self.rtc_available,
            "rtc_time": rtc_now.isoformat() if rtc_now else None,
            "system_time": system_now.isoformat(),
            "battery_ok": self.state.get("rtc_battery_ok", True),
            "last_known_good": self.state.get("last_known_good_time"),
            "drift_seconds": round(abs((system_now - rtc_now).total_seconds()), 2) if rtc_now else None,
            "state_file": str(self.state_file)
        }
        
        # Add temperature if RTC available
        if self.rtc_available and self.rtc:
            status["rtc_temperature_c"] = self.rtc.get_temperature()
            status["oscillator_stopped"] = self.rtc.check_oscillator_stopped()
        
        return status
