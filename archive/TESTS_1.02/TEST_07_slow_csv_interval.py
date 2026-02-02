#!/usr/bin/env python3
"""
TEST_07: Verify slow CSV write interval (60s default)
PASS if: CSV writes only happen at slow_csv_interval, not every poll

This test verifies the dual-rate architecture where fast polling (0.5s)
happens for blackout detection, but CSV writes only occur every 60s
to keep file sizes manageable.
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
        "CSV": f"{Colors.YELLOW}[CSV]{Colors.ENDC}",
    }
    print(f"{timestamp} {prefix.get(level, '[???]')} {msg}")

def count_csv_rows(path):
    """Count rows in CSV file."""
    try:
        with open(path, 'r') as f:
            return len(list(csv.reader(f)))
    except:
        return 0

def test_slow_csv_interval():
    print("\n" + "="*80)
    log("TEST_07: SLOW CSV WRITE INTERVAL TEST", "HEADER")
    print("="*80 + Colors.ENDC)
    print("""
    PURPOSE: Verify that DATA_ALL.csv writes only happen at the slow_csv_interval
             (default 60s), not on every fast poll (0.5s).
    
    SCENARIO: Using shortened intervals for testing:
      - fast_poll_interval: 0.1s (100ms)
      - slow_csv_interval: 0.5s (500ms)
    
    EXPECTED:
      1. First read_all() triggers CSV write (interval elapsed)
      2. Rapid subsequent reads do NOT write to CSV
      3. After 500ms passes, next read_all() writes to CSV
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
        
        read_count = [0]
        def mock_read():
            read_count[0] += 1
            return [f"2026-01-25 10:00:{read_count[0]:02d}", 50.0, 230.0, 0]
        
        m.read_data = mock_read
        
        fast_poll = 0.1   # 100ms for testing
        slow_csv = 1.0    # 1000ms for testing (longer to avoid race condition)
        
        log(f"Mock meter configured:", "INPUT")
        log(f"  - Name: {m.name}", "INPUT")
        log(f"  - Returns incrementing timestamps", "INPUT")
        
        log(f"Timing configuration (shortened for testing):", "INPUT")
        log(f"  - fast_poll_interval: {fast_poll}s (100ms)", "INPUT")
        log(f"  - slow_csv_interval: {slow_csv}s (1000ms)", "INPUT")
        
        try:
            # ===== PROCESS: CREATE MANAGER =====
            print("\n" + "-"*40)
            log("CREATING METER MANAGER", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            csv_path = os.path.join(tmpdir, "test.csv")
            
            log("Instantiating MeterManager...", "PROCESS")
            manager = MeterManager(
                [m], 
                ["Time", "Frequency", "Voltage", "No_of_Interruption"],
                fast_poll_interval=fast_poll,
                slow_csv_interval=slow_csv
            )
            manager.csv_path = csv_path
            manager.events_path = Path(tmpdir) / "events.csv"
            
            # Force CSV write on first call by setting last write time to past
            log(f"Setting _last_csv_write_time to past (forcing first write)...", "PROCESS")
            manager._last_csv_write_time = time.time() - 1
            
            log(f"Manager created:", "OUTPUT")
            log(f"  - csv_path: {csv_path}", "OUTPUT")
            log(f"  - _last_csv_write_time: {manager._last_csv_write_time} (1s in past)", "OUTPUT")
            
            # ===== PHASE 1: FIRST READ (SHOULD WRITE) =====
            print("\n" + "-"*40)
            log("PHASE 1: FIRST READ (CSV write expected)", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Calling read_all()...", "PROCESS")
            manager.read_all()
            
            rows_after_first = count_csv_rows(csv_path)
            log(f"CSV state after first read:", "CSV")
            log(f"  - File exists: {os.path.exists(csv_path)}", "CSV")
            log(f"  - Row count: {rows_after_first}", "CSV")
            
            if rows_after_first > 0:
                with open(csv_path, 'r') as f:
                    content = f.read()
                    log(f"  - Content preview:", "CSV")
                    for line in content.strip().split('\n')[:3]:
                        log(f"    | {line[:70]}...", "DETAIL")
            
            time.sleep(0.15)  # Wait for fast poll throttle
            
            # ===== PHASE 2: RAPID READS (SHOULD NOT WRITE) =====
            print("\n" + "-"*40)
            log("PHASE 2: RAPID READS (NO CSV write expected)", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Calling read_all() 3 more times rapidly...", "PROCESS")
            log(f"  (Within {slow_csv}s slow interval, so no CSV writes expected)", "PROCESS")
            
            for i in range(3):
                time.sleep(0.15)
                log(f"  Call {i+1}/3...", "PROCESS")
                manager.read_all()
            
            rows_after_rapid = count_csv_rows(csv_path)
            log(f"\nCSV state after rapid reads:", "CSV")
            log(f"  - Row count before: {rows_after_first}", "CSV")
            log(f"  - Row count after: {rows_after_rapid}", "CSV")
            log(f"  - Rows added: {rows_after_rapid - rows_after_first}", "CSV")
            
            # ===== CHECK 1: NO WRITES DURING RAPID POLLING =====
            print("\n" + "-"*40)
            log("CHECK 1: No CSV writes during rapid polling", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Checking: rows_after_rapid ({rows_after_rapid}) == rows_after_first ({rows_after_first})", "CHECK")
            log(f"  Rationale: All reads were within {slow_csv}s interval,", "CHECK")
            log(f"             so no new CSV writes should have occurred", "CHECK")
            log(f"  (Total time for 3 rapid reads: ~450ms, interval: {slow_csv*1000}ms)", "CHECK")
            
            if rows_after_rapid == rows_after_first:
                log(f"✓ No spurious CSV writes during rapid polling", "PASS")
            else:
                log(f"✗ Unexpected CSV writes: {rows_after_first} -> {rows_after_rapid}", "FAIL")
                return False
            
            # ===== PHASE 3: WAIT FOR SLOW INTERVAL =====
            print("\n" + "-"*40)
            log("PHASE 3: WAIT FOR SLOW INTERVAL TO ELAPSE", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            wait_time = slow_csv + 0.1  # Wait full interval plus buffer
            log(f"Waiting {wait_time:.2f}s for slow interval to elapse...", "PROCESS")
            time.sleep(wait_time)
            
            log(f"Calling read_all() after slow interval...", "PROCESS")
            manager.read_all()
            
            rows_after_slow = count_csv_rows(csv_path)
            log(f"\nCSV state after slow interval:", "CSV")
            log(f"  - Row count before: {rows_after_rapid}", "CSV")
            log(f"  - Row count after: {rows_after_slow}", "CSV")
            log(f"  - Rows added: {rows_after_slow - rows_after_rapid}", "CSV")
            
            # ===== CHECK 2: WRITE AFTER SLOW INTERVAL =====
            print("\n" + "-"*40)
            log("CHECK 2: CSV write after slow interval elapsed", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Checking: rows_after_slow ({rows_after_slow}) > rows_after_rapid ({rows_after_rapid})", "CHECK")
            log(f"  Rationale: Slow interval ({slow_csv}s) has elapsed,", "CHECK")
            log(f"             so a new CSV write should have occurred", "CHECK")
            
            if rows_after_slow > rows_after_rapid:
                log(f"✓ CSV write occurred after slow interval: {rows_after_rapid} -> {rows_after_slow}", "PASS")
            else:
                log(f"✗ No CSV write after slow interval elapsed", "FAIL")
                return False
            
            # ===== SUMMARY =====
            print("\n" + "-"*40)
            log("ROW COUNT PROGRESSION", "HEADER")
            print("-"*40 + Colors.ENDC)
            
            log(f"Timeline:", "INFO")
            log(f"  1. After first read:    {rows_after_first} rows (write)", "INFO")
            log(f"  2. After 3 rapid reads: {rows_after_rapid} rows (no write)", "INFO")
            log(f"  3. After slow interval: {rows_after_slow} rows (write)", "INFO")
            log(f"", "INFO")
            log(f"In production (default config):", "INFO")
            log(f"  - Fast poll: every 0.5s (for blackout detection)", "INFO")
            log(f"  - CSV write: every 60s (120 polls = 1 CSV row)", "INFO")
            log(f"  - File size reduction: ~120x smaller than per-poll writes", "INFO")
            
            # ===== FINAL RESULT =====
            print("\n" + "="*80)
            log(f"TEST_07 RESULT: ALL CHECKS PASSED", "PASS")
            log(f"  - Rapid polling does NOT trigger CSV writes", "INFO")
            log(f"  - CSV writes only occur after slow_csv_interval", "INFO")
            log(f"  - Dual-rate architecture working correctly", "INFO")
            print("="*80 + "\n")
            return True
            
        except Exception as e:
            print("\n" + "="*80)
            log(f"TEST_07 RESULT: EXCEPTION OCCURRED", "FAIL")
            log(f"  Error: {e}", "FAIL")
            print("="*80)
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_slow_csv_interval()
    sys.exit(0 if success else 1)
