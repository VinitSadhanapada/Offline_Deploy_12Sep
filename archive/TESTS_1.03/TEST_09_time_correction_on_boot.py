#!/usr/bin/env python3
"""
TEST_09: System time wrong on boot, verify correction to RTC.

SCENARIO:
  - Mock RTC returning correct time (2026)
  - Mock system time being wrong (very different from RTC)
  - Verify that:
    1. Time correction is detected (offset > 1 second)
    2. System time would be corrected to RTC
    3. Event is logged

PASS if: Time correction detected, correction attempted, event logged
"""
import sys
import os
import tempfile
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

def test_time_correction():
    print("\n" + "="*80)
    log("TEST_09: TIME CORRECTION ON BOOT TEST", "HEADER")
    print("="*80 + Colors.ENDC)
    print("""
    PURPOSE: Verify that when system time differs from RTC by > 1 second,
             the system time is corrected to match RTC.
    
    SCENARIO:
      1. Mock RTC returning correct time (2026-01-25 14:30:00)
      2. Mock system datetime.now() returning wrong time (5 hours behind)
      3. Call validate_and_correct()
      4. Verify correction is detected and attempted
    """)
    
    from src.utils.time_sanitizer import RTCTimeSanitizer
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, "rtc_state.json")
        
        # ===== SETUP =====
        print("\n" + "-"*40)
        log("SETUP: CREATING TIME SANITIZER", "HEADER")
        print("-"*40 + Colors.ENDC)
        
        sanitizer = RTCTimeSanitizer(state_file_path=state_file)
        log(f"Sanitizer created", "OUTPUT")
        
        # ===== DEFINE TEST TIMES =====
        print("\n" + "-"*40)
        log("DEFINING TEST TIMES", "HEADER")
        print("-"*40 + Colors.ENDC)
        
        rtc_time = datetime(2026, 1, 25, 14, 30, 0)
        wrong_system_time = datetime(2026, 1, 25, 9, 30, 0)  # 5 hours behind
        expected_offset = abs((wrong_system_time - rtc_time).total_seconds())
        
        log(f"RTC time (correct):    {rtc_time}", "INPUT")
        log(f"System time (wrong):   {wrong_system_time}", "INPUT")
        log(f"Expected offset:       {expected_offset} seconds ({expected_offset/3600:.1f} hours)", "INPUT")
        
        try:
            # ===== MOCK RTC AND SYSTEM TIME =====
            print("\n" + "-"*40)
            log("APPLYING MOCKS AND RUNNING VALIDATION", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            # Force hwclock_available=True so RTC validation runs
            sanitizer.hwclock_available = True
            
            with patch.object(sanitizer, 'get_rtc_time', return_value=rtc_time):
                # We need to mock datetime.now() inside the module
                # Since we import datetime at module level, we patch it in time_sanitizer
                original_datetime = datetime
                
                class MockDatetime:
                    @classmethod
                    def now(cls):
                        return wrong_system_time
                    
                    @classmethod
                    def fromisoformat(cls, s):
                        return original_datetime.fromisoformat(s)
                    
                    @classmethod
                    def strptime(cls, s, fmt):
                        return original_datetime.strptime(s, fmt)
                
                with patch('src.utils.time_sanitizer.datetime', MockDatetime):
                    with patch.object(sanitizer, 'sync_system_to_rtc') as mock_sync:
                        mock_sync.return_value = True
                        
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
                        
                        # ===== CHECK 1: Time correction detected =====
                        print("\n" + "-"*40)
                        log("CHECK 1: Time correction detection", "HEADER")
                        print("-"*40 + Colors.ENDC)
                        
                        corr_events = [e for e in events if e['type'] == 'TIME_CORRECTION']
                        log(f"Looking for TIME_CORRECTION event...", "CHECK")
                        
                        if len(corr_events) >= 1:
                            log(f"✓ Time correction detected", "PASS")
                            event = corr_events[0]
                            log(f"  System was: {event.get('system_was')}", "DETAIL")
                            log(f"  RTC is: {event.get('rtc_is')}", "DETAIL")
                            log(f"  Offset: {event.get('offset_sec')} seconds", "DETAIL")
                        else:
                            log(f"✗ Time correction NOT detected", "FAIL")
                            log(f"  Events found: {[e['type'] for e in events]}", "DETAIL")
                            return False
                        
                        # ===== CHECK 2: Offset is significant =====
                        print("\n" + "-"*40)
                        log("CHECK 2: Offset magnitude", "HEADER")
                        print("-"*40 + Colors.ENDC)
                        
                        actual_offset = corr_events[0].get('offset_sec', 0)
                        log(f"Checking offset magnitude...", "CHECK")
                        log(f"  Expected: ~{expected_offset} seconds", "CHECK")
                        log(f"  Actual: {actual_offset} seconds", "CHECK")
                        
                        # Allow some tolerance due to test execution time
                        if abs(actual_offset - expected_offset) < 10:
                            log(f"✓ Offset matches expected value", "PASS")
                        else:
                            log(f"✗ Offset doesn't match (tolerance: 10s)", "FAIL")
                            return False
                        
                        # ===== CHECK 3: Sync was called =====
                        print("\n" + "-"*40)
                        log("CHECK 3: RTC sync call", "HEADER")
                        print("-"*40 + Colors.ENDC)
                        
                        log(f"Checking if sync_system_to_rtc was called...", "CHECK")
                        
                        if mock_sync.called:
                            log(f"✓ sync_system_to_rtc was called", "PASS")
                        else:
                            log(f"✗ sync_system_to_rtc was NOT called", "FAIL")
                            return False
            
            # ===== FINAL RESULT =====
            print("\n" + "="*80)
            log("TEST_09 RESULT: ALL CHECKS PASSED", "PASS")
            print("="*80 + "\n")
            return True
            
        except Exception as e:
            print("\n" + "="*80)
            log(f"TEST_09 RESULT: EXCEPTION OCCURRED", "FAIL")
            log(f"  Error: {e}", "FAIL")
            print("="*80)
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_time_correction()
    sys.exit(0 if success else 1)
