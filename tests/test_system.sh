#!/bin/bash
# ============================================================================
# Unified System Test Script
# ============================================================================
# Combines preflight checks, quick validation, and full setup verification
# into a single file.
#
# Usage:
#   bash tests/test_system.sh              # Quick checks (no sudo needed)
#   sudo bash tests/test_system.sh --full  # Full end-to-end with services
# ============================================================================

set -eo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$SCRIPT_DIR/src" && -d "$SCRIPT_DIR/config" ]]; then
    PROJECT_ROOT="$SCRIPT_DIR"
else
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
cd "$PROJECT_ROOT"

# ── Colors ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Counters ───────────────────────────────────────────────────────────────
PASS=0
FAIL=0
WARN=0
declare -a FAILED_TESTS=()
declare -a WARN_TESTS=()

# ── Flags ──────────────────────────────────────────────────────────────────
FULL_TEST=0
for arg in "$@"; do
    case "$arg" in
        --full) FULL_TEST=1 ;;
        --help|-h)
            echo "Usage: bash tests/test_system.sh [--full]"
            echo ""
            echo "  (no flags)  Quick validation — file checks, syntax, config (no sudo)"
            echo "  --full      Full end-to-end — services, venv packages, permissions (needs sudo)"
            exit 0
            ;;
    esac
done

# ── Helpers ────────────────────────────────────────────────────────────────
test_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
    PASS=$((PASS + 1))
}

test_fail() {
    echo -e "  ${RED}✗${NC} $1"
    FAIL=$((FAIL + 1))
    FAILED_TESTS+=("$1")
}

test_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
    WARN=$((WARN + 1))
    WARN_TESTS+=("$1")
}

section() {
    echo ""
    echo -e "${BOLD}${BLUE}── $1 ──${NC}"
}

check_file()  { [[ -f "$1" ]] && test_pass "File: ${1#$PROJECT_ROOT/}" || test_fail "Missing: ${1#$PROJECT_ROOT/}"; }
check_dir()   { [[ -d "$1" ]] && test_pass "Dir:  ${1#$PROJECT_ROOT/}" || test_fail "Missing dir: ${1#$PROJECT_ROOT/}"; }
check_exec()  { [[ -x "$1" ]] && test_pass "Exec: ${1#$PROJECT_ROOT/}" || test_fail "Not executable: ${1#$PROJECT_ROOT/}"; }

check_json() {
    local f="$1"
    if [[ -f "$f" ]]; then
        if python3 -c "import json; json.load(open('$f'))" 2>/dev/null; then
            test_pass "Valid JSON: ${f#$PROJECT_ROOT/}"
        else
            test_fail "Invalid JSON: ${f#$PROJECT_ROOT/}"
        fi
    else
        test_fail "Missing: ${f#$PROJECT_ROOT/}"
    fi
}

check_syntax() {
    local f="$1"
    if [[ -f "$f" ]]; then
        if python3 -m py_compile "$f" 2>/dev/null; then
            test_pass "Syntax OK: ${f#$PROJECT_ROOT/}"
        else
            test_fail "Syntax error: ${f#$PROJECT_ROOT/}"
        fi
    else
        test_fail "Missing: ${f#$PROJECT_ROOT/}"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
if [[ "$FULL_TEST" -eq 1 ]]; then
echo -e "${CYAN}║  System Test — FULL (requires sudo)                       ║${NC}"
else
echo -e "${CYAN}║  System Test — Quick Validation                           ║${NC}"
fi
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Project: $PROJECT_ROOT"
echo "  Date:    $(date)"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: Preflight / Environment
# ═══════════════════════════════════════════════════════════════════════════
section "1. Environment"

# Python
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
    PY_MAJOR_MINOR=$(echo "$PY_VER" | cut -d. -f1,2)
    test_pass "python3 installed ($PY_VER)"
else
    test_fail "python3 not found"
fi

# Git
if command -v git &>/dev/null; then
    test_pass "git installed"
    if [[ -d "$PROJECT_ROOT/.git" ]]; then
        GIT_BRANCH=$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null || echo "unknown")
        DIRTY=$(git -C "$PROJECT_ROOT" status --porcelain 2>/dev/null | wc -l)
        test_pass "Git branch: $GIT_BRANCH"
        if [[ "$DIRTY" -gt 0 ]]; then
            test_warn "Uncommitted changes: $DIRTY file(s)"
        else
            test_pass "Working tree clean"
        fi
    fi
else
    test_warn "git not installed"
fi

# Disk space
DISK_AVAIL=$(df -h "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
test_pass "Disk available: $DISK_AVAIL"

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: Directory Structure
# ═══════════════════════════════════════════════════════════════════════════
section "2. Directory Structure"

for d in src src/dashboard src/devices src/network src/utils \
         scripts scripts/setup scripts/launchers \
         config data data/csv logs exports \
         packages_folder usb_download_mvp docs tests tools; do
    check_dir "$PROJECT_ROOT/$d"
done

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: Core Python Files
# ═══════════════════════════════════════════════════════════════════════════
section "3. Core Python Files — existence"

for f in \
    src/dashboard/simple_rpi_dashboard.py \
    src/dashboard/simple_meter_ui.py \
    src/dashboard/terminal_meter_ui.py \
    src/devices/meter_manager.py \
    src/devices/meter_device.py \
    src/utils/configure_device.py \
    src/utils/macros.py \
    src/utils/paths.py \
    src/network/cloud_sync.py \
    src/network/mqtt_client.py; do
    check_file "$PROJECT_ROOT/$f"
done

section "3b. Python Syntax Check"

for f in \
    src/dashboard/simple_rpi_dashboard.py \
    src/dashboard/simple_meter_ui.py \
    src/dashboard/terminal_meter_ui.py \
    src/devices/meter_manager.py \
    src/devices/meter_device.py; do
    check_syntax "$PROJECT_ROOT/$f"
done

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: Setup & Launcher Scripts
# ═══════════════════════════════════════════════════════════════════════════
section "4. Setup & Launcher Scripts"

for f in \
    master_setup.sh \
    scripts/setup/master_setup.sh \
    scripts/setup/one_click_system_py313.sh \
    scripts/setup/enable_auto_start.sh \
    scripts/setup/setup_static_ethernet.sh \
    terminal_ui.sh; do
    check_file "$PROJECT_ROOT/$f"
    check_exec "$PROJECT_ROOT/$f"
done

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: Configuration
# ═══════════════════════════════════════════════════════════════════════════
section "5. Configuration Files"

check_json "$PROJECT_ROOT/config/config.json"
check_json "$PROJECT_ROOT/config/device_config.json"

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: Offline Packages
# ═══════════════════════════════════════════════════════════════════════════
section "6. Offline Wheels"

for pkg in pymodbus paho_mqtt pandas pyserial numpy termcolor smbus2; do
    if ls "$PROJECT_ROOT/packages_folder/"*"$pkg"*.whl &>/dev/null; then
        test_pass "Wheel: $pkg"
    else
        test_fail "Missing wheel: $pkg"
    fi
done

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: Documentation
# ═══════════════════════════════════════════════════════════════════════════
section "7. Documentation"

check_file "$PROJECT_ROOT/README.md"
check_dir  "$PROJECT_ROOT/docs/user"
check_dir  "$PROJECT_ROOT/docs/developer"

# ═══════════════════════════════════════════════════════════════════════════
# FULL-TEST-ONLY SECTIONS (require sudo)
# ═══════════════════════════════════════════════════════════════════════════
if [[ "$FULL_TEST" -eq 1 ]]; then

    if [[ "$EUID" -ne 0 ]]; then
        echo ""
        test_fail "Full test requires sudo — re-run: sudo bash tests/test_system.sh --full"
        # skip to summary
    else

    ACTUAL_USER="${SUDO_USER:-${USER:-pi}}"

    # ───────────────────────────────────────────────────────────────────────
    section "8. Python Virtual Environment"
    # ───────────────────────────────────────────────────────────────────────
    VENV_DIR="$PROJECT_ROOT/venv"
    if [[ -x "$VENV_DIR/bin/python" ]]; then
        test_pass "venv exists at $VENV_DIR"
        VENV_PY_VER=$("$VENV_DIR/bin/python" --version 2>&1 | awk '{print $2}')
        test_pass "venv Python: $VENV_PY_VER"

        for mod in numpy pandas pymodbus serial paho.mqtt.client termcolor smbus2; do
            if "$VENV_DIR/bin/python" -c "import $mod" 2>/dev/null; then
                test_pass "Module: $mod"
            else
                test_fail "Missing module: $mod"
            fi
        done
    else
        test_fail "venv not found — run master_setup.sh first"
    fi

    # ───────────────────────────────────────────────────────────────────────
    section "9. Systemd Services"
    # ───────────────────────────────────────────────────────────────────────
    for svc in meter-dashboard; do
        if systemctl list-unit-files | grep -q "${svc}.service"; then
            if systemctl is-active "$svc" &>/dev/null; then
                test_pass "Service $svc: active"
            else
                test_warn "Service $svc: installed but not running"
            fi
        else
            test_warn "Service $svc: not installed (run master_setup.sh)"
        fi
    done

    for svc in usb_csv_auto_copy cloud_sync; do
        if systemctl list-unit-files | grep -q "${svc}"; then
            test_pass "Service $svc: installed"
        else
            test_warn "Service $svc: not installed"
        fi
    done

    # ───────────────────────────────────────────────────────────────────────
    section "10. Network"
    # ───────────────────────────────────────────────────────────────────────
    if ip addr show eth0 &>/dev/null; then
        ETH_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
        if [[ -n "$ETH_IP" ]]; then
            test_pass "eth0 IP: $ETH_IP"
        else
            test_warn "eth0 exists but has no IP (cable disconnected?)"
        fi
    else
        test_warn "eth0 not found"
    fi

    # ───────────────────────────────────────────────────────────────────────
    section "11. User Groups"
    # ───────────────────────────────────────────────────────────────────────
    for grp in dialout i2c gpio; do
        if groups "$ACTUAL_USER" 2>/dev/null | grep -q "$grp"; then
            test_pass "$ACTUAL_USER in $grp group"
        else
            test_warn "$ACTUAL_USER NOT in $grp group"
        fi
    done

    # ───────────────────────────────────────────────────────────────────────
    section "12. Data & Logs"
    # ───────────────────────────────────────────────────────────────────────
    # Writable check
    if touch "$PROJECT_ROOT/data/csv/.write_test" 2>/dev/null; then
        rm -f "$PROJECT_ROOT/data/csv/.write_test"
        test_pass "data/csv/ is writable"
    else
        test_fail "data/csv/ is NOT writable"
    fi

    if [[ -f "$PROJECT_ROOT/exports/DATA_ALL.csv" ]]; then
        LINES=$(wc -l < "$PROJECT_ROOT/exports/DATA_ALL.csv")
        test_pass "DATA_ALL.csv exists ($LINES lines)"
    else
        test_warn "DATA_ALL.csv not found (no data collected yet)"
    fi

    LATEST_LOG=$(ls -t "$PROJECT_ROOT/logs/"master_setup*.log 2>/dev/null | head -1)
    if [[ -n "$LATEST_LOG" ]]; then
        test_pass "Setup log found: $(basename "$LATEST_LOG")"
    else
        test_warn "No setup log yet"
    fi

    # ───────────────────────────────────────────────────────────────────────
    section "13. File Permissions"
    # ───────────────────────────────────────────────────────────────────────
    SCRIPT_COUNT=0; EXEC_COUNT=0
    while IFS= read -r -d '' s; do
        SCRIPT_COUNT=$((SCRIPT_COUNT + 1))
        [[ -x "$s" ]] && EXEC_COUNT=$((EXEC_COUNT + 1))
    done < <(find "$PROJECT_ROOT/scripts" -name "*.sh" -type f -print0 2>/dev/null)

    if [[ "$EXEC_COUNT" -eq "$SCRIPT_COUNT" && "$SCRIPT_COUNT" -gt 0 ]]; then
        test_pass "All $SCRIPT_COUNT scripts in scripts/ are executable"
    else
        test_fail "Only $EXEC_COUNT/$SCRIPT_COUNT scripts are executable"
    fi

    fi  # end sudo check
fi  # end --full

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}Passed:${NC}   $PASS"
echo -e "  ${YELLOW}Warnings:${NC} $WARN"
echo -e "  ${RED}Failed:${NC}   $FAIL"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"

if [[ ${#FAILED_TESTS[@]} -gt 0 ]]; then
    echo ""
    echo -e "${RED}Failed:${NC}"
    for t in "${FAILED_TESTS[@]}"; do echo "  - $t"; done
fi

if [[ ${#WARN_TESTS[@]} -gt 0 ]]; then
    echo ""
    echo -e "${YELLOW}Warnings:${NC}"
    for t in "${WARN_TESTS[@]}"; do echo "  - $t"; done
fi

echo ""
if [[ "$FULL_TEST" -eq 0 ]]; then
    echo "Run full test:  sudo bash tests/test_system.sh --full"
fi

if [[ "$FAIL" -eq 0 ]]; then
    echo -e "${GREEN}ALL TESTS PASSED${NC}"
    exit 0
else
    echo -e "${RED}SOME TESTS FAILED${NC}"
    exit 1
fi
