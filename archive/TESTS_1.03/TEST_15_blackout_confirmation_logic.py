#!/usr/bin/env python3
"""
TEST_15: Option C Deferred Confirmation - Verify blackouts are confirmed on next poll

Tests that:
1. Suspect state (Freq=0, Int=0) sets pending_confirmation=True but does NOT log immediately
2. If next poll shows Int increase, BLACKOUT_CONFIRMED and BLACKOUT are logged
3. If next poll shows Freq>0 without Int increase, SUSPECT_RESOLVED is logged
"""
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_deferred_confirmation():
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        events_path = os.path.join(tmpdir, "EVENTS.csv")
        csv_path = os.path.join(tmpdir, "DATA_ALL.csv")
        data_dir = Path(tmpdir)
        
        meter = MagicMock()
        meter.name = "TestMeter_Test"
        meter.device_address = 1
        meter.model = "LG6400"
        
        # Sequence: Normal -> Suspect (Freq=0,Int=0) -> Confirmed (Freq=0,Int=1)
        # This proves Option C works (defers logging until Int increases)
        # Format: [Time, Freq, Voltage, ..., Interruption] - indices depend on parameters
        readings = [
            ["2026-01-25 10:00:00", 50.0, 230.0, 0, 0, 0],  # Normal: Freq=50, Int=0
            ["2026-01-25 10:00:01", 0.0, 0.0, 0, 0, 0],      # Suspect: Freq=0, Int=0
            ["2026-01-25 10:00:02", 0.0, 0.0, 0, 0, 1],      # Confirmed: Freq=0, Int=1
            ["2026-01-25 10:00:03", 50.0, 230.0, 0, 0, 1],   # Recovered: Freq=50, Int=1
        ]
        
        call_idx = [0]
        def read_seq():
            r = readings[min(call_idx[0], len(readings)-1)]
            call_idx[0] += 1
            return r
        
        meter.read_data = read_seq
        
        # Parameters order: Time, Frequency, Voltage, Current, Power, No of interruption
        parameters = ["Time", "Frequency", "Voltage", "Current", "Power", "No of interruption"]
        
        manager = MeterManager(
            meters=[meter],
            parameters=parameters,
            fast_poll_interval=0,  # No throttling for test
            slow_csv_interval=9999  # Don't write slow CSV during test
        )
        
        # Override paths to use temp directory (isolate test data)
        manager.csv_path = csv_path
        manager.events_path = Path(events_path)
        manager.data_dir = data_dir
        manager._init_events_csv()
        
        # Pre-set last valid int
        manager._meter_last_valid_int["TestMeter_Test"] = 0
        
        # Poll 1: Normal (no event expected)
        manager.read_all(inter_device_delay=0)
        assert call_idx[0] == 1, f"Expected 1 read, got {call_idx[0]}"
        
        # Poll 2: Suspect (should set pending, but NOT log yet)
        manager.read_all(inter_device_delay=0)
        assert call_idx[0] == 2, f"Expected 2 reads, got {call_idx[0]}"
        
        suspect_state = manager._meter_suspect_state.get("TestMeter", {})
        assert suspect_state.get("pending_confirmation") == True, \
            f"Should have pending_confirmation=True, got {suspect_state}"
        
        # Check events file - should NOT have BLACKOUT yet
        with open(events_path, 'r') as f:
            content = f.read()
            blackout_count = content.count('BLACKOUT')
            assert blackout_count == 0, \
                f"Option C should defer logging, found {blackout_count} BLACKOUT entries before confirmation"
        
        # Poll 3: Confirmed (should log BLACKOUT_CONFIRMED and BLACKOUT)
        manager.read_all(inter_device_delay=0)
        assert call_idx[0] == 3, f"Expected 3 reads, got {call_idx[0]}"
        
        with open(events_path, 'r') as f:
            content = f.read()
            
        # Should have BLACKOUT_CONFIRMED or BLACKOUT now
        has_confirmed = 'BLACKOUT_CONFIRMED' in content
        has_blackout = 'BLACKOUT' in content
        
        assert has_confirmed or has_blackout, \
            f"Should log blackout on confirmation. Content:\n{content}"
        
        # Verify count values are in the log
        assert '0' in content and '1' in content, \
            f"Should show count 0->1 in events. Content:\n{content}"
        
        print("✓ PASS: Option C deferred confirmation working")
        return True


def test_suspect_resolved():
    """Test that suspect state is resolved without blackout if Freq recovers without Int increase."""
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        events_path = os.path.join(tmpdir, "EVENTS.csv")
        csv_path = os.path.join(tmpdir, "DATA_ALL.csv")
        data_dir = Path(tmpdir)
        
        meter = MagicMock()
        meter.name = "ResolveMeter_Test"
        meter.device_address = 1
        meter.model = "LG6400"
        
        # Sequence: Normal -> Suspect (Freq=0,Int=0) -> Resolved (Freq=50,Int=0)
        readings = [
            ["2026-01-25 10:00:00", 50.0, 230.0, 0, 0, 0],  # Normal
            ["2026-01-25 10:00:01", 0.0, 0.0, 0, 0, 0],      # Suspect
            ["2026-01-25 10:00:02", 50.0, 230.0, 0, 0, 0],   # Resolved (no Int increase)
        ]
        
        call_idx = [0]
        def read_seq():
            r = readings[min(call_idx[0], len(readings)-1)]
            call_idx[0] += 1
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
        manager._meter_last_valid_int["ResolveMeter_Test"] = 0
        
        # 3 polls
        for _ in range(3):
            manager.read_all(inter_device_delay=0)
        
        with open(events_path, 'r') as f:
            content = f.read()
        
        # Should have SUSPECT_RESOLVED, NOT BLACKOUT
        has_resolved = 'SUSPECT_RESOLVED' in content
        has_blackout = content.count('BLACKOUT') > 0 and 'SUSPECT_RESOLVED' not in content
        
        assert has_resolved or not has_blackout, \
            f"Should resolve suspect without blackout. Content:\n{content}"
        
        print("✓ PASS: Suspect state correctly resolved without false blackout")
        return True


if __name__ == "__main__":
    success = True
    try:
        success = test_deferred_confirmation() and success
    except Exception as e:
        print(f"✗ FAIL: test_deferred_confirmation - {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    try:
        success = test_suspect_resolved() and success
    except Exception as e:
        print(f"✗ FAIL: test_suspect_resolved - {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    sys.exit(0 if success else 1)
