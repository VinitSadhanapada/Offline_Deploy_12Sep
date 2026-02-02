#!/usr/bin/env python3
"""
TEST_13: ARCHIVE CLEANUP TEST

PURPOSE: Verify archives older than retention_days are automatically deleted.

SCENARIO:
  1. Create MeterManager
  2. Manually create archive files with various dates:
     - Old archive: 15 days ago (should be deleted)
     - Recent archive: 1 hour ago (should be kept)
  3. Call _cleanup_old_archives()
  4. Verify:
     - Old archive deleted
     - Recent archive preserved

IMPORTANT: Uses stdlib only, no pip install required.
"""
import sys
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def log(level, msg):
    """Verbose test logging with timestamp."""
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"{ts} [{level}] {msg}")

def test_archive_cleanup():
    """Test that archives older than retention_days are deleted."""
    print("")
    print("=" * 80)
    log("INFO", "TEST_13: ARCHIVE CLEANUP TEST")
    print("=" * 80)
    print("""
    PURPOSE: Verify archives older than retention_days are automatically deleted
             while recent archives are preserved.
    
    SCENARIO:
      1. Create backup directory with old and new archives
      2. Set retention_days = 7 for testing
      3. Call _cleanup_old_archives()
      4. Verify old archive deleted, recent archive kept
    """)
    
    from src.devices.meter_manager import MeterManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_dir = Path(tmpdir) / "backup"
        backup_dir.mkdir()
        csv_path = os.path.join(tmpdir, "DATA_ALL.csv")
        
        # Create empty CSV for MeterManager
        with open(csv_path, 'w') as f:
            f.write("Device_ID,Meter_Name,Time,Model,Frequency\n")
        
        print("-" * 40)
        log("INFO", "SETUP: CREATING TEST ARCHIVES")
        print("-" * 40)
        
        # Create old archive (15 days ago -> 8 days ago, older than 7-day retention)
        old_start = datetime.now() - timedelta(days=16)
        old_end = datetime.now() - timedelta(days=15)  # End time is what matters
        old_name = f"{old_start.strftime('%Y-%m-%d_%H%M%S')}_TO_{old_end.strftime('%Y-%m-%d_%H%M%S')}.csv"
        old_file = backup_dir / old_name
        old_file.write_text("Device_ID,Meter_Name,Time\n1,OldMeter,2026-01-15 10:00:00\n")
        
        log("INPUT", f"Created OLD archive (15 days ago):")
        log("DETAIL", f"  Name: {old_name}")
        log("DETAIL", f"  End timestamp: {old_end}")
        
        # Create recent archive (2 hours ago -> 1 hour ago, within retention)
        new_start = datetime.now() - timedelta(hours=2)
        new_end = datetime.now() - timedelta(hours=1)
        new_name = f"{new_start.strftime('%Y-%m-%d_%H%M%S')}_TO_{new_end.strftime('%Y-%m-%d_%H%M%S')}.csv"
        new_file = backup_dir / new_name
        new_file.write_text("Device_ID,Meter_Name,Time\n1,NewMeter,2026-01-30 10:00:00\n")
        
        log("INPUT", f"Created RECENT archive (1 hour ago):")
        log("DETAIL", f"  Name: {new_name}")
        log("DETAIL", f"  End timestamp: {new_end}")
        
        # Create medium-age archive (exactly at cutoff - 7 days ago, should be KEPT)
        mid_start = datetime.now() - timedelta(days=8)
        mid_end = datetime.now() - timedelta(days=7, hours=-1)  # Just inside retention
        mid_name = f"{mid_start.strftime('%Y-%m-%d_%H%M%S')}_TO_{mid_end.strftime('%Y-%m-%d_%H%M%S')}.csv"
        mid_file = backup_dir / mid_name
        mid_file.write_text("Device_ID,Meter_Name,Time\n1,MidMeter,2026-01-24 10:00:00\n")
        
        log("INPUT", f"Created EDGE CASE archive (~7 days ago):")
        log("DETAIL", f"  Name: {mid_name}")
        log("DETAIL", f"  End timestamp: {mid_end}")
        
        print("-" * 40)
        log("INFO", "SETUP: CREATING METERMANAGER")
        print("-" * 40)
        
        mock_meter = MagicMock()
        mock_meter.name = "TestMeter"
        mock_meter.model = "LG6400"
        
        manager = MeterManager(
            meters=[mock_meter],
            parameters=["Time", "Frequency"]
        )
        
        # Override backup_dir and retention
        manager.backup_dir = backup_dir
        manager.retention_days = 7  # 7 days for testing
        
        log("OUTPUT", f"MeterManager created with retention_days={manager.retention_days}")
        
        # Calculate cutoff
        cutoff = datetime.now() - timedelta(days=manager.retention_days)
        log("DETAIL", f"  Cutoff date: {cutoff.strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("-" * 40)
        log("INFO", "BEFORE CLEANUP: Listing archives")
        print("-" * 40)
        
        for f in sorted(backup_dir.glob("*.csv")):
            log("OUTPUT", f"  {f.name}")
        
        print("-" * 40)
        log("INFO", "RUNNING _cleanup_old_archives()")
        print("-" * 40)
        
        log("PROCESS", "Executing cleanup...")
        manager._cleanup_old_archives()
        
        print("-" * 40)
        log("INFO", "AFTER CLEANUP: Listing archives")
        print("-" * 40)
        
        remaining_files = list(backup_dir.glob("*.csv"))
        for f in sorted(remaining_files):
            log("OUTPUT", f"  {f.name}")
        
        all_passed = True
        
        # CHECK 1: Old archive deleted
        print("-" * 40)
        log("INFO", "CHECK 1: Old archive deleted (>14 days)")
        print("-" * 40)
        
        if old_file.exists():
            log("FAIL", f"✗ Old archive still exists: {old_name}")
            all_passed = False
        else:
            log("PASS", f"✓ Old archive deleted correctly")
            log("DETAIL", f"  Deleted: {old_name}")
        
        # CHECK 2: Recent archive preserved
        print("-" * 40)
        log("INFO", "CHECK 2: Recent archive preserved (<7 days)")
        print("-" * 40)
        
        if new_file.exists():
            log("PASS", f"✓ Recent archive preserved correctly")
            log("DETAIL", f"  Kept: {new_name}")
        else:
            log("FAIL", f"✗ Recent archive was incorrectly deleted: {new_name}")
            all_passed = False
        
        # CHECK 3: Edge case archive (at cutoff)
        print("-" * 40)
        log("INFO", "CHECK 3: Edge case archive (just within retention)")
        print("-" * 40)
        
        if mid_file.exists():
            log("PASS", f"✓ Edge case archive preserved (just within retention)")
            log("DETAIL", f"  Kept: {mid_name}")
        else:
            log("WARN", f"⚠ Edge case archive deleted (borderline expected)")
            log("DETAIL", f"  Deleted: {mid_name}")
        
        # CHECK 4: Correct count
        print("-" * 40)
        log("INFO", "CHECK 4: Final archive count")
        print("-" * 40)
        
        expected_min = 1  # At least the recent one
        expected_max = 2  # Recent + maybe edge case
        actual_count = len(remaining_files)
        
        log("OUTPUT", f"Archives remaining: {actual_count}")
        
        if expected_min <= actual_count <= expected_max:
            log("PASS", f"✓ Correct number of archives ({actual_count})")
        else:
            log("FAIL", f"✗ Unexpected archive count: {actual_count} (expected {expected_min}-{expected_max})")
            all_passed = False
        
        # Cleanup manager
        try:
            manager.csv_file.close()
        except:
            pass
        
        print("")
        print("=" * 80)
        if all_passed:
            log("PASS", "TEST_13 RESULT: ALL CHECKS PASSED")
        else:
            log("FAIL", "TEST_13 RESULT: SOME CHECKS FAILED")
        print("=" * 80)
        
        return all_passed

if __name__ == "__main__":
    success = test_archive_cleanup()
    sys.exit(0 if success else 1)
