#!/usr/bin/env python3
"""Set DS3231 RTC from current system time.

Run with sudo to allow I2C access and to write the RTC.
"""
from datetime import datetime
import sys
import traceback
try:
    from smbus2 import SMBus
except Exception:
    try:
        from smbus import SMBus
    except Exception:
        SMBus = None

def dec_to_bcd(n):
    return ((n // 10) << 4) | (n % 10)

def main():
    try:
        from rtc_module import get_rtc
    except ImportError:
        print("rtc_module not found. Please ensure src/utils/rtc_module.py exists.")
        sys.exit(2)
    now = datetime.now()
    rtc = get_rtc()
    if rtc.is_available():
        success = rtc.set_time(now)
        if success:
            print(f"RTC updated with system time: {now.isoformat(sep=' ')}")
            sys.exit(0)
        else:
            print("Failed to write RTC.")
            sys.exit(1)
    else:
        print("RTC not available. Check hardware and I2C connection.")
        sys.exit(3)

if __name__ == '__main__':
    main()
