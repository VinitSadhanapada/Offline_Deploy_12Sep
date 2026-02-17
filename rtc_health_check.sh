#!/bin/bash
# ============================================================
# rtc_health_check.sh — Verify DS3231 RTC is working
# ============================================================
#
# Run anytime to check RTC health. No sudo required for most
# checks (needs sudo only for hwclock).
#
# Usage:
#   bash rtc_health_check.sh
#
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "  DS3231 RTC Health Check"
echo "============================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

ok()   { echo -e "  ${GREEN}✓ PASS${NC}  $1"; PASS=$((PASS+1)); }
warn() { echo -e "  ${YELLOW}⚠ WARN${NC}  $1"; WARN=$((WARN+1)); }
fail() { echo -e "  ${RED}✗ FAIL${NC}  $1"; FAIL=$((FAIL+1)); }

# ── Check 1: I2C enabled ───────────────────────────────────
echo "Check 1: I2C interface"
if [ -e /dev/i2c-1 ]; then
    ok "I2C bus 1 available (/dev/i2c-1 exists)"
else
    fail "I2C bus 1 not found — run: sudo raspi-config → Interface → I2C"
fi

# ── Check 2: DS3231 detected ───────────────────────────────
echo "Check 2: DS3231 on I2C bus"
I2C_RESULT=$(i2cdetect -y 1 2>/dev/null | grep -o "68\|UU" | head -1)
if [ "$I2C_RESULT" = "UU" ]; then
    ok "DS3231 at 0x68 (kernel driver loaded)"
elif [ "$I2C_RESULT" = "68" ]; then
    warn "DS3231 at 0x68 (detected but kernel driver not loaded)"
    echo "         This is OK for Python I2C mode"
else
    fail "DS3231 NOT detected at 0x68"
    echo "         Check wiring: VCC→3.3V, GND→GND, SDA→GPIO2, SCL→GPIO3"
fi

# ── Check 3: /dev/rtc0 exists ──────────────────────────────
echo "Check 3: RTC device node"
if [ -e /dev/rtc0 ]; then
    ok "/dev/rtc0 exists"
else
    warn "/dev/rtc0 not found (kernel driver not loaded)"
    echo "         Add 'dtoverlay=i2c-rtc,ds3231' to config.txt and reboot"
    echo "         Python I2C still works without /dev/rtc0"
fi

# ── Check 4: hwclock readable ──────────────────────────────
echo "Check 4: hwclock read"
HWCLOCK_TIME=$(sudo hwclock -r 2>/dev/null)
if [ $? -eq 0 ]; then
    ok "hwclock reads: $HWCLOCK_TIME"
else
    warn "hwclock could not read RTC (needs sudo or /dev/rtc0)"
fi

# ── Check 5: Python I2C read ───────────────────────────────
echo "Check 5: Python I2C read (rtc_module.py)"
PYTHON_RTC=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from rtc_module import get_rtc
rtc = get_rtc(fallback_to_system=False)
if rtc.is_available():
    t = rtc.get_time()
    print(t.strftime('%Y-%m-%d %H:%M:%S'))
else:
    print('UNAVAILABLE')
" 2>/dev/null || echo "ERROR")

if [ "$PYTHON_RTC" = "ERROR" ] || [ "$PYTHON_RTC" = "UNAVAILABLE" ]; then
    fail "Python rtc_module could not read DS3231"
    echo "         Check: python3-smbus or smbus2 installed?"
else
    ok "Python reads RTC: $PYTHON_RTC"
fi

# ── Check 6: System vs RTC drift ───────────────────────────
echo "Check 6: System ↔ RTC drift"
SYSTEM_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "         System: $SYSTEM_TIME"

if [ -n "$PYTHON_RTC" ] && [ "$PYTHON_RTC" != "ERROR" ] && [ "$PYTHON_RTC" != "UNAVAILABLE" ]; then
    echo "         RTC:    $PYTHON_RTC"
    
    # Calculate drift in seconds
    DRIFT=$(python3 -c "
from datetime import datetime
sys_t = datetime.strptime('$SYSTEM_TIME', '%Y-%m-%d %H:%M:%S')
rtc_t = datetime.strptime('$PYTHON_RTC', '%Y-%m-%d %H:%M:%S')
print(int(abs((sys_t - rtc_t).total_seconds())))
" 2>/dev/null || echo "?")
    
    if [ "$DRIFT" != "?" ]; then
        if [ "$DRIFT" -le 2 ]; then
            ok "Drift: ${DRIFT}s (excellent)"
        elif [ "$DRIFT" -le 5 ]; then
            ok "Drift: ${DRIFT}s (acceptable)"
        elif [ "$DRIFT" -le 60 ]; then
            warn "Drift: ${DRIFT}s (should sync — run: sudo bash fix_time.sh)"
        else
            fail "Drift: ${DRIFT}s (significant — run: sudo bash fix_time.sh)"
        fi
    fi
else
    warn "Cannot calculate drift (RTC unavailable)"
fi

# ── Check 7: DS3231 temperature ─────────────────────────────
echo "Check 7: DS3231 temperature (battery proxy)"
TEMP=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from rtc_module import get_rtc
rtc = get_rtc(fallback_to_system=False)
if rtc.is_available():
    t = rtc.get_temperature()
    if t is not None:
        print(f'{t:.1f}')
    else:
        print('NONE')
else:
    print('NONE')
" 2>/dev/null || echo "NONE")

if [ "$TEMP" != "NONE" ]; then
    ok "DS3231 temperature: ${TEMP}°C (chip is powered)"
else
    warn "Could not read DS3231 temperature"
fi

# ── Check 8: rtc-sync service ──────────────────────────────
echo "Check 8: Boot sync service"
if systemctl is-enabled rtc-sync.service >/dev/null 2>&1; then
    ok "rtc-sync.service is enabled"
else
    warn "rtc-sync.service not enabled — run: sudo bash rtc_setup.sh"
fi

# ── Check 9: Oscillator Stop Flag ──────────────────────────
echo "Check 9: Oscillator stop flag"
OSF=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from rtc_module import get_rtc
rtc = get_rtc(fallback_to_system=False)
if rtc.is_available():
    osf = rtc.check_oscillator_stopped()
    print('SET' if osf else 'CLEAR')
else:
    print('UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")

if [ "$OSF" = "CLEAR" ]; then
    ok "Oscillator stop flag: clear (RTC running normally)"
elif [ "$OSF" = "SET" ]; then
    warn "Oscillator stop flag: SET (power was lost to RTC)"
    echo "         Run 'sudo bash fix_time.sh' to clear this"
else
    warn "Could not check oscillator flag"
fi

# ── Summary ─────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  Results: ${GREEN}${PASS} passed${NC}, ${YELLOW}${WARN} warnings${NC}, ${RED}${FAIL} failed${NC}"
echo ""
if [ $FAIL -eq 0 ]; then
    echo -e "  ${GREEN}RTC is working!${NC}"
    echo "  Time will persist across power cycles."
else
    echo -e "  ${RED}Issues found.${NC} Run setup or fix:"
    echo "    sudo bash rtc_setup.sh    # First-time setup"
    echo "    sudo bash fix_time.sh     # Fix time now"
fi
echo "============================================"
