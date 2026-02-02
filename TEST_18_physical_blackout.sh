#!/bin/bash
# TEST_18_physical_blackout.sh
# Physical test: Induce real blackout and verify detection
#
# This test requires:
# 1. A physical meter connected via RS485/USB
# 2. Ability to disconnect the meter's voltage input
#
# Usage: ./TEST_18_physical_blackout.sh

set -e

echo "=== Physical Blackout Detection Test ==="
echo "This will monitor for a real blackout event"
echo "You will need to physically disconnect the meter's voltage input"
echo ""
echo "Requirements:"
echo "  - Meter connected to /dev/ttyUSB0 (or update SERIAL_PORT below)"
echo "  - Meter powered and communicating (Freq=50, Int=0)"
echo "  - Ability to safely disconnect voltage to meter"
echo ""
echo "Test Procedure:"
echo "  1. Script will start monitoring at 0.5s intervals"
echo "  2. Wait for 'READY' message"
echo "  3. Disconnect voltage for 2-3 seconds"
echo "  4. Reconnect voltage"
echo "  5. Wait for monitoring to complete (60 seconds total)"
echo "  6. Check results"
echo ""

# Configuration
SERIAL_PORT="/dev/ttyUSB0"
PROJECT_DIR="/home/pi/Desktop/offline-setup-12Sep"
EVENTS_FILE="$PROJECT_DIR/data/csv/EVENTS.csv"
DATA_FILE="$PROJECT_DIR/data/csv/DATA_ALL.csv"

# Check if we're in the right directory
cd "$PROJECT_DIR" || {
    echo "ERROR: Cannot cd to $PROJECT_DIR"
    exit 1
}

# Check serial port
if [ ! -e "$SERIAL_PORT" ]; then
    echo "WARNING: Serial port $SERIAL_PORT not found"
    echo "Available ports:"
    ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "  (none found)"
    echo ""
    read -p "Enter serial port path (or press Enter to continue anyway): " ALT_PORT
    if [ -n "$ALT_PORT" ]; then
        SERIAL_PORT="$ALT_PORT"
    fi
fi

# Backup existing events file
if [ -f "$EVENTS_FILE" ]; then
    BACKUP_FILE="${EVENTS_FILE}.backup_$(date +%Y%m%d_%H%M%S)"
    cp "$EVENTS_FILE" "$BACKUP_FILE"
    echo "Backed up existing EVENTS.csv to $BACKUP_FILE"
fi

echo ""
read -p "Press Enter when meter is connected and stable..."

# Create Python monitoring script
MONITOR_SCRIPT=$(mktemp)
cat > "$MONITOR_SCRIPT" << 'PYEOF'
#!/usr/bin/env python3
"""Physical blackout monitoring script."""
import sys
import time
import os

# Add project to path
sys.path.insert(0, '/home/pi/Desktop/offline-setup-12Sep')

SERIAL_PORT = os.environ.get('SERIAL_PORT', '/dev/ttyUSB0')
MONITOR_DURATION = int(os.environ.get('MONITOR_DURATION', 60))

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    try:
        from pymodbus.client.sync import ModbusSerialClient
    except ImportError:
        print("ERROR: pymodbus not installed. Run: pip install pymodbus")
        sys.exit(1)

from src.devices.meter_manager import MeterManager
from src.devices.meter_device import MeterDevice

# Parameters for LG6400 meter
PARAMETERS = [
    "Time", "Frequency", "Voltage_L1_N", "Voltage_L2_N", "Voltage_L3_N",
    "Current_L1", "Current_L2", "Current_L3", "Power_Factor",
    "Active_Power", "Reactive_Power", "Apparent_Power",
    "Active_Energy", "Reactive_Energy", "No of interruption"
]

def main():
    print(f"Connecting to {SERIAL_PORT}...")
    
    try:
        client = ModbusSerialClient(
            method="rtu",
            port=SERIAL_PORT,
            baudrate=9600,
            timeout=1,
            stopbits=1,
            bytesize=8,
            parity='N'
        )
        
        if not client.connect():
            print(f"ERROR: Could not connect to {SERIAL_PORT}")
            sys.exit(1)
        
        print("Connected!")
        
    except Exception as e:
        print(f"ERROR connecting: {e}")
        sys.exit(1)
    
    try:
        meter = MeterDevice(
            name="PhysicalTest",
            model="LG6400",
            parameters=PARAMETERS,
            client=client,
            device_address=1
        )
        
        manager = MeterManager(
            meters=[meter],
            parameters=PARAMETERS,
            fast_poll_interval=0.5,
            slow_csv_interval=10
        )
        
        print("")
        print("=" * 50)
        print(">>> READY: DISCONNECT VOLTAGE NOW (2-3 seconds) <<<")
        print("=" * 50)
        print("")
        print(f"Monitoring for {MONITOR_DURATION} seconds...")
        
        start_time = time.time()
        poll_count = 0
        
        while time.time() - start_time < MONITOR_DURATION:
            manager.read_all(inter_device_delay=0.1)
            poll_count += 1
            
            # Progress indicator every 5 seconds
            elapsed = int(time.time() - start_time)
            if elapsed > 0 and elapsed % 5 == 0 and poll_count % 10 == 0:
                print(f"  {elapsed}s elapsed... ({poll_count} polls)", flush=True)
            
            # Small sleep to maintain polling rate
            time.sleep(0.1)
        
        print(f"\nMonitoring complete. Total polls: {poll_count}")
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    
    except Exception as e:
        print(f"ERROR during monitoring: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            client.close()
        except:
            pass
        
        print("\nConnection closed.")

if __name__ == "__main__":
    main()
PYEOF

# Run the monitoring script
echo ""
echo "Starting monitoring..."
export SERIAL_PORT
export MONITOR_DURATION=60

# Try with venv first, fall back to system python
if [ -d "test_venv" ]; then
    test_venv/bin/python3 "$MONITOR_SCRIPT"
elif [ -d "venv313" ]; then
    venv313/bin/python3 "$MONITOR_SCRIPT"
else
    python3 "$MONITOR_SCRIPT"
fi

RESULT=$?

# Cleanup
rm -f "$MONITOR_SCRIPT"

echo ""
echo "=== RESULTS ==="
echo ""

# Check events file
if [ -f "$EVENTS_FILE" ]; then
    echo "Blackout events detected:"
    echo "------------------------"
    grep -E "BLACKOUT|BLACKOUT_CONFIRMED" "$EVENTS_FILE" 2>/dev/null | tail -10 || echo "  (none)"
    echo ""
    
    echo "Comm error events:"
    echo "------------------"
    COMM_START=$(grep -c "COMM_ERROR_START" "$EVENTS_FILE" 2>/dev/null || echo "0")
    COMM_END=$(grep -c "COMM_ERROR_END" "$EVENTS_FILE" 2>/dev/null || echo "0")
    echo "  COMM_ERROR_START: $COMM_START"
    echo "  COMM_ERROR_END: $COMM_END"
    echo ""
    
    echo "Suspect/resolved events:"
    echo "------------------------"
    grep -E "SUSPECT_RESOLVED" "$EVENTS_FILE" 2>/dev/null | tail -5 || echo "  (none)"
    echo ""
else
    echo "EVENTS.csv not found at $EVENTS_FILE"
fi

# Check data file for timestamp gaps
if [ -f "$DATA_FILE" ]; then
    echo "Recent DATA_ALL.csv timestamps:"
    echo "-------------------------------"
    tail -20 "$DATA_FILE" | cut -d, -f3 | head -20
    echo ""
fi

echo ""
if [ $RESULT -eq 0 ]; then
    echo "✓ Monitoring completed successfully"
else
    echo "✗ Monitoring encountered errors (exit code: $RESULT)"
fi

echo ""
echo "Full events log: $EVENTS_FILE"
echo "Full data log: $DATA_FILE"
