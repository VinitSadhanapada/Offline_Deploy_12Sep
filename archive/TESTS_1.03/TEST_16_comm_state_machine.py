#!/usr/bin/env python3
"""
TEST_16: Comm Error State Machine - START and END events

Tests that:
1. COMM_ERROR_START is logged only ONCE when values become -1 (not every cycle)
2. COMM_ERROR_END is logged only ONCE when values recover (not every healthy cycle)
3. Consecutive error cycles do NOT produce multiple START events
4. Consecutive healthy cycles do NOT produce multiple END events
"""
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_comm_state_machine():
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        events_path = os.path.join(tmpdir, "EVENTS.csv")
        csv_path = os.path.join(tmpdir, "DATA_ALL.csv")
        data_dir = Path(tmpdir)
        
        meter = MagicMock()
        meter.name = "CommTest_Test"
        meter.device_address = 1
        meter.model = "LG6400"
        
        # Sequence: Healthy -> Error -> Error -> Healthy -> Healthy
        # Should produce: 1 START, 1 END (not 2 STARTs or 2 ENDs)
        readings = [
            ["10:00:00", 50.0, 230.0, 1.0, 100.0, 5],   # Healthy
            ["10:00:01", -1, -1, -1, -1, -1],            # Error starts
            ["10:00:02", -1, -1, -1, -1, -1],            # Error continues (no new START)
            ["10:00:03", 50.0, 230.0, 1.0, 100.0, 5],   # Recovered (END logged)
            ["10:00:04", 50.0, 230.0, 1.0, 100.0, 5],   # Healthy continues (no new END)
        ]
        
        idx = [0]
        def read_seq():
            r = readings[min(idx[0], len(readings)-1)]
            idx[0] += 1
            return r
        
        meter.read_data = read_seq
        
        parameters = ["Time", "Frequency", "Voltage", "Current", "Power", "No of interruption"]
        
        manager = MeterManager(
            meters=[meter],
            parameters=parameters,
            fast_poll_interval=0,
            slow_csv_interval=9999
        )
        
        # Override paths to use temp directory (isolate test data)
        manager.csv_path = csv_path
        manager.events_path = Path(events_path)
        manager.data_dir = data_dir
        manager._init_events_csv()
        
        # Run 5 polls
        for i in range(5):
            manager.read_all(inter_device_delay=0)
        
        with open(events_path, 'r') as f:
            content = f.read()
        
        # Count START and END events
        start_count = content.count('COMM_ERROR_START')
        end_count = content.count('COMM_ERROR_END')
        
        assert start_count == 1, \
            f"Should have exactly 1 COMM_ERROR_START, got {start_count}. Content:\n{content}"
        assert end_count == 1, \
            f"Should have exactly 1 COMM_ERROR_END, got {end_count}. Content:\n{content}"
        
        print("✓ PASS: Comm state machine working (single START/END per transition)")
        return True


def test_comm_error_multiple_transitions():
    """Test multiple healthy->error->healthy transitions produce correct event counts."""
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        events_path = os.path.join(tmpdir, "EVENTS.csv")
        csv_path = os.path.join(tmpdir, "DATA_ALL.csv")
        data_dir = Path(tmpdir)
        
        meter = MagicMock()
        meter.name = "MultiTransition_Test"
        meter.device_address = 1
        meter.model = "LG6400"
        
        # Sequence: Healthy -> Error -> Healthy -> Error -> Healthy
        # Should produce: 2 START, 2 END
        readings = [
            ["10:00:00", 50.0, 230.0, 1.0, 100.0, 5],   # Healthy
            ["10:00:01", -1, -1, -1, -1, -1],            # Error 1 START
            ["10:00:02", 50.0, 230.0, 1.0, 100.0, 5],   # END 1
            ["10:00:03", -1, -1, -1, -1, -1],            # Error 2 START
            ["10:00:04", 50.0, 230.0, 1.0, 100.0, 5],   # END 2
        ]
        
        idx = [0]
        def read_seq():
            r = readings[min(idx[0], len(readings)-1)]
            idx[0] += 1
            return r
        
        meter.read_data = read_seq
        
        parameters = ["Time", "Frequency", "Voltage", "Current", "Power", "No of interruption"]
        
        manager = MeterManager(
            meters=[meter],
            parameters=parameters,
            fast_poll_interval=0,
            slow_csv_interval=9999
        )
        
        # Override paths to use temp directory (isolate test data)
        manager.csv_path = csv_path
        manager.events_path = Path(events_path)
        manager.data_dir = data_dir
        manager._init_events_csv()
        
        # Run 5 polls
        for i in range(5):
            manager.read_all(inter_device_delay=0)
        
        with open(events_path, 'r') as f:
            content = f.read()
        
        start_count = content.count('COMM_ERROR_START')
        end_count = content.count('COMM_ERROR_END')
        
        assert start_count == 2, \
            f"Should have exactly 2 COMM_ERROR_START, got {start_count}. Content:\n{content}"
        assert end_count == 2, \
            f"Should have exactly 2 COMM_ERROR_END, got {end_count}. Content:\n{content}"
        
        print("✓ PASS: Multiple transitions correctly logged (2 START, 2 END)")
        return True


def test_partial_comm_error():
    """Test that partial -1 values (only some fields) are detected as comm error."""
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        events_path = os.path.join(tmpdir, "EVENTS.csv")
        csv_path = os.path.join(tmpdir, "DATA_ALL.csv")
        data_dir = Path(tmpdir)
        
        meter = MagicMock()
        meter.name = "PartialError_Test"
        meter.device_address = 1
        meter.model = "LG6400"
        
        # Sequence: Healthy -> Partial error (Freq=-1 but Int=5) -> Healthy
        readings = [
            ["10:00:00", 50.0, 230.0, 1.0, 100.0, 5],   # Healthy
            ["10:00:01", -1, 230.0, 1.0, 100.0, 5],      # Partial: Freq=-1, Int=5 (should be error)
            ["10:00:02", 50.0, 230.0, 1.0, 100.0, 5],   # Recovered
        ]
        
        idx = [0]
        def read_seq():
            r = readings[min(idx[0], len(readings)-1)]
            idx[0] += 1
            return r
        
        meter.read_data = read_seq
        
        parameters = ["Time", "Frequency", "Voltage", "Current", "Power", "No of interruption"]
        
        manager = MeterManager(
            meters=[meter],
            parameters=parameters,
            fast_poll_interval=0,
            slow_csv_interval=9999
        )
        
        # Override paths to use temp directory (isolate test data)
        manager.csv_path = csv_path
        manager.events_path = Path(events_path)
        manager.data_dir = data_dir
        manager._init_events_csv()
        
        for i in range(3):
            manager.read_all(inter_device_delay=0)
        
        with open(events_path, 'r') as f:
            content = f.read()
        
        # Should detect comm error when Freq=-1 (even if Int is valid)
        start_count = content.count('COMM_ERROR_START')
        end_count = content.count('COMM_ERROR_END')
        
        assert start_count == 1, \
            f"Partial error should trigger COMM_ERROR_START, got {start_count}. Content:\n{content}"
        assert end_count == 1, \
            f"Recovery should trigger COMM_ERROR_END, got {end_count}. Content:\n{content}"
        
        print("✓ PASS: Partial comm error (Freq=-1) correctly detected")
        return True


if __name__ == "__main__":
    success = True
    
    for test_func in [test_comm_state_machine, test_comm_error_multiple_transitions, test_partial_comm_error]:
        try:
            success = test_func() and success
        except Exception as e:
            print(f"✗ FAIL: {test_func.__name__} - {e}")
            import traceback
            traceback.print_exc()
            success = False
    
    sys.exit(0 if success else 1)
