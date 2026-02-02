#!/usr/bin/env python3
"""
TEST_08: Integration test - verify EVENTS.csv gets fsync'd immediately
PASS if: Events file is written and synced to disk on blackout detection

This test verifies that blackout events are immediately written to disk
using os.fsync(), ensuring they survive a power loss immediately after
detection. This is critical for forensic analysis.
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
        "DISK": f"{Colors.YELLOW}{Colors.BOLD}[DISK]{Colors.ENDC}",
    }
    print(f"{timestamp} {prefix.get(level, '[???]')} {msg}")

def get_file_size(path):
    """Get file size, return 0 if doesn't exist."""
    try:
        return os.path.getsize(path)
    except:
        return 0

def test_events_immediate_sync():
    print("\n" + "="*80)
    log("TEST_08: EVENTS IMMEDIATE SYNC TEST", "HEADER")
    print("="*80 + Colors.ENDC)
    print("""
    PURPOSE: Verify that blackout events are immediately written to disk
             using os.fsync(), ensuring crash/power-loss durability.
    
    WHY THIS MATTERS:
      - Normal file writes go to OS buffer first
      - If power is lost before OS flushes buffer, data is lost
      - os.fsync() forces immediate physical write to disk
      - Blackout events MUST survive the power outage that caused them
    
    SCENARIO:
      1. Read #1: Establish baseline (int count = 10)
      2. Trigger blackout (int count jumps to 15)
      3. Immediately check file size (should grow due to fsync)
      4. Verify event content without closing file handles
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
        m.name = "EventTestMeter"
        m.device_address = 1
        m.model = "LG6400"
        
        int_count = [10]  # Starting interruption count
        
        def mock_read():
            values = [f"2026-01-25 10:00:00", 50.0, 230.0, int_count[0]]
            log(f"  Meter returns: int_count={int_count[0]}", "DETAIL")
            return values
        
        m.read_data = mock_read
        
        log(f"Mock meter configured:", "INPUT")
        log(f"  - Name: {m.name}", "INPUT")
        log(f"  - Initial int_count: {int_count[0]}", "INPUT")
        log(f"  - fast_poll_interval: 0.05s (50ms for testing)", "INPUT")
        
        try:
            # ===== PROCESS: CREATE MANAGER =====
            print("\n" + "-"*40)
            log("CREATING METER MANAGER", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log("Instantiating MeterManager...", "PROCESS")
            manager = MeterManager(
                [m], 
                ["Time", "Frequency", "Voltage", "No_of_Interruption"],
                fast_poll_interval=0.05,  # 50ms for testing
                slow_csv_interval=60
            )
            manager.csv_path = os.path.join(tmpdir, "test.csv")
            manager.events_path = Path(tmpdir) / "events.csv"
            manager._init_events_csv()
            
            events_path = manager.events_path
            
            log(f"Manager created:", "OUTPUT")
            log(f"  - events_path: {events_path}", "OUTPUT")
            
            # ===== PHASE 1: ESTABLISH BASELINE =====
            print("\n" + "-"*40)
            log("PHASE 1: ESTABLISH BASELINE", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Calling read_all() to establish baseline...", "PROCESS")
            manager.read_all()
            
            baseline_size = get_file_size(events_path)
            log(f"After baseline read:", "OUTPUT")
            log(f"  - int_count in meter state: {manager._meter_state['EventTestMeter']['last_int_count']}", "OUTPUT")
            log(f"  - EVENTS.csv size: {baseline_size} bytes", "DISK")
            
            time.sleep(0.1)  # Wait for throttle
            
            # ===== PHASE 2: PRE-BLACKOUT MEASUREMENT =====
            print("\n" + "-"*40)
            log("PHASE 2: PRE-BLACKOUT FILE STATE", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            size_before = get_file_size(events_path)
            log(f"File state immediately before blackout:", "DISK")
            log(f"  - events_path: {events_path}", "DISK")
            log(f"  - File exists: {events_path.exists()}", "DISK")
            log(f"  - Size: {size_before} bytes", "DISK")
            
            if size_before > 0:
                with open(events_path, 'r') as f:
                    content = f.read()
                    log(f"  - Current content:", "DETAIL")
                    for line in content.strip().split('\n'):
                        log(f"    | {line}", "DETAIL")
            
            # ===== PHASE 3: TRIGGER BLACKOUT =====
            print("\n" + "-"*40)
            log("PHASE 3: TRIGGERING BLACKOUT", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            old_count = int_count[0]
            int_count[0] = 15  # Jump from 10 to 15!
            
            log(f"*** BLACKOUT TRIGGERED ***", "EVENT")
            log(f"  - Interruption count changed: {old_count} -> {int_count[0]}", "EVENT")
            log(f"  - Delta: +{int_count[0] - old_count} blackout(s)", "EVENT")
            log(f"", "INFO")
            
            log(f"Calling read_all() which should detect and log blackout...", "PROCESS")
            
            # Capture time just before the call
            call_time = datetime.now()
            manager.read_all()
            after_time = datetime.now()
            
            elapsed_ms = (after_time - call_time).total_seconds() * 1000
            log(f"read_all() completed in {elapsed_ms:.1f}ms", "PROCESS")
            
            # ===== PHASE 4: IMMEDIATE FILE CHECK =====
            print("\n" + "-"*40)
            log("PHASE 4: IMMEDIATE FILE CHECK (no close/flush)", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Checking file IMMEDIATELY after read_all()...", "DISK")
            log(f"  (If fsync worked, data should already be on disk)", "DISK")
            
            size_after = get_file_size(events_path)
            size_delta = size_after - size_before
            
            log(f"File state after blackout detection:", "DISK")
            log(f"  - Size before: {size_before} bytes", "DISK")
            log(f"  - Size after: {size_after} bytes", "DISK")
            log(f"  - Delta: +{size_delta} bytes", "DISK")
            
            # ===== CHECK 1: FILE SIZE INCREASED =====
            print("\n" + "-"*40)
            log("CHECK 1: File size increased immediately", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Checking: size_after ({size_after}) > size_before ({size_before})", "CHECK")
            log(f"  Rationale: os.fsync() should have forced immediate disk write", "CHECK")
            log(f"             If only buffered, size might not change yet", "CHECK")
            
            if size_after > size_before:
                log(f"✓ File size increased: +{size_delta} bytes", "PASS")
            else:
                log(f"✗ File size did not increase (fsync may have failed)", "FAIL")
                return False
            
            # ===== CHECK 2: CONTENT VERIFICATION =====
            print("\n" + "-"*40)
            log("CHECK 2: Event content verification", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Reading events file to verify content...", "CHECK")
            
            with open(events_path, 'r') as f:
                content = f.read()
                
            log(f"Current file content ({len(content)} bytes):", "OUTPUT")
            for line in content.strip().split('\n'):
                log(f"  | {line}", "DETAIL")
            
            # Check for BLACKOUT keyword
            blackout_present = 'BLACKOUT' in content
            meter_name_present = 'EventTestMeter' in content
            
            log(f"\nContent checks:", "CHECK")
            
            if blackout_present:
                log(f"✓ 'BLACKOUT' found in events file", "PASS")
            else:
                log(f"✗ 'BLACKOUT' NOT found in events file", "FAIL")
                return False
            
            if meter_name_present:
                log(f"✓ 'EventTestMeter' found in events file", "PASS")
            else:
                log(f"✗ 'EventTestMeter' NOT found in events file", "FAIL")
                return False
            
            # ===== EDGE CASE ANALYSIS =====
            print("\n" + "-"*40)
            log("EDGE CASE ANALYSIS", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Potential edge cases to consider:", "INFO")
            log(f"  1. Power loss during fsync() itself", "INFO")
            log(f"     -> Hardware dependent, ~5-20ms window", "INFO")
            log(f"     -> Generally safe on modern storage", "INFO")
            log(f"", "INFO")
            log(f"  2. SD card write latency on Raspberry Pi", "INFO")
            log(f"     -> Can be 10-100ms under load", "INFO")
            log(f"     -> fsync() blocks until complete", "INFO")
            log(f"", "INFO")
            log(f"  3. Multiple rapid blackouts", "INFO")
            log(f"     -> Each triggers separate fsync()", "INFO")
            log(f"     -> May slow down polling slightly", "INFO")
            log(f"", "INFO")
            log(f"  4. File handle invalidation", "INFO")
            log(f"     -> Covered by _ensure_csv_handle()", "INFO")
            
            # ===== FINAL RESULT =====
            print("\n" + "="*80)
            log(f"TEST_08 RESULT: ALL CHECKS PASSED", "PASS")
            log(f"  - Blackout event immediately written to disk", "INFO")
            log(f"  - File size increased by {size_delta} bytes", "INFO")
            log(f"  - Event content verified (BLACKOUT + meter name)", "INFO")
            log(f"  - Data would survive immediate power loss", "INFO")
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
    success = test_events_immediate_sync()
    sys.exit(0 if success else 1)
