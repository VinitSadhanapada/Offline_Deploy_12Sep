#!/usr/bin/env python3
"""
TEST_17: Distinguish True Blackout (Freq=0,Int↑) vs Meter Glitch (Freq>0,Int↑)

Tests that:
1. Int increase WITH Freq=0 -> BLACKOUT logged (true power loss)
2. Int increase WITH Freq>0 -> NO BLACKOUT (meter glitch or reset, not power loss)
3. The key distinction is: Freq=0 proves the LINE is dead, not just meter hiccup
"""
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_blackout_vs_glitch():
    """Test that Int increase is ignored when Freq>0 (not a true blackout)."""
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        events_path = os.path.join(tmpdir, "EVENTS.csv")
        csv_path = os.path.join(tmpdir, "DATA_ALL.csv")
        data_dir = Path(tmpdir)
        
        meter = MagicMock()
        meter.name = "GlitchTest_Test"
        meter.device_address = 1
        meter.model = "LG6400"
        
        # Scenario: Int increases but Freq still 50 (not a blackout - meter glitch)
        readings = [
            ["10:00:00", 50.0, 230.0, 1.0, 100.0, 5],  # Normal: Int=5
            ["10:00:01", 50.0, 230.0, 1.0, 100.0, 6],  # Int up to 6, but Freq=50 (glitch)
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
        manager._meter_last_valid_int["GlitchTest_Test"] = 5  # Pre-set
        
        # Run 2 polls
        for _ in range(2):
            manager.read_all(inter_device_delay=0)
        
        with open(events_path, 'r') as f:
            content = f.read()
        
        # Should NOT have BLACKOUT because Freq was not 0
        # Per requirement: "Freq=0 AND Int increased" proves line dead
        blackout_count = content.count('BLACKOUT')
        
        # Exclude header line from count
        lines = content.strip().split('\n')
        blackout_events = [l for l in lines if 'BLACKOUT' in l and 'timestamp' not in l.lower()]
        
        assert len(blackout_events) == 0, \
            f"Should NOT log BLACKOUT if Freq>0, found {len(blackout_events)}. Content:\n{content}"
        
        print("✓ PASS: Correctly ignored Int increase when Freq>0 (not a blackout)")
        return True


def test_true_blackout_detection():
    """Test that Freq=0 AND Int increase correctly logs BLACKOUT."""
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        events_path = os.path.join(tmpdir, "EVENTS.csv")
        csv_path = os.path.join(tmpdir, "DATA_ALL.csv")
        data_dir = Path(tmpdir)
        
        meter = MagicMock()
        meter.name = "TrueBlackout_Test"
        meter.device_address = 1
        meter.model = "LG6400"
        
        # Scenario: Int increases AND Freq=0 (true blackout)
        readings = [
            ["10:00:00", 50.0, 230.0, 1.0, 100.0, 5],  # Normal: Int=5
            ["10:00:01", 0.0, 0.0, 0.0, 0.0, 6],       # BLACKOUT: Freq=0, Int=6
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
        manager._meter_last_valid_int["TrueBlackout_Test"] = 5  # Pre-set
        
        # Run 2 polls
        for _ in range(2):
            manager.read_all(inter_device_delay=0)
        
        with open(events_path, 'r') as f:
            content = f.read()
        
        # Should have BLACKOUT because Freq=0 AND Int increased
        lines = content.strip().split('\n')
        blackout_events = [l for l in lines if 'BLACKOUT' in l and 'timestamp' not in l.lower()]
        
        assert len(blackout_events) >= 1, \
            f"Should log BLACKOUT when Freq=0 AND Int increased, found {len(blackout_events)}. Content:\n{content}"
        
        # Verify the count values are in the event
        assert '5' in content and '6' in content, \
            f"Should show count 5->6 in BLACKOUT event. Content:\n{content}"
        
        print("✓ PASS: True blackout (Freq=0, Int↑) correctly detected")
        return True


def test_multiple_int_increase_with_freq_zero():
    """Test multiple interruptions during extended blackout."""
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        events_path = os.path.join(tmpdir, "EVENTS.csv")
        csv_path = os.path.join(tmpdir, "DATA_ALL.csv")
        data_dir = Path(tmpdir)
        
        meter = MagicMock()
        meter.name = "ExtendedBlackout_Test"
        meter.device_address = 1
        meter.model = "LG6400"
        
        # Scenario: Multiple Int increases during extended Freq=0 period
        readings = [
            ["10:00:00", 50.0, 230.0, 1.0, 100.0, 0],  # Normal
            ["10:00:01", 0.0, 0.0, 0.0, 0.0, 1],       # Blackout start: Int 0->1
            ["10:00:02", 0.0, 0.0, 0.0, 0.0, 2],       # More blackouts: Int 1->2
            ["10:00:03", 0.0, 0.0, 0.0, 0.0, 3],       # More blackouts: Int 2->3
            ["10:00:04", 50.0, 230.0, 1.0, 100.0, 3],  # Recovery
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
        manager._meter_last_valid_int["ExtendedBlackout_Test"] = 0
        
        # Run 5 polls
        for _ in range(5):
            manager.read_all(inter_device_delay=0)
        
        with open(events_path, 'r') as f:
            content = f.read()
        
        # Should have multiple BLACKOUT events (one for each Int increase)
        lines = content.strip().split('\n')
        blackout_events = [l for l in lines if 'BLACKOUT' in l and 'timestamp' not in l.lower()]
        
        # Should detect Int 0->1, 1->2, 2->3 = 3 blackout events
        assert len(blackout_events) >= 3, \
            f"Should log multiple BLACKOUTs during extended outage, found {len(blackout_events)}. Content:\n{content}"
        
        print("✓ PASS: Multiple interruptions during extended blackout correctly logged")
        return True


if __name__ == "__main__":
    success = True
    
    for test_func in [test_blackout_vs_glitch, test_true_blackout_detection, test_multiple_int_increase_with_freq_zero]:
        try:
            success = test_func() and success
        except Exception as e:
            print(f"✗ FAIL: {test_func.__name__} - {e}")
            import traceback
            traceback.print_exc()
            success = False
    
    sys.exit(0 if success else 1)
