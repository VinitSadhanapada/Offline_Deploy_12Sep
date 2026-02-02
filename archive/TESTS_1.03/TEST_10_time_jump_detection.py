#!/usr/bin/env python3
"""
TEST_10: Detect >1 hour time jump between readings.

SCENARIO:
  - Test check_discontinuity() with various time gaps
  - Should NOT trigger for gaps < 1 hour
  - Should trigger for gaps > 1 hour (forward or backward)

PASS if: All gap detection cases work correctly
"""
import sys
from datetime import datetime
from pathlib import Path

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

def test_time_jump_detection():
    print("\n" + "="*80)
    log("TEST_10: TIME JUMP DETECTION TEST", "HEADER")
    print("="*80 + Colors.ENDC)
    print("""
    PURPOSE: Verify check_discontinuity() correctly detects time jumps > 1 hour.
    
    TEST CASES:
      1. 30 minute gap (normal) -> NO event
      2. 59 minute gap (edge case) -> NO event
      3. 61 minute gap (just over threshold) -> event
      4. 2 hour forward jump -> event
      5. 3 hour backward jump -> event
      6. None timestamps -> NO event (graceful handling)
    """)
    
    from src.utils.time_sanitizer import RTCTimeSanitizer
    
    sanitizer = RTCTimeSanitizer(state_file_path="/tmp/test_rtc_jump.json")
    
    test_cases = [
        {
            "name": "30 minute gap (normal)",
            "last": "2026-01-25 11:30:00",
            "current": "2026-01-25 12:00:00",
            "expect_event": False,
        },
        {
            "name": "59 minute gap (edge - under threshold)",
            "last": "2026-01-25 12:00:00",
            "current": "2026-01-25 12:59:00",
            "expect_event": False,
        },
        {
            "name": "61 minute gap (just over threshold)",
            "last": "2026-01-25 12:00:00",
            "current": "2026-01-25 13:01:00",
            "expect_event": True,
            "expected_hours": 1.02,
        },
        {
            "name": "2 hour forward jump",
            "last": "2026-01-25 12:00:00",
            "current": "2026-01-25 14:00:00",
            "expect_event": True,
            "expected_hours": 2.0,
            "expected_direction": "forward",
        },
        {
            "name": "3 hour backward jump",
            "last": "2026-01-25 15:00:00",
            "current": "2026-01-25 12:00:00",
            "expect_event": True,
            "expected_hours": 3.0,
            "expected_direction": "backward",
        },
        {
            "name": "None last timestamp (first reading)",
            "last": None,
            "current": "2026-01-25 12:00:00",
            "expect_event": False,
        },
        {
            "name": "None current timestamp",
            "last": "2026-01-25 12:00:00",
            "current": None,
            "expect_event": False,
        },
        {
            "name": "Invalid timestamp format",
            "last": "2026-01-25 12:00:00",
            "current": "invalid-time",
            "expect_event": False,
        },
    ]
    
    all_passed = True
    
    for i, tc in enumerate(test_cases, 1):
        print("\n" + "-"*40)
        log(f"TEST CASE {i}: {tc['name']}", "HEADER")
        print("-"*40 + Colors.ENDC)
        
        log(f"Last timestamp:    {tc['last']}", "INPUT")
        log(f"Current timestamp: {tc['current']}", "INPUT")
        log(f"Expect event:      {tc['expect_event']}", "INPUT")
        
        log("Calling check_discontinuity()...", "PROCESS")
        event = sanitizer.check_discontinuity(tc['current'], tc['last'])
        
        log(f"Returned event: {event}", "OUTPUT")
        
        if tc['expect_event']:
            # Should have returned an event
            if event is None:
                log(f"✗ FAILED: Expected event but got None", "FAIL")
                all_passed = False
                continue
            
            log(f"✓ Event detected as expected", "PASS")
            log(f"  Type: {event.get('type')}", "DETAIL")
            log(f"  Hours: {event.get('hours')}", "DETAIL")
            log(f"  Direction: {event.get('direction', 'N/A')}", "DETAIL")
            
            # Verify event type
            if event.get('type') != 'TIME_JUMP':
                log(f"✗ FAILED: Expected type TIME_JUMP, got {event.get('type')}", "FAIL")
                all_passed = False
                continue
            
            # Verify hours if specified
            if 'expected_hours' in tc:
                actual_hours = event.get('hours', 0)
                if abs(actual_hours - tc['expected_hours']) > 0.1:
                    log(f"✗ FAILED: Expected {tc['expected_hours']} hours, got {actual_hours}", "FAIL")
                    all_passed = False
                    continue
                log(f"✓ Hours value correct: {actual_hours}", "PASS")
            
            # Verify direction if specified
            if 'expected_direction' in tc:
                actual_dir = event.get('direction')
                if actual_dir != tc['expected_direction']:
                    log(f"✗ FAILED: Expected direction '{tc['expected_direction']}', got '{actual_dir}'", "FAIL")
                    all_passed = False
                    continue
                log(f"✓ Direction correct: {actual_dir}", "PASS")
        else:
            # Should NOT have returned an event
            if event is not None:
                log(f"✗ FAILED: Expected None but got event: {event}", "FAIL")
                all_passed = False
                continue
            log(f"✓ No event as expected (gap within threshold)", "PASS")
    
    # ===== TEST is_timestamp_sane() =====
    print("\n" + "-"*40)
    log("BONUS: Testing is_timestamp_sane()", "HEADER")
    print("-"*40 + Colors.ENDC)
    
    # Use relative timestamps for sanity checks
    from datetime import timedelta
    now = datetime.now()
    valid_ts = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    old_ts = "2020-01-01 12:00:00"
    future_ts = (now + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    
    sanity_cases = [
        (valid_ts, True, "Valid current timestamp (1 hour ago)"),
        (old_ts, False, "Year before 2024"),
        (future_ts, False, "Far future (> 1 day ahead)"),
        ("invalid", False, "Invalid format"),
    ]
    
    for ts, expect_sane, desc in sanity_cases:
        is_sane, reason = sanitizer.is_timestamp_sane(ts)
        log(f"  {desc}: is_sane={is_sane}, reason={reason}", "OUTPUT")
        
        if is_sane != expect_sane:
            log(f"    ✗ Expected is_sane={expect_sane}", "FAIL")
            all_passed = False
        else:
            log(f"    ✓ Correct", "PASS")
    
    # ===== FINAL RESULT =====
    print("\n" + "="*80)
    if all_passed:
        log("TEST_10 RESULT: ALL CHECKS PASSED", "PASS")
    else:
        log("TEST_10 RESULT: SOME CHECKS FAILED", "FAIL")
    print("="*80 + "\n")
    
    return all_passed

if __name__ == "__main__":
    success = test_time_jump_detection()
    sys.exit(0 if success else 1)
