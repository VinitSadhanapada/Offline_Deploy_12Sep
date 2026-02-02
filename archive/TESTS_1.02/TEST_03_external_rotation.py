#!/usr/bin/env python3
"""
TEST_03: Simulate external file rotation (logrotate/manual move)
PASS if: Script detects missing file and recreates automatically
"""
import sys
import os
import tempfile
import csv
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_rotation_detection():
    from src.devices.meter_manager import MeterManager
    from unittest.mock import MagicMock
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "data.csv")
        
        # Setup manager and write initial data
        m = MagicMock()
        m.name = "TestMeter"
        
        manager = MeterManager([m], ["Time", "Frequency", "Voltage"])
        manager.csv_path = csv_path
        manager._write_row_safe([1, "Test", "2026-01-25 10:00:00", "LG6400", 50.0, 230.0])
        
        # Simulate external rotation (like your backup script does)
        backup_path = os.path.join(tmpdir, "data.csv.1")
        os.rename(csv_path, backup_path)
        
        # Verify file is gone
        assert not os.path.exists(csv_path), "Test setup failed: file still exists"
        
        try:
            # Next write should detect and recreate
            manager._write_row_safe([1, "Test", "2026-01-25 10:01:00", "LG6400", 50.0, 230.0])
            
            # Verify new file created with headers
            assert os.path.exists(csv_path), "File not recreated after rotation"
            
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                assert rows[0][0] == "Device_ID", "Header not written to new file"
            
            print("✓ PASS: External rotation handled correctly")
            return True
            
        except Exception as e:
            print(f"✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_rotation_detection()
    sys.exit(0 if success else 1)
