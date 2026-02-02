"""
RTC Module
==========
Interface for DS3231 Real-Time Clock module via I2C.
Provides accurate time reading with fallback to system time.
"""

import os
from datetime import datetime
from typing import Optional

# Simple logger replacement for now
def get_logger():
    class Logger:
        def info(self, msg): print(f"[INFO] {msg}")
        def warning(self, msg): print(f"[WARN] {msg}")
        def error(self, msg): print(f"[ERROR] {msg}")
        def debug(self, msg): print(f"[DEBUG] {msg}")
    return Logger()

def log_error(context, exc, msg):
    print(f"[ERROR] {context}: {msg}: {exc}")

# Try to import smbus2 for I2C communication
try:
    import smbus2
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False

class DS3231:
    REG_SECONDS = 0x00
    REG_MINUTES = 0x01
    REG_HOURS = 0x02
    REG_DAY = 0x03
    REG_DATE = 0x04
    REG_MONTH = 0x05
    REG_YEAR = 0x06

    def __init__(self, i2c_bus: int = 1, i2c_address: int = 0x68, fallback_to_system: bool = True):
        self._bus_num = i2c_bus
        self._address = i2c_address
        self._fallback = fallback_to_system
        self._bus: Optional["smbus2.SMBus"] = None
        self._available = False
        self._init_i2c()

    def _init_i2c(self) -> None:
        logger = get_logger()
        if not SMBUS_AVAILABLE:
            logger.warning("smbus2 not available - RTC will use system time fallback")
            return
        try:
            self._bus = smbus2.SMBus(self._bus_num)
            self._bus.read_byte_data(self._address, self.REG_SECONDS)
            self._available = True
            logger.info(f"DS3231 RTC initialized on I2C bus {self._bus_num}, address 0x{self._address:02X}")
        except FileNotFoundError:
            logger.warning(f"I2C bus {self._bus_num} not found - RTC will use system time fallback")
            self._bus = None
        except OSError as e:
            logger.warning(f"Could not connect to DS3231: {e} - RTC will use system time fallback")
            self._bus = None

    def _bcd_to_int(self, bcd: int) -> int:
        return (bcd & 0x0F) + ((bcd >> 4) * 10)

    def _int_to_bcd(self, value: int) -> int:
        return (value % 10) | ((value // 10) << 4)

    def is_available(self) -> bool:
        if not self._available or self._bus is None:
            return False
        try:
            self._bus.read_byte_data(self._address, self.REG_SECONDS)
            return True
        except OSError:
            self._available = False
            return False

    def get_time(self) -> datetime:
        logger = get_logger()
        if not self._available or self._bus is None:
            if self._fallback:
                logger.debug("RTC unavailable, using system time")
                return datetime.now()
            else:
                raise RuntimeError("DS3231 RTC not available and fallback disabled")
        try:
            data = self._bus.read_i2c_block_data(self._address, self.REG_SECONDS, 7)
            seconds = self._bcd_to_int(data[0] & 0x7F)
            minutes = self._bcd_to_int(data[1])
            hours_reg = data[2]
            if hours_reg & 0x40:
                hours = self._bcd_to_int(hours_reg & 0x1F)
                if hours_reg & 0x20:
                    hours = (hours % 12) + 12
            else:
                hours = self._bcd_to_int(hours_reg & 0x3F)
            day = self._bcd_to_int(data[4])
            month_reg = data[5]
            month = self._bcd_to_int(month_reg & 0x1F)
            century = 1 if (month_reg & 0x80) else 0
            year = self._bcd_to_int(data[6]) + 2000 + (century * 100)
            return datetime(year, month, day, hours, minutes, seconds)
        except OSError as e:
            log_error("RTC", e, "Error reading time from DS3231")
            if self._fallback:
                logger.warning("RTC read failed, using system time")
                return datetime.now()
            else:
                raise RuntimeError(f"Failed to read DS3231 time: {e}")

    def set_time(self, dt: datetime) -> bool:
        logger = get_logger()
        if not self._available or self._bus is None:
            logger.error("Cannot set time - RTC not available")
            return False
        try:
            seconds = self._int_to_bcd(dt.second)
            minutes = self._int_to_bcd(dt.minute)
            hours = self._int_to_bcd(dt.hour)
            day_of_week = dt.weekday() + 1
            day = self._int_to_bcd(dt.day)
            month = self._int_to_bcd(dt.month)
            year = self._int_to_bcd(dt.year % 100)
            if dt.year >= 2100:
                month |= 0x80
            data = [seconds, minutes, hours, day_of_week, day, month, year]
            self._bus.write_i2c_block_data(self._address, self.REG_SECONDS, data)
            logger.info(f"RTC time set to {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            return True
        except OSError as e:
            log_error("RTC", e, "Error setting time on DS3231")
            return False

    def sync_system_clock(self) -> bool:
        logger = get_logger()
        rtc_time = self.get_time()
        if not self._available:
            logger.warning("Cannot sync - using fallback system time")
            return False
        try:
            time_str = rtc_time.strftime("%Y-%m-%d %H:%M:%S")
            result = os.system(f'sudo date -s "{time_str}"')
            if result == 0:
                logger.info(f"System clock synced to RTC: {time_str}")
                return True
            else:
                logger.error("Failed to set system time (may need root)")
                return False
        except Exception as e:
            log_error("RTC", e, "Error syncing system clock")
            return False

    def close(self) -> None:
        if self._bus:
            self._bus.close()
            self._bus = None
            self._available = False

_rtc_instance: Optional[DS3231] = None

def get_rtc(i2c_bus: int = 1, i2c_address: int = 0x68, fallback_to_system: bool = True) -> DS3231:
    global _rtc_instance
    if _rtc_instance is None:
        _rtc_instance = DS3231(i2c_bus, i2c_address, fallback_to_system)
    return _rtc_instance

def get_rtc_time() -> datetime:
    return get_rtc().get_time()

def is_rtc_available() -> bool:
    return get_rtc().is_available()
