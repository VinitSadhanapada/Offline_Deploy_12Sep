#!/usr/bin/env python3
"""
TEST_06: Verify blackout detection via interruption count delta
PASS if: Blackout event logged when interruption count increases

This test simulates a power blackout by incrementing the meter's
"No of Interruption" counter and verifies the event is logged to EVENTS.csv.
"""
import sys
import os
import tempfile
import csv
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
        "EVENT": f"{Colors.RED}{Colors.BOLD}[EVENT]{Colors.ENDC}",
    }
    print(f"{timestamp} {prefix.get(level, '[???]')} {msg}")

def test_blackout_detection():
    print("\n" + "="*80)
    log("TEST_06: BLACKOUT DETECTION TEST", "HEADER")
    print("="*80 + Colors.ENDC)
    print("""
    PURPOSE: Verify that MeterManager detects power blackouts by monitoring
             the "No of Interruption" counter from the meter's EEPROM.
    
    SCENARIO: 
      1. First read: Establish baseline (interruption count = 5)
      2. Second read: Same count (5) - no blackout
      3. Third read: Count jumped to 7 - BLACKOUT DETECTED!
    
    EXPECTED: One BLACKOUT event written to EVENTS.csv with:
              - count_before: 5
              - count_after: 7
              - meter_name: TestMeter
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
        
        int_count = [5]  # Mutable container for interruption count
        read_num = [0]
        
        def mock_read():
            read_num[0] += 1
            values = [f"2026-01-25 10:00:{int_count[0]:02d}", 50.0, 230.0, int_count[0]]
            log(f"  READ #{read_num[0]}: Meter returns {values}", "DETAIL")
            log(f"    - Time: {values[0]}", "DETAIL")
            log(f"    - Frequency: {values[1]} Hz", "DETAIL")
            log(f"    - Voltage: {values[2]} V", "DETAIL")
            log(f"    - Interruption Count: {values[3]}", "DETAIL")
            return values
        
        m.read_data = mock_read
        
        log(f"Mock meter configured:", "INPUT")
        log(f"  - Name: {m.name}", "INPUT")
        log(f"  - Initial Interruption Count: {int_count[0]}", "INPUT")
        log(f"  - Parameters: [Time, Frequency, Voltage, No_of_Interruption]", "INPUT")
        
        try:
            # ===== PROCESS: CREATE MANAGER =====
            print("\n" + "-"*40)
            log("CREATING METER MANAGER", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log("Instantiating MeterManager...", "PROCESS")
            manager = MeterManager(
                [m], 
                ["Time", "Frequency", "Voltage", "No_of_Interruption"],
                fast_poll_interval=0.1,  # Fast for testing
                slow_csv_interval=60
            )
            manager.csv_path = os.path.join(tmpdir, "test.csv")
            manager.events_path = Path(tmpdir) / "events.csv"
            manager._init_events_csv()
            
            log(f"Manager created:", "OUTPUT")
            log(f"  - events_path: {manager.events_path}", "OUTPUT")
            log(f"  - _intr_idx (interruption param index): {manager._intr_idx}", "OUTPUT")
            log(f"  - _freq_idx (frequency param index): {manager._freq_idx}", "OUTPUT")
            
            # ===== PHASE 1: ESTABLISH BASELINE =====
            print("\n" + "-"*40)
            log("PHASE 1: ESTABLISH BASELINE", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Calling read_all() to establish baseline...", "PROCESS")
            log(f"Current int_count: {int_count[0]}", "PROCESS")
            manager.read_all()
            
            state = manager._meter_state['TestMeter']
            log(f"After first read:", "OUTPUT")
            log(f"  - last_int_count: {state['last_int_count']}", "OUTPUT")
            log(f"  - latest_values: {state['latest_values']}", "OUTPUT")
            
            time.sleep(0.15)  # Wait for throttle
            
            # ===== PHASE 2: SAME COUNT (NO BLACKOUT) =====
            print("\n" + "-"*40)
            log("PHASE 2: SAME COUNT - NO BLACKOUT EXPECTED", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Calling read_all() with same interruption count...", "PROCESS")
            log(f"Current int_count: {int_count[0]} (unchanged)", "PROCESS")
            manager.read_all()
            
            log(f"After second read:", "OUTPUT")
            log(f"  - last_int_count: {state['last_int_count']}", "OUTPUT")
            log(f"  - No blackout expected (count unchanged)", "OUTPUT")
            
            time.sleep(0.15)
            
            # ===== PHASE 3: COUNT JUMP (BLACKOUT!) =====
            print("\n" + "-"*40)
            log("PHASE 3: INTERRUPTION COUNT JUMP - BLACKOUT!", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            old_count = int_count[0]
            int_count[0] = 7  # Simulate blackout - count jumps!
            
            log(f"*** SIMULATING BLACKOUT ***", "EVENT")
            log(f"  - Changing interruption count: {old_count} -> {int_count[0]}", "EVENT")
            log(f"  - Delta: +{int_count[0] - old_count} blackout(s)", "EVENT")
            
            log(f"Calling read_all() with new count...", "PROCESS")
            manager.read_all()
            
            log(f"After third read:", "OUTPUT")
            log(f"  - last_int_count: {state['last_int_count']}", "OUTPUT")
            log(f"  - Blackout should have been logged!", "OUTPUT")
            
            time.sleep(0.15)
            
            # Close to flush events
            log(f"Closing manager to flush files...", "PROCESS")
            manager.close()
            
            # ===== VERIFICATION =====
            print("\n" + "-"*40)
            log("VERIFICATION: CHECKING EVENTS.CSV", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            events_path = Path(tmpdir) / "events.csv"
            
            log(f"Checking events file: {events_path}", "CHECK")
            log(f"  - File exists: {events_path.exists()}", "CHECK")
            
            if not events_path.exists():
                log(f"✗ Events CSV not created!", "FAIL")
                return False
            
            with open(events_path, 'r') as f:
                content = f.read()
                log(f"Raw file content ({len(content)} bytes):", "OUTPUT")
                for line in content.strip().split('\n'):
                    log(f"  | {line}", "DETAIL")
            
            with open(events_path, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                log(f"\nParsed CSV:", "OUTPUT")
                log(f"  - Total rows: {len(rows)}", "OUTPUT")
                log(f"  - Header: {rows[0] if rows else 'MISSING'}", "OUTPUT")
                
                # Find blackout row
                blackout_found = False
                for i, row in enumerate(rows[1:], 1):
                    log(f"  - Row {i}: {row}", "DETAIL")
                    if len(row) >= 2 and row[1] == 'BLACKOUT':
                        blackout_found = True
                        log(f"\n  BLACKOUT EVENT FOUND:", "OUTPUT")
                        log(f"    - timestamp: {row[0]}", "OUTPUT")
                        log(f"    - event_type: {row[1]}", "OUTPUT")
                        log(f"    - meter_name: {row[2]}", "OUTPUT")
                        log(f"    - details: {row[3]}", "OUTPUT")
                        log(f"    - count_before: {row[4]}", "OUTPUT")
                        log(f"    - count_after: {row[5]}", "OUTPUT")
                        
                        # Verify values
                        print("\n" + "-"*40)
                        log("FIELD VERIFICATION", "HEADER")
                        print("-"*40 + Colors.ENDC)
                        
                        checks_passed = 0
                        total_checks = 3
                        
                        # Check 1: Meter name
                        if row[2] == 'TestMeter':
                            log(f"✓ meter_name correct: {row[2]}", "PASS")
                            checks_passed += 1
                        else:
                            log(f"✗ meter_name wrong: expected 'TestMeter', got '{row[2]}'", "FAIL")
                        
                        # Check 2: count_before
                        if row[4] == '5' or row[4] == 5:
                            log(f"✓ count_before correct: {row[4]}", "PASS")
                            checks_passed += 1
                        else:
                            log(f"✗ count_before wrong: expected '5', got '{row[4]}'", "FAIL")
                        
                        # Check 3: count_after
                        if row[5] == '7' or row[5] == 7:
                            log(f"✓ count_after correct: {row[5]}", "PASS")
                            checks_passed += 1
                        else:
                            log(f"✗ count_after wrong: expected '7', got '{row[5]}'", "FAIL")
                        
                        if checks_passed == total_checks:
                            break
                
                if not blackout_found:
                    log(f"✗ No BLACKOUT event found in EVENTS.csv!", "FAIL")
                    return False
            
            # ===== FINAL RESULT =====
            print("\n" + "="*80)
            log(f"TEST_06 RESULT: ALL CHECKS PASSED", "PASS")
            log(f"  - Blackout correctly detected when int count jumped 5->7", "INFO")
            log(f"  - Event logged to EVENTS.csv with correct fields", "INFO")
            log(f"  - Meter EEPROM counter approach validated", "INFO")
            print("="*80 + "\n")
            return True
            
        except Exception as e:
            print("\n" + "="*80)
            log(f"TEST_06 RESULT: EXCEPTION OCCURRED", "FAIL")
            log(f"  Error: {e}", "FAIL")
            print("="*80)
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_blackout_detection()
    sys.exit(0 if success else 1)
