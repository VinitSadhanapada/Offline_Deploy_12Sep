#!/usr/bin/env python3
"""
TEST_12: ROTATION TIMING TEST

PURPOSE: Verify rotation happens when file exceeds size threshold and hourly check is triggered.

SCENARIO:
  1. Create MeterManager with short prune check interval (for fast testing)
  2. Create a CSV file with ~1000 rows (exceeds threshold)
  3. Force prune check by resetting _last_prune_check to 0
  4. Call _maybe_prune_old_rows()
  5. Verify:
     - Backup file created in backup/ directory
     - Backup naming follows [START]_TO_[END].csv pattern
     - Original DATA_ALL.csv is truncated (just headers)
     - CSV_ROTATION event logged

IMPORTANT: Uses stdlib only, no pip install required.
"""
import sys
import os
import csv
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def log(level, msg):
    """Verbose test logging with timestamp."""
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"{ts} [{level}] {msg}")

def create_test_csv(csv_path, num_rows=1000):
    """Create a CSV file with many rows to exceed size threshold."""
    start_time = datetime(2026, 1, 18, 10, 0, 0)
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        # Header: Device_ID, Meter_Name, Time, Model, Frequency, Voltage, Current
        writer.writerow(["Device_ID", "Meter_Name", "Time", "Model", "Frequency", "Voltage", "Current"])
        
        for i in range(num_rows):
            ts = (start_time + timedelta(minutes=i)).strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow([1, "TestMeter", ts, "LG6400", 50.0, 230.5, 5.2])
    
    return start_time

def test_rotation_timing():
    """Test that rotation triggers when file is large and prune check interval passes."""
    print("")
    print("=" * 80)
    log("INFO", "TEST_12: ROTATION TIMING TEST")
    print("=" * 80)
    print("""
    PURPOSE: Verify rotation happens when file exceeds size threshold
             and the hourly prune check interval has passed.
    
    SCENARIO:
      1. Create large CSV (1000 rows)
      2. Force prune check interval to pass
      3. Call _maybe_prune_old_rows()
      4. Verify backup created and original truncated
    """)
    
    # Import MeterManager
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "DATA_ALL.csv")
        backup_dir = os.path.join(tmpdir, "backup")
        os.makedirs(backup_dir, exist_ok=True)
        events_path = os.path.join(tmpdir, "EVENTS.csv")
        
        print("-" * 40)
        log("INFO", "SETUP: CREATING LARGE CSV FILE")
        print("-" * 40)
        
        # Create large CSV
        start_time = create_test_csv(csv_path, num_rows=1000)
        initial_size = os.path.getsize(csv_path)
        log("OUTPUT", f"Created test CSV: {csv_path}")
        log("DETAIL", f"  Rows: 1000")
        log("DETAIL", f"  Size: {initial_size} bytes ({initial_size/1024:.1f} KB)")
        log("DETAIL", f"  Start timestamp: {start_time}")
        
        print("-" * 40)
        log("INFO", "SETUP: CREATING METERMANAGER")
        print("-" * 40)
        
        # Create mock meter
        mock_meter = MagicMock()
        mock_meter.name = "TestMeter"
        mock_meter.model = "LG6400"
        mock_meter.device_address = 1
        
        # Create manager (will use default paths initially)
        manager = MeterManager(
            meters=[mock_meter],
            parameters=["Time", "Frequency", "Voltage", "Current"]
        )
        
        # Close default file handles
        try:
            manager.csv_file.close()
        except:
            pass
        try:
            manager.events_file.close()
        except:
            pass
        
        # Override paths to use temp directory
        manager.csv_path = csv_path
        manager.backup_dir = Path(backup_dir)
        manager.events_path = Path(events_path)
        manager.data_dir = Path(tmpdir)
        
        # Set low threshold for testing (500 bytes)
        manager.rotation_size_threshold = 500
        
        # Set short prune interval for testing
        manager.prune_check_interval = 0.1  # 100ms
        
        # Set CSV start time to match our test file
        manager._current_csv_start_time = start_time
        
        # Open our test file
        manager.csv_file = open(csv_path, 'a', newline='', buffering=1)
        manager.csv_writer = csv.writer(manager.csv_file)
        
        # Initialize events writer for logging
        with open(events_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp_detected', 'event_type', 'meter_name', 'details', 'count_before', 'count_after', 'estimated_start'])
        manager.events_file = open(events_path, 'a', newline='', buffering=1)
        manager.events_writer = csv.writer(manager.events_file)
        
        log("OUTPUT", "MeterManager created")
        log("DETAIL", f"  csv_path: {manager.csv_path}")
        log("DETAIL", f"  backup_dir: {manager.backup_dir}")
        log("DETAIL", f"  rotation_size_threshold: {manager.rotation_size_threshold} bytes")
        log("DETAIL", f"  prune_check_interval: {manager.prune_check_interval}s")
        
        print("-" * 40)
        log("INFO", "FORCING PRUNE CHECK (simulating 1 hour passed)")
        print("-" * 40)
        
        # Force prune check by setting last check time to past
        manager._last_prune_check = 0
        log("INPUT", "_last_prune_check set to 0 (forcing check)")
        
        # Wait a bit to ensure interval passes
        time.sleep(0.2)
        
        print("-" * 40)
        log("INFO", "CALLING _maybe_prune_old_rows()")
        print("-" * 40)
        
        log("PROCESS", "Executing rotation check...")
        manager._maybe_prune_old_rows()
        
        # Allow file operations to complete
        time.sleep(0.1)
        
        print("-" * 40)
        log("INFO", "ANALYZING RESULTS")
        print("-" * 40)
        
        # Check for backup files
        backup_files = list(Path(backup_dir).glob("*.csv"))
        log("OUTPUT", f"Backup files found: {len(backup_files)}")
        
        all_passed = True
        
        # CHECK 1: Backup file created
        print("-" * 40)
        log("INFO", "CHECK 1: Backup file created")
        print("-" * 40)
        
        if len(backup_files) == 0:
            log("FAIL", "✗ No backup file created")
            all_passed = False
        else:
            log("PASS", f"✓ Backup file created: {backup_files[0].name}")
            backup_name = backup_files[0].name
            backup_size = backup_files[0].stat().st_size
            log("DETAIL", f"  Size: {backup_size} bytes ({backup_size/1024:.1f} KB)")
        
        # CHECK 2: Naming convention
        print("-" * 40)
        log("INFO", "CHECK 2: Backup naming convention")
        print("-" * 40)
        
        if backup_files:
            backup_name = backup_files[0].name
            if '_TO_' in backup_name:
                log("PASS", "✓ Backup follows [START]_TO_[END].csv pattern")
                
                # Parse dates from name
                parts = backup_name.replace('.csv', '').split('_TO_')
                log("DETAIL", f"  Start: {parts[0]}")
                log("DETAIL", f"  End: {parts[1]}")
            else:
                log("FAIL", f"✗ Backup naming incorrect: {backup_name}")
                all_passed = False
        
        # CHECK 3: Original file truncated (only headers remain)
        print("-" * 40)
        log("INFO", "CHECK 3: Original CSV truncated")
        print("-" * 40)
        
        new_size = os.path.getsize(csv_path)
        log("OUTPUT", f"Original file new size: {new_size} bytes")
        
        if new_size < 500:  # Should be just headers (~100 bytes)
            log("PASS", "✓ Original file truncated (headers only)")
            
            # Verify headers are intact
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header and 'Device_ID' in header:
                    log("DETAIL", f"  Header preserved: {header[:4]}...")
                else:
                    log("WARN", "  Header may be missing or corrupted")
        else:
            log("FAIL", f"✗ Original file not truncated: {new_size} bytes (expected < 500)")
            all_passed = False
        
        # CHECK 4: Size reduction
        print("-" * 40)
        log("INFO", "CHECK 4: Size reduction ratio")
        print("-" * 40)
        
        if backup_files:
            backup_size = backup_files[0].stat().st_size
            reduction_pct = ((initial_size - new_size) / initial_size) * 100
            log("OUTPUT", f"Size reduction: {initial_size} -> {new_size} bytes ({reduction_pct:.1f}%)")
            
            if reduction_pct > 90:
                log("PASS", f"✓ Significant size reduction: {reduction_pct:.1f}%")
            else:
                log("WARN", f"⚠ Low size reduction: {reduction_pct:.1f}%")
            
            # Verify backup preserves data
            if backup_size >= initial_size * 0.9:
                log("PASS", "✓ Backup preserves original data")
            else:
                log("FAIL", f"✗ Backup size mismatch: {backup_size} vs original {initial_size}")
                all_passed = False
        
        # CHECK 5: Events log
        print("-" * 40)
        log("INFO", "CHECK 5: CSV_ROTATION event logged")
        print("-" * 40)
        
        try:
            manager.events_file.flush()
            with open(events_path, 'r') as f:
                events_content = f.read()
            
            if 'CSV_ROTATION' in events_content:
                log("PASS", "✓ CSV_ROTATION event logged to EVENTS.csv")
                # Extract the event line
                for line in events_content.split('\n'):
                    if 'CSV_ROTATION' in line:
                        log("DETAIL", f"  Event: {line[:100]}...")
                        break
            else:
                log("WARN", "⚠ CSV_ROTATION event not found in EVENTS.csv")
        except Exception as e:
            log("WARN", f"⚠ Could not read events file: {e}")
        
        # Cleanup
        try:
            manager.csv_file.close()
            manager.events_file.close()
        except:
            pass
        
        print("")
        print("=" * 80)
        if all_passed:
            log("PASS", "TEST_12 RESULT: ALL CHECKS PASSED")
        else:
            log("FAIL", "TEST_12 RESULT: SOME CHECKS FAILED")
        print("=" * 80)
        
        return all_passed

if __name__ == "__main__":
    success = test_rotation_timing()
    sys.exit(0 if success else 1)
