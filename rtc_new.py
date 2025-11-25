#!/usr/bin/env python3
from smbus2 import SMBus
from datetime import datetime, timezone
import subprocess
import sys



def bcd_to_dec(bcd):
    return (bcd >> 4) * 10 + (bcd & 0x0F)

def dec_to_bcd(dec):
    return ((dec // 10) << 4) + (dec % 10)

def read_rtc_time():
    """Read time from RTC and return as datetime object"""
    addr = 0x68
    try:
        with SMBus(1) as bus:
            data = bus.read_i2c_block_data(addr, 0x00, 7)
            seconds = bcd_to_dec(data[0] & 0x7F)
            minutes = bcd_to_dec(data[1])
            hours = bcd_to_dec(data[2] & 0x3F)
            day = bcd_to_dec(data[4])
            month = bcd_to_dec(data[5] & 0x1F)
            year = bcd_to_dec(data[6]) + 2000
            return datetime(year, month, day, hours, minutes, seconds)
    except Exception as e:
        print(f"Error reading RTC: {e}")
        return None

def write_rtc_time(dt):
    """Write datetime to RTC"""
    print(f"🔧 Attempting to write time to RTC: {dt}")
    addr = 0x68
    try:
        with SMBus(1) as bus:
            data = [
                dec_to_bcd(dt.second),
                dec_to_bcd(dt.minute),
                dec_to_bcd(dt.hour),
                dec_to_bcd(dt.weekday() + 1),  # RTC weekday: 1=Monday
                dec_to_bcd(dt.day),
                dec_to_bcd(dt.month),
                dec_to_bcd(dt.year - 2000)
            ]
            print(f"🔍 Data to write: {[hex(x) for x in data]}")
            bus.write_i2c_block_data(addr, 0x00, data)
            print(f"✅ Time written to RTC: {dt}")
            import time
            time.sleep(0.1)
            verify_data = bus.read_i2c_block_data(addr, 0x00, 7)
            print(f"🔍 Verification read: {[hex(x) for x in verify_data]}")
            return True
    except Exception as e:
        print(f"Error writing to RTC: {e}")
        return False
def main():
    print(f"🔍 DEBUG: Command line arguments: {sys.argv}")
    print(f"🔍 DEBUG: Number of arguments: {len(sys.argv)}")
    
    if len(sys.argv) > 1:
        print(f"🔍 DEBUG: First argument: '{sys.argv[1]}'")
        if sys.argv[1] == "--set-rtc" or sys.argv[1] == "--set_rtc":
            print("🔧 Setting RTC to current system time...")
            current_time = datetime.now()
            if write_rtc_time(current_time):
                print("✅ RTC updated with system time")
            else:
                print("❌ Failed to update RTC")
            return
        elif sys.argv[1] == "--set-time" and len(sys.argv) > 2:
            try:
                new_time = datetime.strptime(sys.argv[2], "%Y-%m-%d %H:%M:%S")
                if write_rtc_time(new_time):
                    print(f"RTC updated to: {new_time}")
                    subprocess.run(["sudo", "date", "-s", sys.argv[2]])
                    print(f"System time also updated to: {new_time}")
                else:
                    print("Failed to update RTC")
                return
            except ValueError:
                print("Invalid time format. Use: YYYY-MM-DD HH:MM:SS")
                print("Example: python3 rtc_new.py --set-time '2025-07-28 14:30:00'")
                return
        elif sys.argv[1] == "--help":
            print("RTC Time Manager")
            print("Usage:")
            print("  python3 rtc_new.py                    # Read RTC and sync system time")
            print("  python3 rtc_new.py --set-rtc          # Set RTC to current system time (requires RTC hardware)")
            print("  python3 rtc_new.py --set-time 'YYYY-MM-DD HH:MM:SS'  # Set both RTC and system to specific time (requires RTC hardware)")
            print("  python3 rtc_new.py --help             # Show this help")
            return
        else:
            print(f"🔍 DEBUG: Unknown argument: '{sys.argv[1]}'")
            print("   Falling back to default behavior...")
    else:
        print("🔍 DEBUG: No arguments provided, using default behavior...")
    
    # Read RTC and set system time
    rtc_time = read_rtc_time()
    if rtc_time is None:
        print("❌ Failed to read RTC time")
        sys.exit(1)
    
    current_system_time = datetime.now()
    print(f"📅 RTC Time: {rtc_time}")
    print(f"🖥️ System Time: {current_system_time}")
    
    # Check time difference
    time_diff = abs((rtc_time - current_system_time).total_seconds())
    print(f"⏱️ Time difference: {time_diff:.1f} seconds")
    
    if time_diff > 2:  # Only update if difference > 2 seconds
        # Format for date command (using local timezone)
        datetime_str = rtc_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Set system time
        result = subprocess.run(["sudo", "date", "-s", datetime_str], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ System time updated to: {datetime_str}")
        else:
            print(f"❌ Failed to set system time: {result.stderr}")
    else:
        print("✅ System time is already synchronized with RTC")

if __name__ == "__main__":
    main()
