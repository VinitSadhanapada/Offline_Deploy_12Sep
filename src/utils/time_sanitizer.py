#!/usr/bin/env python3
"""
Time Sanitizer Module for RTC-based System Time Integrity.

This module manages system time integrity using the hardware RTC as reference.
Handles battery failures, drift correction, boot gap detection, and discontinuity logging.

Key Features:
- Persists last known good time across reboots (JSON state file)
- Detects RTC battery failure (year < 2024) and restores from state
- Corrects system time from RTC on boot if offset > 1 second
- Detects runtime drift > 1 minute and corrects
- Logs time jumps > 1 hour between CSV readings

All events are logged to EVENTS.csv for forensic analysis.
"""
import os
import json
import time
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Try to import rtc_module for direct I2C access to DS3231
try:
    from src.utils.rtc_module import get_rtc, is_rtc_available
    RTC_MODULE_AVAILABLE = True
except ImportError:
    RTC_MODULE_AVAILABLE = False


class RTCTimeSanitizer:
    """
    Manages system time integrity using RTC as reference.
    Handles battery failures, drift correction, and discontinuity logging.
    
    Args:
        state_file_path: Path to JSON file storing persistent state
        
    Attributes:
        state: Dictionary containing last_known_good_time, rtc_battery_ok, last_boot_time
        last_rtc_check: Timestamp of last RTC validation
        rtc_available: Whether RTC (DS3231 via I2C or hwclock) is available
    """
    
    def __init__(self, state_file_path=None):
        """
        Initialize RTCTimeSanitizer with state file path.
        
        Args:
            state_file_path: Path to JSON state file. Defaults to project data dir.
        """
        if state_file_path is None:
            # Default: project data directory
            project_root = Path(__file__).resolve().parent.parent.parent
            state_file_path = project_root / "data" / "rtc_state.json"
        
        self.state_file = Path(state_file_path)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Setup logger if not configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Check RTC availability - prefer rtc_module (I2C), fallback to hwclock
        self.rtc_available, self.rtc_method = self._check_rtc_available()
        if self.rtc_available:
            self.logger.debug(f"RTC available via {self.rtc_method}")
        else:
            self.logger.debug("RTC not available - RTC features disabled")
        
        # Legacy compatibility
        self.hwclock_available = self.rtc_available
        
        # Load or initialize state
        self.state = self._load_state()
        self.last_rtc_check = None
    
    def _check_rtc_available(self):
        """
        Check if RTC is available via rtc_module (I2C) or hwclock.
        
        Returns:
            tuple: (bool available, str method) - method is 'i2c', 'hwclock', or None
        """
        # First try rtc_module (direct I2C to DS3231)
        if RTC_MODULE_AVAILABLE:
            try:
                if is_rtc_available():
                    self.logger.debug("DS3231 RTC available via I2C")
                    return True, 'i2c'
            except Exception as e:
                self.logger.debug(f"rtc_module check failed: {e}")
        
        # Fallback to hwclock
        try:
            # Try to run hwclock with version flag (less intrusive than reading time)
            result = subprocess.run(
                ['which', 'hwclock'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                # hwclock exists, now check if we can actually use it
                result = subprocess.run(
                    ['sudo', 'hwclock', '-r'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return True, 'hwclock'
            return False, None
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False, None
        
    def _load_state(self):
        """
        Load persistent state (last good time, battery status) from JSON file.
        
        Returns:
            dict: State dictionary with last_known_good_time, rtc_battery_ok, last_boot_time
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.logger.debug(f"Loaded RTC state from {self.state_file}")
                    return state
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Could not load RTC state: {e}")
        
        return {
            "last_known_good_time": None,  # ISO format string
            "rtc_battery_ok": True,
            "last_boot_time": None
        }
    
    def _save_state(self):
        """
        Save state to disk with fsync (survives power loss).
        """
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            self.logger.debug(f"Saved RTC state to {self.state_file}")
        except Exception as e:
            self.logger.error(f"Failed to save RTC state: {e}")
    
    def get_rtc_time(self):
        """
        Read hardware RTC time via I2C (DS3231) or hwclock command.
        
        Returns:
            datetime: RTC time, or None if read failed or RTC unavailable
        """
        # Skip if RTC is not available
        if not self.rtc_available:
            return None
        
        # Try I2C method first (preferred for DS3231)
        if self.rtc_method == 'i2c' and RTC_MODULE_AVAILABLE:
            try:
                rtc = get_rtc()
                if rtc.is_available():
                    rtc_time = rtc.get_time()
                    # Verify we got actual RTC time, not fallback
                    if rtc._available:
                        return rtc_time
            except Exception as e:
                self.logger.debug(f"I2C RTC read failed: {e}")
        
        # Fallback to hwclock
        if self.rtc_method == 'hwclock' or (self.rtc_method == 'i2c' and not RTC_MODULE_AVAILABLE):
            return self._get_rtc_time_hwclock()
        
        return None
    
    def _get_rtc_time_hwclock(self):
        """
        Read RTC time using hwclock command (fallback method).
        
        Returns:
            datetime: RTC time, or None if read failed
        """
        try:
            result = subprocess.run(
                ['sudo', 'hwclock', '-r'], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode != 0:
                self.logger.error(f"hwclock returned error: {result.stderr}")
                return None
            
            # Parse output - format varies by system
            # Common formats:
            #   "2026-01-25 14:30:15.123456+00:00"
            #   "Sat 25 Jan 2026 02:30:15 PM UTC  .123456 seconds"
            rtc_str = result.stdout.strip()
            
            # Try ISO format first
            try:
                # Remove timezone and microseconds for parsing
                clean_str = rtc_str.split('.')[0].split('+')[0].strip()
                return datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
            
            # Try alternate format (hwclock verbose)
            try:
                # Extract date/time components
                import re
                match = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})', rtc_str)
                if match:
                    return datetime(
                        int(match.group(1)), int(match.group(2)), int(match.group(3)),
                        int(match.group(4)), int(match.group(5)), int(match.group(6))
                    )
            except:
                pass
            
            self.logger.error(f"Could not parse RTC output: {rtc_str}")
            return None
            
        except subprocess.TimeoutExpired:
            self.logger.error("hwclock command timed out")
            return None
        except FileNotFoundError:
            self.logger.error("hwclock command not found")
            return None
        except Exception as e:
            self.logger.error(f"RTC read failed: {e}")
            return None
            return None
    
    def set_system_time(self, dt):
        """
        Set system time from datetime object using hwclock.
        
        Args:
            dt: datetime object to set as system time
            
        Returns:
            bool: True if successful
        """
        try:
            # First set system time
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Use date command to set system time
            subprocess.run(
                ['sudo', 'date', '-s', time_str],
                check=True, 
                timeout=5,
                capture_output=True
            )
            
            self.logger.info(f"System time set to: {time_str}")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to set system time: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to set system time: {e}")
            return False
    
    def sync_system_to_rtc(self):
        """
        Sync system time from RTC using hwclock --hctosys.
        
        Returns:
            bool: True if successful
        """
        try:
            subprocess.run(
                ['sudo', 'hwclock', '--hctosys'],
                check=True, 
                timeout=5,
                capture_output=True
            )
            self.logger.info("System time synced from RTC")
            return True
        except Exception as e:
            self.logger.error(f"Failed to sync from RTC: {e}")
            return False
    
    def validate_and_correct(self, event_logger_callback=None):
        """
        Main validation routine - call on boot and periodically.
        
        Checks:
        1. RTC battery failure (year < 2024)
        2. System vs RTC offset on boot
        3. Boot gap detection (time since last shutdown)
        
        Args:
            event_logger_callback: Optional callback(event_dict) for logging
            
        Returns:
            tuple: (is_valid: bool, events: list of event dicts)
        """
        events = []
        
        # If RTC is not available, skip RTC validation entirely
        if not self.rtc_available:
            self.logger.debug("RTC not available - skipping RTC validation")
            # Still update last known good time from system clock
            self.state["last_known_good_time"] = datetime.now().isoformat()
            self._save_state()
            return True, events  # Return success with no events
        
        rtc_now = self.get_rtc_time()
        
        if rtc_now is None:
            self.logger.error("RTC unavailable - cannot validate time")
            events.append({
                "type": "RTC_UNAVAILABLE",
                "timestamp": datetime.now().isoformat(),
                "warning": "Hardware RTC could not be read"
            })
            return False, events
        
        system_now = datetime.now()
        
        # ===== Check 1: RTC Battery Failure (year < 2024) =====
        if rtc_now.year < 2024:
            self.state["rtc_battery_ok"] = False
            events.append({
                "type": "RTC_BATTERY_FAIL",
                "rtc_reading": rtc_now.isoformat(),
                "rtc_year": rtc_now.year,
                "action": "restoring_last_known_good"
            })
            self.logger.warning(f"RTC battery failure detected: year={rtc_now.year}")
            
            # Restore from last known good time
            if self.state["last_known_good_time"]:
                try:
                    last_good = datetime.fromisoformat(self.state["last_known_good_time"])
                    # Add elapsed time estimate (assume minimal drift)
                    # Use last_good as base, system uptime could help but not reliable
                    restored_time = last_good
                    
                    self.set_system_time(restored_time)
                    events.append({
                        "type": "TIME_RESTORED",
                        "restored_to": self.state["last_known_good_time"],
                        "source": "state_file"
                    })
                    self.logger.info(f"Time restored from state file: {self.state['last_known_good_time']}")
                except Exception as e:
                    self.logger.error(f"Failed to restore time: {e}")
            else:
                events.append({
                    "type": "NO_LAST_GOOD_TIME",
                    "warning": "RTC failed but no state history available",
                    "action": "manual_time_set_required"
                })
                self.logger.error("RTC failed and no last known good time available!")
                
            self._save_state()
            return False, events
        
        # ===== RTC is valid (year >= 2024) =====
        self.state["rtc_battery_ok"] = True
        
        # ===== Check 2: System vs RTC offset on boot =====
        offset = abs((system_now - rtc_now).total_seconds())
        
        if offset > 1:  # > 1 second difference
            events.append({
                "type": "TIME_CORRECTION",
                "system_was": system_now.isoformat(),
                "rtc_is": rtc_now.isoformat(),
                "offset_sec": round(offset, 2),
                "action": "correcting_to_rtc"
            })
            self.logger.info(f"Time correction needed: offset={offset:.2f}s")
            self.sync_system_to_rtc()
        
        # ===== Check 3: Boot gap detection =====
        if self.state["last_known_good_time"]:
            try:
                last_good = datetime.fromisoformat(self.state["last_known_good_time"])
                gap = (rtc_now - last_good).total_seconds()
                
                if gap > 60:  # > 1 minute gap
                    gap_minutes = round(gap / 60, 1)
                    gap_hours = round(gap / 3600, 2)
                    
                    events.append({
                        "type": "BOOT",
                        "resumed_after_seconds": round(gap, 0),
                        "resumed_after_minutes": gap_minutes,
                        "resumed_after_hours": gap_hours if gap_hours >= 1 else None,
                        "last_seen": self.state["last_known_good_time"],
                        "now": rtc_now.isoformat()
                    })
                    self.logger.info(f"Boot detected: {gap_minutes} minutes since last run")
                    
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Could not calculate boot gap: {e}")
        
        # ===== Update state with current valid time =====
        self.state["last_known_good_time"] = rtc_now.isoformat()
        self.state["last_boot_time"] = rtc_now.isoformat()
        self._save_state()
        self.last_rtc_check = rtc_now
        
        return True, events
    
    def check_drift(self, event_logger_callback=None):
        """
        Runtime drift check - call every minute or every CSV cycle.
        
        Detects if system time has drifted > 1 minute from RTC.
        
        Returns:
            dict: Event dict if drift > 1 minute detected, else None
        """
        # Skip if RTC is not available
        if not self.rtc_available:
            # Still update last known good time from system clock
            self.state["last_known_good_time"] = datetime.now().isoformat()
            self._save_state()
            return None
        
        if not self.state.get("rtc_battery_ok", True):
            return None  # Don't check if battery known bad
        
        rtc_now = self.get_rtc_time()
        if rtc_now is None:
            return None
        
        system_now = datetime.now()
        drift = abs((system_now - rtc_now).total_seconds())
        
        if drift > 60:  # > 1 minute drift
            event = {
                "type": "TIME_DRIFT_DETECTED",
                "drift_seconds": round(drift, 2),
                "system_time": system_now.isoformat(),
                "rtc_time": rtc_now.isoformat(),
                "action": "correcting_to_rtc"
            }
            self.logger.warning(f"Time drift detected: {drift:.2f}s, correcting")
            self.sync_system_to_rtc()
            
            # Update state
            self.state["last_known_good_time"] = rtc_now.isoformat()
            self._save_state()
            
            return event
        
        # Update last known good time even if no drift
        self.state["last_known_good_time"] = system_now.isoformat()
        self._save_state()
        
        return None
    
    def check_discontinuity(self, current_timestamp_str, last_timestamp_str):
        """
        Check for time jumps between readings (> 1 hour).
        
        Args:
            current_timestamp_str: Current reading timestamp (YYYY-MM-DD HH:MM:SS)
            last_timestamp_str: Previous reading timestamp
            
        Returns:
            dict: Event dict if jump > 1 hour detected, else None
        """
        if not last_timestamp_str or not current_timestamp_str:
            return None
        
        try:
            current = datetime.strptime(current_timestamp_str, "%Y-%m-%d %H:%M:%S")
            last = datetime.strptime(last_timestamp_str, "%Y-%m-%d %H:%M:%S")
            
            # Calculate absolute difference (handles both forward and backward jumps)
            diff = (current - last).total_seconds()
            abs_diff = abs(diff)
            
            if abs_diff > 3600:  # > 1 hour
                direction = "forward" if diff > 0 else "backward"
                hours = round(abs_diff / 3600, 2)
                
                return {
                    "type": "TIME_JUMP",
                    "direction": direction,
                    "hours": hours,
                    "seconds": round(abs_diff, 0),
                    "from": last_timestamp_str,
                    "to": current_timestamp_str
                }
        except (ValueError, TypeError) as e:
            self.logger.debug(f"Could not parse timestamps for discontinuity check: {e}")
        
        return None
    
    def is_timestamp_sane(self, timestamp_str):
        """
        Quick sanity check for a timestamp string.
        
        Args:
            timestamp_str: Timestamp to validate (YYYY-MM-DD HH:MM:SS)
            
        Returns:
            tuple: (is_sane: bool, reason: str or None)
        """
        try:
            ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            
            # Check 1: Not in the past (> 7 days ago)
            if ts < now - timedelta(days=7):
                return False, f"timestamp_too_old_{ts.isoformat()}"
            
            # Check 2: Not in the future (> 1 day ahead)
            if ts > now + timedelta(days=1):
                return False, f"timestamp_in_future_{ts.isoformat()}"
            
            # Check 3: Year sanity (>= 2024)
            if ts.year < 2024:
                return False, f"year_before_2024_{ts.year}"
            
            return True, None
            
        except (ValueError, TypeError):
            return False, "invalid_format"
    
    def get_status(self):
        """
        Get current time sanitizer status for diagnostics.
        
        Returns:
            dict: Status information
        """
        system_now = datetime.now()
        
        # Only read RTC if available
        rtc_now = self.get_rtc_time() if self.rtc_available else None
        
        return {
            "rtc_available": self.rtc_available,
            "rtc_method": self.rtc_method,
            "rtc_time": rtc_now.isoformat() if rtc_now else None,
            "system_time": system_now.isoformat(),
            "rtc_battery_ok": self.state.get("rtc_battery_ok", True),
            "last_known_good_time": self.state.get("last_known_good_time"),
            "drift_seconds": abs((system_now - rtc_now).total_seconds()) if rtc_now else None,
            "state_file": str(self.state_file)
        }
