#!/bin/bash
#
# TEST_14_physical_rotation.sh
# 
# PURPOSE: Physical hardware test to verify CSV rotation on real SD card
#
# SCENARIO:
#   1. Create a large CSV file (~5MB, approximately 100,000 rows)
#   2. Run MeterManager rotation
#   3. Verify backup created in data/csv/backup/
#   4. Verify original DATA_ALL.csv truncated
#   5. Check file system for corruption (optional sync test)
#
# REQUIREMENTS:
#   - Run from project root: /home/pi/Desktop/offline-setup-12Sep
#   - Python 3.x with src/devices/meter_manager.py available
#
# USAGE:
#   chmod +x TEST_14_physical_rotation.sh
#   ./TEST_14_physical_rotation.sh
#

set -e

echo "================================================================================"
echo "$(date '+%H:%M:%S') TEST_14: PHYSICAL CSV ROTATION TEST"
echo "================================================================================"
echo ""
echo "PURPOSE: Test CSV rotation with real file system operations"
echo "         Creates ~5MB CSV and verifies backup/rotation works correctly"
echo ""
echo "WARNING: This will create/modify files in data/csv/"
echo ""
read -p "Press ENTER to continue or Ctrl+C to cancel..."
echo ""

cd /home/pi/Desktop/offline-setup-12Sep

# Ensure directories exist
mkdir -p data/csv/backup

echo "--------------------------------------------------------------------------------"
echo "$(date '+%H:%M:%S') STEP 1: Creating large test CSV file"
echo "--------------------------------------------------------------------------------"

python3 << 'PYEOF'
import csv
import os
from datetime import datetime, timedelta

csv_path = "data/csv/DATA_ALL.csv"

# Backup existing file if present
if os.path.exists(csv_path):
    backup_name = csv_path + ".pre_test_backup"
    print(f"Backing up existing file to: {backup_name}")
    import shutil
    shutil.copy2(csv_path, backup_name)

print(f"Creating large test file: {csv_path}")

with open(csv_path, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Device_ID", "Meter_Name", "Time", "Model", "Frequency", "Voltage", "Current", "Power", "Energy"])
    
    start = datetime(2026, 1, 18, 10, 0, 0)
    # Create ~100,000 rows for ~5MB file
    total_rows = 100000
    for i in range(total_rows):
        ts = (start + timedelta(seconds=i*10)).strftime('%Y-%m-%d %H:%M:%S')
        writer.writerow([1, "PhysicalTest", ts, "LG6400", 50.0, 230.5, 5.2, 1198.6, i*0.01])
        
        if i % 25000 == 0:
            print(f"  Written {i}/{total_rows} rows ({i/total_rows*100:.0f}%)...")

file_size = os.path.getsize(csv_path)
print(f"✓ Created: {file_size} bytes ({file_size/1024/1024:.2f} MB)")
PYEOF

echo ""
echo "--------------------------------------------------------------------------------"
echo "$(date '+%H:%M:%S') STEP 2: Listing backup directory BEFORE rotation"
echo "--------------------------------------------------------------------------------"

echo "Contents of data/csv/backup/:"
ls -lh data/csv/backup/ 2>/dev/null || echo "  (empty)"

echo ""
echo "--------------------------------------------------------------------------------"
echo "$(date '+%H:%M:%S') STEP 3: Running rotation via MeterManager"
echo "--------------------------------------------------------------------------------"

timeout 30 python3 << 'PYEOF'
import sys
import os
import time
sys.path.insert(0, '.')

from src.devices.meter_manager import MeterManager
from unittest.mock import MagicMock
from pathlib import Path

print("Creating MeterManager instance...")
mock_meter = MagicMock()
mock_meter.name = "PhysicalTest"
mock_meter.model = "LG6400"
mock_meter.device_address = 1

manager = MeterManager(
    meters=[mock_meter], 
    parameters=["Time", "Frequency", "Voltage", "Current", "Power", "Energy"]
)

# Force prune check interval to pass
manager.prune_check_interval = 0
manager._last_prune_check = 0

# Lower threshold for testing (current file should exceed 1MB)
print(f"Current rotation_size_threshold: {manager.rotation_size_threshold} bytes")

print("Checking file size...")
current_size = os.path.getsize(manager.csv_path)
print(f"Current DATA_ALL.csv size: {current_size} bytes ({current_size/1024/1024:.2f} MB)")

if current_size < manager.rotation_size_threshold:
    print(f"File smaller than threshold - lowering threshold for test")
    manager.rotation_size_threshold = 1000  # 1KB for testing

print("Executing rotation...")
start_time = time.time()
manager._perform_safe_rotation()
elapsed = time.time() - start_time

print(f"✓ Rotation completed in {elapsed:.2f} seconds")

# Show results
backup_files = list(manager.backup_dir.glob("*.csv"))
print(f"\nBackup files found: {len(backup_files)}")
for bf in backup_files[-3:]:  # Show last 3
    print(f"  {bf.name}: {bf.stat().st_size} bytes")

new_size = os.path.getsize(manager.csv_path)
print(f"\nNew DATA_ALL.csv size: {new_size} bytes")

manager.close()
PYEOF

echo ""
echo "--------------------------------------------------------------------------------"
echo "$(date '+%H:%M:%S') STEP 4: Listing backup directory AFTER rotation"
echo "--------------------------------------------------------------------------------"

echo "Contents of data/csv/backup/:"
ls -lh data/csv/backup/

echo ""
echo "--------------------------------------------------------------------------------"
echo "$(date '+%H:%M:%S') STEP 5: Verifying results"
echo "--------------------------------------------------------------------------------"

# Check DATA_ALL.csv size
DATA_SIZE=$(stat -f%z data/csv/DATA_ALL.csv 2>/dev/null || stat -c%s data/csv/DATA_ALL.csv)
echo "DATA_ALL.csv size: $DATA_SIZE bytes"

if [ "$DATA_SIZE" -lt 1000 ]; then
    echo "✓ DATA_ALL.csv successfully truncated (headers only)"
else
    echo "⚠ DATA_ALL.csv may not be fully truncated"
fi

# Count backup files
BACKUP_COUNT=$(ls -1 data/csv/backup/*.csv 2>/dev/null | wc -l)
echo "Backup files count: $BACKUP_COUNT"

if [ "$BACKUP_COUNT" -gt 0 ]; then
    echo "✓ Backup file(s) created successfully"
    
    # Show latest backup
    echo ""
    echo "Latest backup file:"
    ls -lht data/csv/backup/*.csv | head -1
    
    # Show first and last few lines of backup
    LATEST=$(ls -t data/csv/backup/*.csv | head -1)
    echo ""
    echo "First 3 lines of backup:"
    head -3 "$LATEST"
    echo ""
    echo "Last 3 lines of backup:"
    tail -3 "$LATEST"
else
    echo "✗ No backup files found!"
fi

# Check EVENTS.csv for rotation event
echo ""
echo "--------------------------------------------------------------------------------"
echo "$(date '+%H:%M:%S') STEP 6: Checking EVENTS.csv for CSV_ROTATION event"
echo "--------------------------------------------------------------------------------"

if [ -f "data/csv/EVENTS.csv" ]; then
    if grep -q "CSV_ROTATION" data/csv/EVENTS.csv; then
        echo "✓ CSV_ROTATION event logged"
        echo ""
        echo "Event details:"
        grep "CSV_ROTATION" data/csv/EVENTS.csv | tail -1
    else
        echo "⚠ CSV_ROTATION event not found in EVENTS.csv"
    fi
else
    echo "⚠ EVENTS.csv not found"
fi

echo ""
echo "================================================================================"
echo "$(date '+%H:%M:%S') TEST_14 COMPLETE"
echo "================================================================================"
echo ""
echo "Manual verification steps:"
echo "  1. Check data/csv/backup/ for timestamped archive"
echo "  2. Verify DATA_ALL.csv has only headers"
echo "  3. Optionally run 'sync' and check disk health"
echo ""
