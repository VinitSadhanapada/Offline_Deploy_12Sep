#!/usr/bin/env python3
"""
TEST_01: Verify normal CSV writing still works (regression test)
PASS if: File created, data readable, no exceptions
"""
import sys
import os
import tempfile
import csv
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent))

def test_basic_write():
    from src.devices.meter_manager import MeterManager, create_formatted_csv_header
    from unittest.mock import MagicMock
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test.csv")
        
        # Create minimal manager
        m = MagicMock()
        m.name = "TestMeter"
        m.device_address = 1
        m.model = "LG6400"
        m.read_data = MagicMock(return_value=["2026-01-25 10:00:00", 50.0, 230.0])
        
        # Initialize with custom path
        manager = MeterManager(
            meters=[m],
            parameters=["Time", "Frequency", "Voltage"],
            csv_filenames=[csv_path]
        )
        manager.csv_path = csv_path
        
        # Test write
        try:
            manager._write_row_safe([1, "TestMeter", "2026-01-25 10:00:00", "LG6400", 50.0, 230.0])
            
            # Verify file exists and readable
            assert os.path.exists(csv_path), "CSV not created"
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                assert len(rows) >= 1, f"Expected at least 1 row, got {len(rows)}"
            
            print("✓ PASS: Basic write works")
            return True
            
        except Exception as e:
            print(f"✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_basic_write()
    sys.exit(0 if success else 1)
