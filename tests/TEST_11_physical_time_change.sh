#!/bin/bash
# TEST_11_physical_time_change.sh
# Physical hardware test: Actually change system time and verify correction
#
# WARNING: This test modifies system time! Only run on test Pi, not production!
#
# WHAT IT DOES:
#   1. Saves current time
#   2. Sets system time to 2020 (wrong)
#   3. Runs time sanitizer validation
#   4. Verifies RTC corrects the system time
#   5. Restores from RTC

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}${BOLD}[PASS]${NC} $1"
}

log_fail() {
    echo -e "${RED}${BOLD}[FAIL]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo ""
echo "================================================================================"
echo -e "${BOLD}TEST_11: PHYSICAL TIME CORRECTION TEST${NC}"
echo "================================================================================"
echo ""
echo "  This test will TEMPORARILY set your system time to 2020-01-01 and verify"
echo "  that the RTCTimeSanitizer correctly detects and corrects the error."
echo ""
echo "  REQUIREMENTS:"
echo "    - Working RTC module (DS3231 or similar)"
echo "    - RTC battery installed and working"
echo "    - Current RTC time is correct (year >= 2024)"
echo ""
echo -e "${YELLOW}  WARNING: Only run on test Pi, not production systems!${NC}"
echo ""
echo "  Press ENTER to continue or Ctrl+C to abort..."
read

# Change to project directory
cd /home/pi/Desktop/offline-setup-12Sep
log_info "Working directory: $(pwd)"

# ===== PRE-CHECKS =====
echo ""
echo "--------------------------------------------------------------------------------"
log_info "PRE-CHECKS: Verifying RTC is working"
echo "--------------------------------------------------------------------------------"

log_info "Current system time: $(date)"
log_info "Reading RTC time..."

RTC_TIME=$(sudo hwclock -r 2>/dev/null || echo "FAILED")
if [ "$RTC_TIME" = "FAILED" ]; then
    log_fail "Cannot read RTC! Is the RTC module connected?"
    exit 1
fi

log_info "RTC time: $RTC_TIME"

# Extract year from RTC
RTC_YEAR=$(sudo hwclock -r 2>/dev/null | grep -oE '20[0-9]{2}' | head -1)
if [ -z "$RTC_YEAR" ] || [ "$RTC_YEAR" -lt 2024 ]; then
    log_fail "RTC year ($RTC_YEAR) is invalid or before 2024"
    log_warn "Please set RTC to current time first: sudo hwclock -w"
    exit 1
fi

log_pass "RTC is working (year=$RTC_YEAR)"

# ===== STOP SERVICES =====
echo ""
echo "--------------------------------------------------------------------------------"
log_info "STOPPING SERVICES"
echo "--------------------------------------------------------------------------------"

log_info "Stopping meter-dashboard service (if running)..."
sudo systemctl stop meter-dashboard 2>/dev/null || true
log_info "Services stopped"

# ===== CLEAR STATE FILE =====
echo ""
echo "--------------------------------------------------------------------------------"
log_info "CLEARING STATE FILE (simulating fresh boot)"
echo "--------------------------------------------------------------------------------"

STATE_FILE="data/rtc_state.json"
if [ -f "$STATE_FILE" ]; then
    log_info "Removing existing state file: $STATE_FILE"
    rm -f "$STATE_FILE"
fi
log_pass "State cleared"

# ===== SET WRONG TIME =====
echo ""
echo "--------------------------------------------------------------------------------"
log_info "SETTING WRONG SYSTEM TIME (2020-01-01)"
echo "--------------------------------------------------------------------------------"

ORIGINAL_TIME=$(date +"%Y-%m-%d %H:%M:%S")
log_info "Original system time: $ORIGINAL_TIME"

log_warn "Setting system time to 2020-01-01 00:00:00..."
sudo date -s "2020-01-01 00:00:00"

WRONG_TIME=$(date +"%Y-%m-%d %H:%M:%S")
log_info "System time now: $WRONG_TIME"

WRONG_YEAR=$(date +%Y)
if [ "$WRONG_YEAR" != "2020" ]; then
    log_fail "Failed to set wrong time"
    sudo hwclock --hctosys
    exit 1
fi
log_pass "System time set to wrong value (2020)"

# ===== RUN TIME SANITIZER =====
echo ""
echo "--------------------------------------------------------------------------------"
log_info "RUNNING TIME SANITIZER VALIDATION"
echo "--------------------------------------------------------------------------------"

# Activate virtual environment if exists
if [ -d "test_venv" ]; then
    source test_venv/bin/activate 2>/dev/null || true
fi

log_info "Executing RTCTimeSanitizer.validate_and_correct()..."
echo ""

# Run Python validation script
RESULT=$(python3 << 'PYEOF'
import sys
import json
sys.path.insert(0, '.')

from src.utils.time_sanitizer import RTCTimeSanitizer

print("[PYTHON] Creating RTCTimeSanitizer...")
sanitizer = RTCTimeSanitizer()

print("[PYTHON] Running validate_and_correct()...")
is_valid, events = sanitizer.validate_and_correct()

print(f"\n[PYTHON] Results:")
print(f"  is_valid: {is_valid}")
print(f"  events ({len(events)}):")

for i, e in enumerate(events):
    print(f"    [{i+1}] {e['type']}")
    for k, v in e.items():
        if k != 'type':
            print(f"        {k}: {v}")

# Check for TIME_CORRECTION event
corrections = [e for e in events if e['type'] == 'TIME_CORRECTION']
if corrections:
    print(f"\n[PYTHON] TIME_CORRECTION detected!")
    print(f"  Offset was: {corrections[0].get('offset_sec', 'N/A')} seconds")
    sys.exit(0)  # Success
else:
    print(f"\n[PYTHON] No TIME_CORRECTION event found!")
    sys.exit(1)  # Failure
PYEOF
)

PYTHON_EXIT=$?
echo "$RESULT"

# ===== VERIFY CORRECTION =====
echo ""
echo "--------------------------------------------------------------------------------"
log_info "VERIFYING TIME WAS CORRECTED"
echo "--------------------------------------------------------------------------------"

CORRECTED_YEAR=$(date +%Y)
log_info "System year after validation: $CORRECTED_YEAR"

if [ "$CORRECTED_YEAR" -ge 2024 ]; then
    log_pass "System time was corrected to RTC time!"
    log_info "Current system time: $(date)"
else:
    log_fail "System time still wrong (year=$CORRECTED_YEAR)"
    log_warn "Restoring from RTC manually..."
    sudo hwclock --hctosys
    exit 1
fi

# ===== CHECK STATE FILE =====
echo ""
echo "--------------------------------------------------------------------------------"
log_info "CHECKING STATE FILE"
echo "--------------------------------------------------------------------------------"

if [ -f "$STATE_FILE" ]; then
    log_pass "State file created: $STATE_FILE"
    log_info "Contents:"
    cat "$STATE_FILE" | sed 's/^/    /'
else
    log_warn "State file not created (non-critical)"
fi

# ===== FINAL SYNC =====
echo ""
echo "--------------------------------------------------------------------------------"
log_info "FINAL SYNC FROM RTC"
echo "--------------------------------------------------------------------------------"

sudo hwclock --hctosys
log_info "System time synced from RTC"
log_info "Final system time: $(date)"

# ===== RESULT =====
echo ""
echo "================================================================================"
if [ $PYTHON_EXIT -eq 0 ]; then
    log_pass "TEST_11 RESULT: PHYSICAL TIME CORRECTION WORKING"
    echo ""
    echo "  The RTCTimeSanitizer successfully:"
    echo "    1. Detected that system time (2020) was wrong"
    echo "    2. Compared against RTC time ($RTC_YEAR)"
    echo "    3. Corrected system time to match RTC"
    echo "    4. Logged the TIME_CORRECTION event"
else
    log_fail "TEST_11 RESULT: TIME CORRECTION FAILED"
    echo ""
    echo "  The RTCTimeSanitizer did not detect or correct the time error."
    echo "  Check the Python output above for details."
fi
echo "================================================================================"
echo ""

exit $PYTHON_EXIT
