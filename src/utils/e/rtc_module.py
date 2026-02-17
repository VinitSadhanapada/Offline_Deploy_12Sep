"""
RTC Module — DS3231 Real-Time Clock
====================================
Supports TWO modes automatically:

  1. KERNEL MODE (preferred): When dtoverlay=i2c-rtc,ds3231 is set,
     the kernel claims the device (i2cdetect shows UU at 0x68).
     Uses hwclock / /dev/rtc0 to read/write.

  2. DIRECT I2C MODE (fallback): When no kernel driver is loaded,
     uses smbus to talk directly to DS3231 at 0x68.

The module auto-detects which mode to use.

Usage:
    from rtc_module import get_rtc, is_rtc_available
    rtc = get_rtc()
    if rtc.is_available():
        print(rtc.get_time())       # Read RTC
        rtc.set_time(datetime.now()) # Write RTC
"""

import os
import re
import time
import logging
import subprocess
from datetime import datetime
from typing import Optional

logger = logging.getLogger("rtc_module")

# Try smbus for direct I2C mode
SMBus = None
try:
    from smbus2 import SMBus as _SMBus
    SMBus = _SMBus
except ImportError:
    try:
        from smbus import SMBus as _SMBus
        SMBus = _SMBus
    except ImportError:
        pass


def _find_hwclock():
    """Find hwclock binary path."""
    for path in ['/sbin/hwclock', '/usr/sbin/hwclock', '/bin/hwclock', '/usr/bin/hwclock']:
        if os.path.isfile(path):
            return path
    # Try which
    try:
        result = subprocess.run(['which', 'hwclock'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


class DS3231:
    """
    DS3231 RTC interface with auto-detection of kernel vs direct I2C mode.
    """

    # DS3231 I2C registers (for direct mode)
    REG_SECONDS = 0x00
    REG_MINUTES = 0x01
    REG_HOURS   = 0x02
    REG_DAY_OF_WEEK = 0x03
    REG_DATE    = 0x04
    REG_MONTH   = 0x05
    REG_YEAR    = 0x06
    REG_TEMP_MSB = 0x11
    REG_STATUS  = 0x0F

    def __init__(self, i2c_bus: int = 1, i2c_address: int = 0x68,
                 fallback_to_system: bool = True, max_retries: int = 3):
        self._bus_num = i2c_bus
        self._address = i2c_address
        self._fallback = fallback_to_system
        self._max_retries = max_retries
        self._bus = None
        self._available = False
        self._mode = None  # 'kernel' or 'i2c'
        self._hwclock_path = None

        self._detect_mode()

    def _detect_mode(self):
        """Auto-detect whether to use kernel driver (hwclock) or direct I2C."""

        # ── Check 1: Does /dev/rtc0 exist? (kernel driver loaded) ──
        if os.path.exists('/dev/rtc0'):
            self._hwclock_path = _find_hwclock()
            if self._hwclock_path:
                # Verify hwclock can actually read
                try:
                    result = subprocess.run(
                        ['sudo', self._hwclock_path, '-r'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        self._mode = 'kernel'
                        self._available = True
                        logger.info(f"DS3231 RTC: kernel mode via {self._hwclock_path}")
                        return
                except Exception as e:
                    logger.debug(f"hwclock test failed: {e}")

            # /dev/rtc0 exists but no hwclock — try reading rtc0 directly
            try:
                with open('/sys/class/rtc/rtc0/time', 'r') as f:
                    f.read()
                with open('/sys/class/rtc/rtc0/date', 'r') as f:
                    f.read()
                self._mode = 'sysfs'
                self._available = True
                logger.info("DS3231 RTC: sysfs mode via /sys/class/rtc/rtc0/")
                return
            except Exception:
                pass

        # ── Check 2: Direct I2C (no kernel driver) ──
        if SMBus is not None:
            try:
                self._bus = SMBus(self._bus_num)
                self._i2c_read(self.REG_SECONDS, 1)
                self._mode = 'i2c'
                self._available = True
                logger.info(f"DS3231 RTC: direct I2C mode on bus {self._bus_num}")
                return
            except FileNotFoundError:
                logger.warning(f"I2C bus {self._bus_num} not found")
                self._bus = None
            except OSError as e:
                # OSError with errno 16 = device busy (kernel has it)
                if "Resource busy" in str(e) or getattr(e, 'errno', 0) == 16:
                    logger.debug("I2C device busy (kernel driver has it)")
                else:
                    logger.warning(f"DS3231 not responding: {e}")
                self._bus = None

        logger.warning("DS3231 RTC: not available (no kernel driver, no direct I2C)")

    # ── I2C helpers (for direct mode) ──────────────────────────────

    def _i2c_read(self, register: int, length: int) -> list:
        """Read I2C with retries."""
        last_error = None
        for attempt in range(self._max_retries):
            try:
                return self._bus.read_i2c_block_data(self._address, register, length)
            except OSError as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    time.sleep(0.05 * (attempt + 1))
        raise last_error

    def _i2c_write(self, register: int, data: list) -> None:
        """Write I2C with retries."""
        last_error = None
        for attempt in range(self._max_retries):
            try:
                self._bus.write_i2c_block_data(self._address, register, data)
                return
            except OSError as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    time.sleep(0.05 * (attempt + 1))
        raise last_error

    @staticmethod
    def _bcd_to_int(bcd: int) -> int:
        return (bcd & 0x0F) + ((bcd >> 4) * 10)

    @staticmethod
    def _int_to_bcd(value: int) -> int:
        return (value % 10) | ((value // 10) << 4)

    # ── Public API ─────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if RTC is available and responding."""
        if not self._available:
            return False

        if self._mode == 'kernel':
            return os.path.exists('/dev/rtc0')
        elif self._mode == 'sysfs':
            return os.path.exists('/sys/class/rtc/rtc0/time')
        elif self._mode == 'i2c':
            try:
                self._i2c_read(self.REG_SECONDS, 1)
                return True
            except OSError:
                self._available = False
                return False
        return False

    def get_time(self) -> datetime:
        """
        Read current time from DS3231.

        Returns datetime from RTC. Falls back to system time if enabled.
        """
        if not self._available:
            if self._fallback:
                return datetime.now()
            raise RuntimeError("DS3231 RTC not available")

        try:
            if self._mode == 'kernel':
                return self._get_time_hwclock()
            elif self._mode == 'sysfs':
                return self._get_time_sysfs()
            elif self._mode == 'i2c':
                return self._get_time_i2c()
        except Exception as e:
            logger.error(f"RTC read failed ({self._mode}): {e}")
            if self._fallback:
                return datetime.now()
            raise RuntimeError(f"Failed to read DS3231: {e}")

        if self._fallback:
            return datetime.now()
        raise RuntimeError("No RTC read method available")

    def set_time(self, dt: datetime) -> bool:
        """
        Write time to DS3231 RTC.

        Returns True if successful.
        """
        if not self._available:
            logger.error("Cannot set time — RTC not available")
            return False

        try:
            if self._mode == 'kernel':
                return self._set_time_hwclock(dt)
            elif self._mode == 'sysfs':
                # sysfs is read-only — try hwclock or fail
                return self._set_time_hwclock(dt)
            elif self._mode == 'i2c':
                return self._set_time_i2c(dt)
        except Exception as e:
            logger.error(f"RTC write failed ({self._mode}): {e}")
            return False

        return False

    # ── Kernel mode (hwclock) ──────────────────────────────────────

    def _get_time_hwclock(self) -> datetime:
        """Read RTC via hwclock."""
        result = subprocess.run(
            ['sudo', self._hwclock_path, '-r'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            raise RuntimeError(f"hwclock -r failed: {result.stderr.strip()}")

        # Parse hwclock output — varies by version:
        #   "2026-02-17 14:30:00.123456+05:30"
        #   "Mon 17 Feb 2026 02:30:00 PM IST  .123456 seconds"
        output = result.stdout.strip()
        return self._parse_hwclock_output(output)

    def _parse_hwclock_output(self, output: str) -> datetime:
        """Parse various hwclock output formats."""
        # Try ISO-like format first: "2026-02-17 14:30:00.123456+05:30"
        match = re.match(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', output)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")

        # Try verbose format: "Mon 17 Feb 2026 02:30:00 PM IST"
        # Strip fractional seconds info at the end
        clean = re.sub(r'\.\d+\s+seconds?\s*$', '', output).strip()
        for fmt in [
            "%a %d %b %Y %I:%M:%S %p %Z",
            "%a %d %b %Y %H:%M:%S %Z",
            "%a %b %d %H:%M:%S %Y",
            "%Y-%m-%d %H:%M:%S.%f%z",
        ]:
            try:
                return datetime.strptime(clean, fmt)
            except ValueError:
                continue
        
        raise RuntimeError(f"Cannot parse hwclock output: '{output}'")

    def _set_time_hwclock(self, dt: datetime) -> bool:
        """Write time to RTC via hwclock."""
        hwclock = self._hwclock_path or _find_hwclock()
        if not hwclock:
            logger.error("hwclock not found — install: sudo apt install util-linux")
            return False

        # First set system time, then write to RTC
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        try:
            # Set system time first
            subprocess.run(
                ['sudo', 'date', '-s', time_str],
                capture_output=True, timeout=5
            )
            # Write system time → RTC
            result = subprocess.run(
                ['sudo', hwclock, '-w'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                logger.info(f"RTC set via hwclock: {time_str}")
                return True
            else:
                logger.error(f"hwclock -w failed: {result.stderr.strip()}")
                return False
        except Exception as e:
            logger.error(f"hwclock set failed: {e}")
            return False

    # ── Sysfs mode ─────────────────────────────────────────────────

    def _get_time_sysfs(self) -> datetime:
        """Read RTC via /sys/class/rtc/rtc0/."""
        with open('/sys/class/rtc/rtc0/date', 'r') as f:
            date_str = f.read().strip()  # "2026-02-17"
        with open('/sys/class/rtc/rtc0/time', 'r') as f:
            time_str = f.read().strip()  # "14:30:00"
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")

    # ── Direct I2C mode ────────────────────────────────────────────

    def _get_time_i2c(self) -> datetime:
        """Read RTC via direct I2C/smbus."""
        data = self._i2c_read(self.REG_SECONDS, 7)

        seconds = self._bcd_to_int(data[0] & 0x7F)
        minutes = self._bcd_to_int(data[1])

        hours_reg = data[2]
        if hours_reg & 0x40:  # 12-hour mode
            hours = self._bcd_to_int(hours_reg & 0x1F)
            if hours_reg & 0x20:  # PM
                if hours != 12:
                    hours += 12
            else:
                if hours == 12:
                    hours = 0
        else:
            hours = self._bcd_to_int(hours_reg & 0x3F)

        day   = self._bcd_to_int(data[4])
        month = self._bcd_to_int(data[5] & 0x1F)
        century = 1 if (data[5] & 0x80) else 0
        year  = self._bcd_to_int(data[6]) + 2000 + (century * 100)

        return datetime(year, month, day, hours, minutes, seconds)

    def _set_time_i2c(self, dt: datetime) -> bool:
        """Write time via direct I2C/smbus."""
        data = [
            self._int_to_bcd(dt.second),
            self._int_to_bcd(dt.minute),
            self._int_to_bcd(dt.hour),
            dt.isoweekday(),
            self._int_to_bcd(dt.day),
            self._int_to_bcd(dt.month),
            self._int_to_bcd(dt.year % 100),
        ]
        if dt.year >= 2100:
            data[5] |= 0x80

        self._i2c_write(self.REG_SECONDS, data)
        logger.info(f"RTC set via I2C: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        return True

    # ── Diagnostics ────────────────────────────────────────────────

    def get_temperature(self) -> Optional[float]:
        """Read DS3231 temperature (only in direct I2C mode)."""
        if self._mode != 'i2c' or not self._available:
            return None
        try:
            data = self._i2c_read(self.REG_TEMP_MSB, 2)
            temp = data[0]
            if temp & 0x80:
                temp -= 256
            temp += (data[1] >> 6) * 0.25
            return temp
        except OSError:
            return None

    def check_oscillator_stopped(self) -> Optional[bool]:
        """Check OSF flag (only in direct I2C mode)."""
        if self._mode != 'i2c' or not self._available:
            return None
        try:
            data = self._i2c_read(self.REG_STATUS, 1)
            return bool(data[0] & 0x80)
        except OSError:
            return None

    def clear_oscillator_flag(self) -> bool:
        """Clear OSF flag (only in direct I2C mode)."""
        if self._mode != 'i2c' or not self._available:
            return False
        try:
            data = self._i2c_read(self.REG_STATUS, 1)
            data[0] &= 0x7F
            self._i2c_write(self.REG_STATUS, [data[0]])
            return True
        except OSError:
            return False

    def sync_system_clock(self) -> bool:
        """Set Linux system time from RTC."""
        rtc_time = self.get_time()
        if not self._available:
            return False
        try:
            time_str = rtc_time.strftime("%Y-%m-%d %H:%M:%S")
            result = subprocess.run(
                ['sudo', 'date', '-s', time_str],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                logger.info(f"System clock set from RTC: {time_str}")
                return True
            return False
        except Exception as e:
            logger.error(f"sync failed: {e}")
            return False

    def get_mode(self) -> str:
        """Return current access mode: 'kernel', 'sysfs', 'i2c', or 'none'."""
        return self._mode or 'none'

    def close(self) -> None:
        if self._bus:
            try:
                self._bus.close()
            except Exception:
                pass
            self._bus = None
            self._available = False


# ── Singleton ──────────────────────────────────────────────────────

_rtc_instance: Optional[DS3231] = None


def get_rtc(i2c_bus: int = 1, i2c_address: int = 0x68,
            fallback_to_system: bool = True) -> DS3231:
    """Get or create singleton DS3231 instance."""
    global _rtc_instance
    if _rtc_instance is None:
        _rtc_instance = DS3231(i2c_bus, i2c_address, fallback_to_system)
    return _rtc_instance


def get_rtc_time() -> datetime:
    return get_rtc().get_time()


def is_rtc_available() -> bool:
    return get_rtc().is_available()
