#!/usr/bin/env python3
"""
TEST_05: Verify dual-rate timing - fast poll throttling works
PASS if: Multiple rapid calls are throttled to fast_poll_interval

This test verifies that the MeterManager correctly throttles polling
to respect the fast_poll_interval setting, preventing excessive RS485 traffic.
"""
import sys
import os
import tempfile
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    prefix = {
        "INFO": f"{Colors.CYAN}[INFO]{Colors.ENDC}",
        "INPUT": f"{Colors.YELLOW}[INPUT]{Colors.ENDC}",
        "PROCESS": f"{Colors.BLUE}[PROCESS]{Colors.ENDC}",
        "OUTPUT": f"{Colors.GREEN}[OUTPUT]{Colors.ENDC}",
        "CHECK": f"{Colors.BOLD}[CHECK]{Colors.ENDC}",
        "PASS": f"{Colors.GREEN}{Colors.BOLD}[PASS]{Colors.ENDC}",
        "FAIL": f"{Colors.RED}{Colors.BOLD}[FAIL]{Colors.ENDC}",
        "HEADER": f"{Colors.HEADER}{Colors.BOLD}",
        "DETAIL": f"{Colors.DIM}[DETAIL]{Colors.ENDC}",
    }
    print(f"{timestamp} {prefix.get(level, '[???]')} {msg}")

def test_fast_poll_throttling():
    print("\n" + "="*80)
    log("TEST_05: DUAL-RATE THROTTLE TEST", "HEADER")
    print("="*80 + Colors.ENDC)
    print("""
    PURPOSE: Verify that MeterManager throttles rapid polling calls
             to respect the fast_poll_interval setting.
    
    SCENARIO: Call read_all() 10 times with only 50ms gaps, but
              fast_poll_interval is set to 500ms. Most calls should
              be ignored (throttled).
    """)
    
    from src.devices.meter_manager import MeterManager
    from unittest.mock import MagicMock
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log(f"Created temp directory: {tmpdir}", "INFO")
        
        # ===== INPUT SETUP =====
        print("\n" + "-"*40)
        log("SETTING UP INPUTS", "HEADER")
        print("-"*40 + Colors.ENDC)
        
        m = MagicMock()
        m.name = "TestMeter"
        m.device_address = 1
        m.model = "LG6400"
        call_count = [0]
        call_times = []
        
        def mock_read():
            call_count[0] += 1
            call_times.append(time.time())
            log(f"  meter.read_data() called (call #{call_count[0]})", "DETAIL")
            return ["2026-01-25 10:00:00", 50.0, 230.0, 0]
        
        m.read_data = mock_read
        
        log(f"Mock meter created:", "INPUT")
        log(f"  - Name: {m.name}", "INPUT")
        log(f"  - Device Address: {m.device_address}", "INPUT")
        log(f"  - Model: {m.model}", "INPUT")
        log(f"  - Returns: [Time, Freq=50.0, Voltage=230.0, Interruption=0]", "INPUT")
        
        fast_poll = 0.5
        slow_csv = 60
        log(f"Timing configuration:", "INPUT")
        log(f"  - fast_poll_interval: {fast_poll}s (500ms)", "INPUT")
        log(f"  - slow_csv_interval: {slow_csv}s", "INPUT")
        
        try:
            # ===== PROCESS: CREATE MANAGER =====
            print("\n" + "-"*40)
            log("CREATING METER MANAGER", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log("Instantiating MeterManager with dual-rate config...", "PROCESS")
            manager = MeterManager(
                [m], 
                ["Time", "Frequency", "Voltage", "No_of_Interruption"],
                fast_poll_interval=fast_poll,
                slow_csv_interval=slow_csv
            )
            manager.csv_path = os.path.join(tmpdir, "test.csv")
            manager.events_path = Path(tmpdir) / "events.csv"
            
            log(f"Manager created successfully", "OUTPUT")
            log(f"  - csv_path: {manager.csv_path}", "OUTPUT")
            log(f"  - events_path: {manager.events_path}", "OUTPUT")
            log(f"  - _last_poll_time: {manager._last_poll_time}", "OUTPUT")
            
            # ===== PROCESS: RAPID POLLING =====
            print("\n" + "-"*40)
            log("PHASE 1: RAPID POLLING (should be throttled)", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Calling read_all() 10 times with 50ms gaps...", "PROCESS")
            log(f"Expected: Most calls throttled, only 1-2 actual meter reads", "PROCESS")
            
            start_time = time.time()
            for i in range(10):
                elapsed = time.time() - start_time
                log(f"  Call {i+1}/10 at t={elapsed:.3f}s", "PROCESS")
                manager.read_all()
                time.sleep(0.05)
            
            total_elapsed = time.time() - start_time
            
            print()
            log(f"Rapid polling complete:", "OUTPUT")
            log(f"  - Total time elapsed: {total_elapsed:.3f}s", "OUTPUT")
            log(f"  - read_all() called: 10 times", "OUTPUT")
            log(f"  - Actual meter reads: {call_count[0]} times", "OUTPUT")
            
            if call_times:
                log(f"  - Meter read timestamps:", "DETAIL")
                for i, t in enumerate(call_times):
                    log(f"      Read {i+1}: t={t - start_time:.3f}s", "DETAIL")
            
            # ===== CHECK 1 =====
            print("\n" + "-"*40)
            log("VERIFICATION CHECK 1: Throttle effectiveness", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Checking: call_count ({call_count[0]}) <= 3", "CHECK")
            log(f"  Rationale: 10 calls in ~500ms with 500ms throttle", "CHECK")
            log(f"             should result in max 1-2 actual reads", "CHECK")
            
            if call_count[0] <= 3:
                log(f"✓ Throttle working: {call_count[0]} calls (expected ≤3)", "PASS")
            else:
                log(f"✗ Throttle failed: {call_count[0]} calls (expected ≤3)", "FAIL")
                return False
            
            # ===== PROCESS: WAIT FOR THROTTLE EXPIRY =====
            print("\n" + "-"*40)
            log("PHASE 2: WAIT FOR THROTTLE TO EXPIRE", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            calls_before_wait = call_count[0]
            log(f"Current call count: {calls_before_wait}", "PROCESS")
            log(f"Waiting {fast_poll}s for throttle to expire...", "PROCESS")
            time.sleep(fast_poll)
            
            log(f"Calling read_all() after throttle expiry...", "PROCESS")
            manager.read_all()
            
            log(f"Call count after wait: {call_count[0]}", "OUTPUT")
            
            # ===== CHECK 2 =====
            print("\n" + "-"*40)
            log("VERIFICATION CHECK 2: Post-throttle read", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Checking: call_count ({call_count[0]}) > calls_before ({calls_before_wait})", "CHECK")
            log(f"  Rationale: After throttle expires, next read_all() should", "CHECK")
            log(f"             actually poll the meter", "CHECK")
            
            if call_count[0] > calls_before_wait:
                log(f"✓ Post-throttle read worked: {calls_before_wait} -> {call_count[0]}", "PASS")
            else:
                log(f"✗ Post-throttle read failed: count unchanged at {call_count[0]}", "FAIL")
                return False
            
            # ===== FINAL RESULT =====
            print("\n" + "="*80)
            log(f"TEST_05 RESULT: ALL CHECKS PASSED", "PASS")
            log(f"  - Throttle correctly limited rapid calls", "INFO")
            log(f"  - Throttle correctly allowed read after interval", "INFO")
            log(f"  - Total actual meter reads: {call_count[0]}", "INFO")
            print("="*80 + "\n")
            return True
            
        except Exception as e:
            print("\n" + "="*80)
            log(f"TEST_05 RESULT: EXCEPTION OCCURRED", "FAIL")
            log(f"  Error: {e}", "FAIL")
            print("="*80)
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_fast_poll_throttling()
    sys.exit(0 if success else 1)
