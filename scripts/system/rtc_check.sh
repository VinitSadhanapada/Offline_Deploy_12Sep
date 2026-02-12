#!/bin/bash
#===============================================================================
# RTC Health Check Script
# =======================
# Run manually to verify DS3231 RTC is working correctly.
# Tests I2C connectivity, time reading, time persistence, and drift.
#
# Usage:
#   sudo bash scripts/system/rtc_check.sh
#   OR
#   sudo ./scripts/system/rtc_check.sh
#
# Exit codes:
#   0 = All checks passed
#   1 = One or more checks failed
#===============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { echo -e "  ${GREEN}✓ PASS${NC}: $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}✗ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }
warn() { echo -e "  ${YELLOW}⚠ WARN${NC}: $1"; WARN=$((WARN + 1)); }
info() { echo -e "  ${CYAN}ℹ INFO${NC}: $1"; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║          DS3231 RTC HEALTH CHECK                 ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""

#--- Check 1: Is I2C enabled? ---
echo -e "${BOLD}[1/7] I2C Interface${NC}"
if [ -e /dev/i2c-1 ]; then
    pass "I2C bus /dev/i2c-1 exists"
else
    fail "I2C bus /dev/i2c-1 NOT found"
    info "Enable I2C: sudo raspi-config → Interface Options → I2C → Enable"
    info "Or: echo 'dtparam=i2c_arm=on' | sudo tee -a /boot/config.txt && sudo reboot"
fi
echo ""

#--- Check 2: Is i2c-tools installed? ---
echo -e "${BOLD}[2/7] I2C Tools${NC}"
if command -v i2cdetect &>/dev/null; then
    pass "i2cdetect is available"
else
    fail "i2cdetect not found"
    info "Install: sudo apt-get install -y i2c-tools"
fi
echo ""

#--- Check 3: DS3231 detected at 0x68? ---
echo -e "${BOLD}[3/7] DS3231 Detection (address 0x68)${NC}"
if command -v i2cdetect &>/dev/null && [ -e /dev/i2c-1 ]; then
    I2C_OUTPUT=$(i2cdetect -y 1 2>/dev/null || true)
    if echo "$I2C_OUTPUT" | grep -q "68"; then
        pass "DS3231 detected at address 0x68"
    else
        fail "No device found at address 0x68"
        info "Check wiring: SDA→GPIO2(pin3), SCL→GPIO3(pin5), VCC→3.3V(pin1), GND→pin9"
        echo ""
        info "I2C bus scan output:"
        echo "$I2C_OUTPUT" | while read -r line; do echo "       $line"; done
    fi
else
    fail "Cannot scan I2C bus (i2cdetect missing or /dev/i2c-1 unavailable)"
fi
echo ""

#--- Check 4: Can we read RTC time? ---
echo -e "${BOLD}[4/7] RTC Time Reading${NC}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON_CMD=""
if [ -x "$PROJECT_ROOT/venv313/bin/python3" ]; then
    PYTHON_CMD="$PROJECT_ROOT/venv313/bin/python3"
elif [ -x "$PROJECT_ROOT/venv/bin/python3" ]; then
    PYTHON_CMD="$PROJECT_ROOT/venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

RTC_TIME=$($PYTHON_CMD -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT/src')
sys.path.insert(0, '$PROJECT_ROOT')
try:
    from src.utils.rtc_module import DS3231
    rtc = DS3231(fallback_to_system=False)
    if rtc.is_available():
        t = rtc.get_time()
        print('OK|' + t.strftime('%Y-%m-%d %H:%M:%S'))
    else:
        print('UNAVAILABLE|RTC not responding')
except Exception as e:
    print('ERROR|' + str(e))
" 2>/dev/null || echo "ERROR|Python script failed")

RTC_STATUS=$(echo "$RTC_TIME" | cut -d'|' -f1)
RTC_VALUE=$(echo "$RTC_TIME" | cut -d'|' -f2-)

if [ "$RTC_STATUS" = "OK" ]; then
    pass "RTC time read successfully: $RTC_VALUE"
    
    # Check year sanity
    RTC_YEAR=$(echo "$RTC_VALUE" | cut -d'-' -f1)
    if [ "$RTC_YEAR" -lt 2024 ]; then
        fail "RTC year is $RTC_YEAR (< 2024) — possible battery failure!"
        info "Replace the CR2032 battery on the DS3231 module"
    else
        pass "RTC year ($RTC_YEAR) is sane"
    fi
else
    fail "Could not read RTC time: $RTC_VALUE"
fi
echo ""

#--- Check 5: System time vs RTC drift ---
echo -e "${BOLD}[5/7] System Time vs RTC Drift${NC}"
SYSTEM_TIME=$(date '+%Y-%m-%d %H:%M:%S')
info "System time: $SYSTEM_TIME"

if [ "$RTC_STATUS" = "OK" ]; then
    info "RTC time:    $RTC_VALUE"
    
    DRIFT=$($PYTHON_CMD -c "
from datetime import datetime
sys_t = datetime.strptime('$SYSTEM_TIME', '%Y-%m-%d %H:%M:%S')
rtc_t = datetime.strptime('$RTC_VALUE', '%Y-%m-%d %H:%M:%S')
diff = abs((sys_t - rtc_t).total_seconds())
print(f'{diff:.1f}')
" 2>/dev/null || echo "unknown")
    
    if [ "$DRIFT" != "unknown" ]; then
        DRIFT_INT=${DRIFT%%.*}
        if [ "$DRIFT_INT" -le 2 ]; then
            pass "Drift is ${DRIFT}s (excellent, ≤2s)"
        elif [ "$DRIFT_INT" -le 60 ]; then
            warn "Drift is ${DRIFT}s (moderate, consider syncing)"
        else
            fail "Drift is ${DRIFT}s (excessive, >60s)"
            info "Run: sudo $PYTHON_CMD $PROJECT_ROOT/src/utils/set_rtc_from_system.py"
        fi
    fi
else
    warn "Cannot compare — RTC time unavailable"
fi
echo ""

#--- Check 6: Python smbus2 module ---
echo -e "${BOLD}[6/7] Python smbus2 Module${NC}"
SMBUS_CHECK=$($PYTHON_CMD -c "
try:
    import smbus2
    print('OK|' + smbus2.__version__ if hasattr(smbus2, '__version__') else 'OK|installed')
except ImportError:
    print('MISSING|not installed')
" 2>/dev/null || echo "ERROR|python error")

SMBUS_STATUS=$(echo "$SMBUS_CHECK" | cut -d'|' -f1)
SMBUS_VALUE=$(echo "$SMBUS_CHECK" | cut -d'|' -f2-)

if [ "$SMBUS_STATUS" = "OK" ]; then
    pass "smbus2 is installed ($SMBUS_VALUE)"
else
    fail "smbus2 is NOT installed"
    info "Install: $PYTHON_CMD -m pip install smbus2"
    info "Or offline: $PYTHON_CMD -m pip install $PROJECT_ROOT/packages_folder/smbus2*.whl"
fi
echo ""

#--- Check 7: RTC state file ---
echo -e "${BOLD}[7/7] RTC State File${NC}"
STATE_FILE="$PROJECT_ROOT/data/rtc_state.json"
if [ -f "$STATE_FILE" ]; then
    pass "State file exists: $STATE_FILE"
    LAST_GOOD=$($PYTHON_CMD -c "
import json
with open('$STATE_FILE') as f:
    s = json.load(f)
print(s.get('last_known_good_time', 'N/A'))
" 2>/dev/null || echo "N/A")
    info "Last known good time: $LAST_GOOD"
    
    BATTERY=$($PYTHON_CMD -c "
import json
with open('$STATE_FILE') as f:
    s = json.load(f)
print('OK' if s.get('rtc_battery_ok', True) else 'FAIL')
" 2>/dev/null || echo "unknown")
    
    if [ "$BATTERY" = "OK" ]; then
        pass "Battery status: OK"
    elif [ "$BATTERY" = "FAIL" ]; then
        fail "Battery status: FAILED — replace CR2032 battery!"
    fi
else
    warn "No state file yet (normal on first run)"
    info "Will be created when meter_manager runs"
fi
echo ""

#--- Summary ---
echo -e "${BOLD}══════════════════════════════════════════════════${NC}"
echo -e "${BOLD}SUMMARY${NC}"
echo -e "  ${GREEN}Passed: $PASS${NC}  |  ${RED}Failed: $FAIL${NC}  |  ${YELLOW}Warnings: $WARN${NC}"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}${BOLD}RTC has issues that need attention!${NC}"
    echo ""
    echo -e "${BOLD}QUICK FIX CHECKLIST:${NC}"
    echo "  1. Enable I2C:  sudo raspi-config → Interface Options → I2C"
    echo "  2. Install tools: sudo apt-get install -y i2c-tools python3-smbus"
    echo "  3. Install smbus2: pip install smbus2"
    echo "  4. Check wiring: SDA→pin3, SCL→pin5, VCC→pin1(3.3V), GND→pin9"
    echo "  5. Reboot after enabling I2C: sudo reboot"
    echo "  6. Set RTC time: sudo $PYTHON_CMD $PROJECT_ROOT/src/utils/set_rtc_from_system.py"
    exit 1
else
    echo -e "${GREEN}${BOLD}RTC is healthy! Time will be maintained when powered off.${NC}"
    exit 0
fi
