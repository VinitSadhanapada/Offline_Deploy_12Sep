#!/usr/bin/env python3
"""
TEST_04: Integration smoke test - run 3 cycles of MeterManager
PASS if: No exceptions, CSV created with expected structure
"""
import sys
import os
import tempfile
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_integration():
    from src.devices.meter_manager import MeterManager
    from unittest.mock import MagicMock
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "integration.csv")
        
        # Setup mock meter
        m = MagicMock()
        m.name = "SmokeTest"
        m.device_address = 1
        m.model = "LG6400"
        m.read_data = MagicMock(return_value=["2026-01-25 10:00:00", 50.0, 230.0])
        
        try:
            manager = MeterManager([m], ["Time", "Frequency", "Voltage"])
            manager.csv_path = csv_path
            
            # Simulate 3 read cycles
            for i in range(3):
                manager.read_all()
                m.read_data.return_value[0] = f"2026-01-25 10:00:0{i+1}"  # Increment time
            
            # Verify output
            assert os.path.exists(csv_path), "CSV not created after 3 cycles"
            
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                assert len(rows) >= 4, f"Expected at least 4 rows (header+3 data), got {len(rows)}"
                # Check column count consistency
                col_counts = [len(r) for r in rows]
                assert len(set(col_counts)) == 1, f"Inconsistent columns: {col_counts}"
            
            print("✓ PASS: Integration smoke test successful")
            return True
            
        except Exception as e:
            print(f"✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_integration()
    sys.exit(0 if success else 1)
