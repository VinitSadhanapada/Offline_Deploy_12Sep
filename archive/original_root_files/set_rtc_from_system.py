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
    if SMBus is None:
        print("smbus2/smbus not installed. Install with: sudo apt install python3-smbus or pip3 install smbus2")
        sys.exit(2)
    now = datetime.now()
    try:
        with SMBus(1) as bus:
            addr = 0x68
            data = [
                dec_to_bcd(now.second),
                dec_to_bcd(now.minute),
                dec_to_bcd(now.hour),
                1,  # day of week (1-7)
                dec_to_bcd(now.day),
                dec_to_bcd(now.month),
                dec_to_bcd(now.year - 2000)
            ]
            bus.write_i2c_block_data(addr, 0x00, data)
        print(f"RTC updated with system time: {now.isoformat(sep=' ')}")
    except FileNotFoundError as e:
        print(f"I2C device not found: {e}")
        sys.exit(3)
    except Exception:
        print("Failed to write RTC:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
