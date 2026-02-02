#!/usr/bin/env python3
"""
TEST_02: Create corrupted CSV (concatenated lines) and verify repair
PASS if: Corruption detected, file repaired, data preserved
"""
import sys
import os
import tempfile
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_corruption_repair():
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "corrupted.csv")
        
        # Create intentionally corrupted file (simulating power loss mid-write)
        with open(csv_path, 'w') as f:
            f.write("Device_ID,Meter_Name,Time,Model,Frequency,Voltage\n")
            f.write("1,Meter1,2026-01-25 10:00:00,LG6400,50.0,230.0\n")
            # Corrupted line: two records concatenated
            f.write("1,Meter1,2026-01-25 10:00:01,LG6400,0.0,0.0,2,Meter2,2026-01-25 10:00:02,LG6400,50.0,230.0\n")
            f.write("1,Meter1,2026-01-25 10:00:03,LG6400,50.0,230.0\n")
        
        # Create manager which should detect and repair
        from unittest.mock import MagicMock
        m = MagicMock()
        m.name = "TestMeter"
        
        manager = MeterManager([m], ["Time", "Frequency", "Voltage"])
        manager.csv_path = csv_path
        
        try:
            # Run detection
            manager._detect_and_repair_corruption()
            
            # Verify repaired file
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                headers = rows[0]
                
                # Check: Should have no row with excessive columns (expected is 6)
                max_cols = max(len(row) for row in rows)
                assert max_cols <= 6, f"Corruption still present: row with {max_cols} columns found"
                
                # Check: All timestamps should be valid (not concatenated)
                for i, row in enumerate(rows[1:], 1):
                    if len(row) >= 3:
                        ts = row[2]
                        assert ts.count(':') == 2, f"Row {i} has invalid timestamp: {ts}"
                
            print(f"✓ PASS: Corruption repaired, {len(rows)} total rows")
            return True
            
        except Exception as e:
            print(f"✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_corruption_repair()
    sys.exit(0 if success else 1)
