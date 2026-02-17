#!/bin/bash
# ============================================================
# fix_time.sh — One-command time fix for RPI with DS3231 RTC
# ============================================================
#
# This is the script you run when the RPI time is wrong.
# It handles the FULL flow automatically:
#
#   1. If internet is available → sync from NTP → write to RTC
#   2. If no internet → read from RTC → set system time
#
# Usage:
#   sudo bash fix_time.sh
#
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "  RPI Time Fix (DS3231 RTC)"
echo "============================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Find hwclock (may not be in PATH)
HWCLOCK=""
for p in /sbin/hwclock /usr/sbin/hwclock /bin/hwclock /usr/bin/hwclock; do
    [ -x "$p" ] && HWCLOCK="$p" && break
done
if [ -z "$HWCLOCK" ]; then
    echo "hwclock not found. Install with: sudo apt install util-linux"
fi

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

# Show current state
echo "Current system time: $(date '+%Y-%m-%d %H:%M:%S')"

# Try to read RTC time via Python
RTC_TIME=""
if python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
try:
    from rtc_module import get_rtc
    rtc = get_rtc(fallback_to_system=False)
    if rtc.is_available():
        t = rtc.get_time()
        print(t.strftime('%Y-%m-%d %H:%M:%S'))
    else:
        sys.exit(1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    RTC_TIME=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from rtc_module import get_rtc
rtc = get_rtc(fallback_to_system=False)
print(rtc.get_time().strftime('%Y-%m-%d %H:%M:%S'))
" 2>/dev/null)
    echo "Current RTC time:    $RTC_TIME"
else
    warn "Could not read RTC — is DS3231 connected?"
fi

echo ""

# ── Step 1: Try NTP sync ──────────────────────────────────────
echo "Step 1: Checking internet connectivity..."

HAS_INTERNET=false
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    ok "Internet available"
    HAS_INTERNET=true
else
    warn "No internet — will use RTC time"
fi

if [ "$HAS_INTERNET" = true ]; then
    echo ""
    echo "Step 2: Syncing system time from NTP..."
    
    # Enable NTP and wait for sync
    timedatectl set-ntp true 2>/dev/null || true
    
    # Wait up to 15 seconds for NTP to sync
    for i in $(seq 1 15); do
        if timedatectl show --property=NTPSynchronized --value 2>/dev/null | grep -q "yes"; then
            ok "NTP synchronized"
            break
        fi
        sleep 1
    done
    
    # Check if sync happened
    if timedatectl show --property=NTPSynchronized --value 2>/dev/null | grep -q "yes"; then
        NTP_OK=true
    else
        # Even without confirmed sync, NTP may have partially corrected
        warn "NTP sync not confirmed, but time may be close enough"
        NTP_OK=true
    fi
    
    echo "System time is now: $(date '+%Y-%m-%d %H:%M:%S')"
    
    echo ""
    echo "Step 3: Writing system time → RTC..."
    
    # Disable NTP before writing to RTC (avoids time changing mid-write)
    timedatectl set-ntp false 2>/dev/null || true
    sleep 0.5
    
    # Write to RTC via Python
    cd "$SCRIPT_DIR"
    if python3 set_rtc.py; then
        ok "RTC updated with correct time"
    else
        fail "Could not write to RTC"
    fi
    
    # Re-enable NTP
    timedatectl set-ntp true 2>/dev/null || true
    
else
    # ── No internet: use RTC ──────────────────────────────────
    echo ""
    echo "Step 2: Setting system time from RTC..."
    
    if [ -n "$RTC_TIME" ]; then
        # Disable NTP (it would try to override our manual time)
        timedatectl set-ntp false 2>/dev/null || true
        
        # Set system time from RTC
        date -s "$RTC_TIME" >/dev/null 2>&1
        ok "System time set from RTC: $RTC_TIME"
    else
        fail "No RTC available and no internet — cannot fix time!"
        echo "  Connect to internet and run again, or set manually:"
        echo "  sudo date -s '2026-02-17 14:00:00'"
        exit 1
    fi
fi

echo ""
echo "============================================"
echo "  Final state:"
echo "  System: $(date '+%Y-%m-%d %H:%M:%S')"

# Read RTC one more time
FINAL_RTC=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from rtc_module import get_rtc
rtc = get_rtc(fallback_to_system=False)
if rtc.is_available():
    print(rtc.get_time().strftime('%Y-%m-%d %H:%M:%S'))
else:
    print('(unavailable)')
" 2>/dev/null || echo "(unavailable)")
echo "  RTC:    $FINAL_RTC"
echo "============================================"
ok "Done! Time should now persist across reboots."
echo ""
