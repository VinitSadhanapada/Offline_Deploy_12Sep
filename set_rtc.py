#!/usr/bin/env python3
"""
Set DS3231 RTC from current system time.

Usage:
    sudo python3 set_rtc.py

Run this AFTER you've set the correct system time (e.g. via NTP).
The fix_time.sh script does this automatically.
"""
import sys
from datetime import datetime

# Try both import paths
try:
    from src.utils.rtc_module import get_rtc
except ImportError:
    try:
        from rtc_module import get_rtc
    except ImportError:
        print("ERROR: rtc_module.py not found.")
        print("Ensure rtc_module.py is in the same directory or at src/utils/rtc_module.py")
        sys.exit(2)


def main():
    rtc = get_rtc(fallback_to_system=False)
    
    if not rtc.is_available():
        print("ERROR: DS3231 RTC not detected on I2C bus.")
        print("  Check wiring: VCC→3.3V, GND→GND, SDA→GPIO2, SCL→GPIO3")
        print("  Check I2C enabled: sudo raspi-config → Interface Options → I2C")
        print("  Check detection: sudo i2cdetect -y 1  (should show 68 or UU)")
        sys.exit(3)
    
    # Read current RTC time for comparison
    try:
        rtc_before = rtc.get_time()
        print(f"Current RTC time:    {rtc_before.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception:
        print("Current RTC time:    (could not read)")
    
    # Write system time to RTC
    now = datetime.now()
    print(f"Current system time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = rtc.set_time(now)
    
    if not success:
        print("ERROR: Failed to write time to RTC.")
        sys.exit(1)
    
    # Verify by reading back
    try:
        rtc_after = rtc.get_time()
        diff = abs((rtc_after - now).total_seconds())
        print(f"RTC after write:     {rtc_after.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if diff < 2:
            print("✓ RTC updated successfully!")
        else:
            print(f"⚠ RTC written but verification shows {diff:.0f}s difference")
    except Exception:
        print("✓ RTC written (could not verify read-back)")
    
    # Clear oscillator stop flag
    rtc.clear_oscillator_flag()
    
    sys.exit(0)


if __name__ == '__main__':
    main()
