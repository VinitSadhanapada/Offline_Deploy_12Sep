#!/usr/bin/env python3
"""
TEST_08: Simulate RTC battery failure (year 2000) and verify recovery from state file.

SCENARIO:
  - Pre-populate state file with "last known good" time (simulating previous run)
  - Mock RTC returning year 2000 (dead battery symptom)
  - Verify that:
    1. Battery failure is detected
    2. System time is restored from state file
    3. Events are logged correctly

PASS if: Battery fail detected, time restored from state, events logged
"""
import sys
import os
import tempfile
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

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

def test_rtc_battery_fail_recovery():
    print("\n" + "="*80)
    log("TEST_08: RTC BATTERY FAILURE RECOVERY TEST", "HEADER")
    print("="*80 + Colors.ENDC)
    print("""
    PURPOSE: Verify that when RTC battery dies (returns year 2000),
             the system can recover time from the state file.
    
    SCENARIO:
      1. Pre-populate state file with known good time
      2. Mock RTC returning year 2000 (dead battery)
      3. Call validate_and_correct()
      4. Verify battery failure detected and time restored
    """)
    
    from src.utils.time_sanitizer import RTCTimeSanitizer
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, "rtc_state.json")
        
        # ===== SETUP: Pre-populate state file =====
        print("\n" + "-"*40)
        log("SETUP: PRE-POPULATING STATE FILE", "HEADER")
        print("-"*40 + Colors.ENDC)
        
        last_good = "2026-01-25 10:00:00"
        initial_state = {
            "last_known_good_time": last_good,
            "rtc_battery_ok": True,
            "last_boot_time": "2026-01-24 08:00:00"
        }
        
        with open(state_file, 'w') as f:
            json.dump(initial_state, f, indent=2)
        
        log(f"State file created: {state_file}", "OUTPUT")
        log(f"  last_known_good_time: {last_good}", "INPUT")
        log(f"  rtc_battery_ok: True", "INPUT")
        
        # ===== INITIALIZE SANITIZER =====
        print("\n" + "-"*40)
        log("INITIALIZING TIME SANITIZER", "HEADER")
        print("-"*40 + Colors.ENDC)
        
        sanitizer = RTCTimeSanitizer(state_file_path=state_file)
        log(f"Sanitizer created, state loaded", "OUTPUT")
        log(f"  Loaded state: {sanitizer.state}", "DETAIL")
        
        # ===== MOCK RTC RETURNING YEAR 2000 =====
        print("\n" + "-"*40)
        log("SIMULATING RTC BATTERY FAILURE", "HEADER")
        print("-"*40 + Colors.ENDC)
        
        dead_battery_time = datetime(2000, 1, 1, 0, 0, 0)
        log(f"Mocking RTC to return: {dead_battery_time}", "INPUT")
        log(f"  Year {dead_battery_time.year} < 2024 indicates dead battery", "DETAIL")
        
        try:
            # Force hwclock_available=True so RTC validation runs
            sanitizer.hwclock_available = True
            
            with patch.object(sanitizer, 'get_rtc_time', return_value=dead_battery_time):
                with patch.object(sanitizer, 'set_system_time') as mock_set:
                    
                    log("Calling validate_and_correct()...", "PROCESS")
                    is_valid, events = sanitizer.validate_and_correct()
                    
                    # ===== ANALYZE RESULTS =====
                    print("\n" + "-"*40)
                    log("ANALYZING RESULTS", "HEADER")
                    print("-"*40 + Colors.ENDC)
                    
                    log(f"is_valid returned: {is_valid}", "OUTPUT")
                    log(f"Number of events: {len(events)}", "OUTPUT")
                    
                    for i, event in enumerate(events):
                        log(f"  Event {i+1}: {event['type']}", "OUTPUT")
                        for k, v in event.items():
                            if k != 'type':
                                log(f"    {k}: {v}", "DETAIL")
                    
                    # ===== CHECK 1: Battery failure detected =====
                    print("\n" + "-"*40)
                    log("CHECK 1: Battery failure detection", "HEADER")
                    print("-"*40 + Colors.ENDC)
                    
                    fail_events = [e for e in events if e['type'] == 'RTC_BATTERY_FAIL']
                    log(f"Looking for RTC_BATTERY_FAIL event...", "CHECK")
                    
                    if len(fail_events) == 1:
                        log(f"✓ Battery failure detected", "PASS")
                        log(f"  RTC reading was: {fail_events[0]['rtc_reading']}", "DETAIL")
                    else:
                        log(f"✗ Battery failure NOT detected (found {len(fail_events)} events)", "FAIL")
                        return False
                    
                    # ===== CHECK 2: Time restored from state =====
                    print("\n" + "-"*40)
                    log("CHECK 2: Time restoration from state file", "HEADER")
                    print("-"*40 + Colors.ENDC)
                    
                    restore_events = [e for e in events if e['type'] == 'TIME_RESTORED']
                    log(f"Looking for TIME_RESTORED event...", "CHECK")
                    
                    if len(restore_events) == 1:
                        restored_to = restore_events[0]['restored_to']
                        log(f"✓ Time restored", "PASS")
                        log(f"  Restored to: {restored_to}", "DETAIL")
                        log(f"  Source: {restore_events[0].get('source', 'unknown')}", "DETAIL")
                        
                        if restored_to == last_good:
                            log(f"✓ Restored time matches last_known_good_time", "PASS")
                        else:
                            log(f"✗ Restored time doesn't match expected", "FAIL")
                            log(f"  Expected: {last_good}", "DETAIL")
                            log(f"  Got: {restored_to}", "DETAIL")
                            return False
                    else:
                        log(f"✗ Time NOT restored (found {len(restore_events)} events)", "FAIL")
                        return False
                    
                    # ===== CHECK 3: set_system_time was called =====
                    print("\n" + "-"*40)
                    log("CHECK 3: System time set call", "HEADER")
                    print("-"*40 + Colors.ENDC)
                    
                    log(f"Checking if set_system_time was called...", "CHECK")
                    
                    if mock_set.called:
                        log(f"✓ set_system_time was called", "PASS")
                        call_args = mock_set.call_args
                        log(f"  Called with: {call_args}", "DETAIL")
                    else:
                        log(f"✗ set_system_time was NOT called", "FAIL")
                        return False
                    
                    # ===== CHECK 4: State updated =====
                    print("\n" + "-"*40)
                    log("CHECK 4: State file updated", "HEADER")
                    print("-"*40 + Colors.ENDC)
                    
                    log(f"Checking sanitizer.state after validation...", "CHECK")
                    log(f"  rtc_battery_ok: {sanitizer.state.get('rtc_battery_ok')}", "OUTPUT")
                    
                    if sanitizer.state.get('rtc_battery_ok') == False:
                        log(f"✓ State correctly reflects battery failure", "PASS")
                    else:
                        log(f"✗ State should show rtc_battery_ok=False", "FAIL")
                        return False
                    
            # ===== FINAL RESULT =====
            print("\n" + "="*80)
            log("TEST_08 RESULT: ALL CHECKS PASSED", "PASS")
            print("="*80 + "\n")
            return True
            
        except Exception as e:
            print("\n" + "="*80)
            log(f"TEST_08 RESULT: EXCEPTION OCCURRED", "FAIL")
            log(f"  Error: {e}", "FAIL")
            print("="*80)
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_rtc_battery_fail_recovery()
    sys.exit(0 if success else 1)
