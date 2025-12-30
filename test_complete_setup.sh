#!/bin/bash
# Complete Setup Test Script
# Tests all components end-to-end on a fresh Raspberry Pi
# Usage: sudo bash test_complete_setup.sh

set -eo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNING=0
declare -a FAILED_TESTS
declare -a WARNING_TESTS

# Logging
TEST_LOG="/tmp/setup_test_$(date +%Y%m%d_%H%M%S).log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Redirect all output to both console and log
exec > >(tee -a "$TEST_LOG") 2>&1

echo "========================================="
echo "COMPLETE SETUP TEST SUITE"
echo "========================================="
echo "Started: $(date)"
echo "Script Dir: $SCRIPT_DIR"
echo "Log File: $TEST_LOG"
echo ""

# Helper functions
test_header() {
    echo ""
    echo -e "${BLUE}[TEST]${NC} $1"
    echo "========================================="
}

test_pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

test_fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    FAILED_TESTS+=("$1")
}

test_warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
    TESTS_WARNING=$((TESTS_WARNING + 1))
    WARNING_TESTS+=("$1")
}

check_command() {
    if command -v "$1" &> /dev/null; then
        test_pass "Command '$1' exists"
        return 0
    else
        test_fail "Command '$1' not found"
        return 1
    fi
}

check_file() {
    if [ -f "$1" ]; then
        test_pass "File exists: $1"
        return 0
    else
        test_fail "File not found: $1"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        test_pass "Directory exists: $1"
        return 0
    else
        test_fail "Directory not found: $1"
        return 1
    fi
}

check_executable() {
    if [ -x "$1" ]; then
        test_pass "File is executable: $1"
        return 0
    else
        test_fail "File not executable: $1"
        return 1
    fi
}

check_service() {
    if systemctl is-enabled "$1" &> /dev/null; then
        if systemctl is-active "$1" &> /dev/null; then
            test_pass "Service '$1' is enabled and running"
            return 0
        else
            test_warn "Service '$1' is enabled but not running"
            return 1
        fi
    else
        test_fail "Service '$1' is not enabled"
        return 1
    fi
}

check_python_module() {
    if python3 -c "import $1" 2>/dev/null; then
        test_pass "Python module '$1' is installed"
        return 0
    else
        test_fail "Python module '$1' not found"
        return 1
    fi
}

#############################################################################
# TEST 1: Pre-requisites
#############################################################################
test_header "1. System Pre-requisites"

check_command "python3"
check_command "git"
check_command "systemctl"
check_command "sudo"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2 || echo "unknown")
if [ "$PYTHON_VERSION" = "3.13" ] || [ "$PYTHON_VERSION" = "3.11" ] || [ "$PYTHON_VERSION" = "3.12" ] || [ "$PYTHON_VERSION" = "3.9" ] || [ "$PYTHON_VERSION" = "3.10" ]; then
    test_pass "Python version $PYTHON_VERSION is compatible"
else
    test_warn "Python version $PYTHON_VERSION (expected 3.9+)"
fi

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then
    test_fail "Script must be run with sudo"
    echo ""
    echo "Please run: sudo bash $0"
    exit 1
else
    test_pass "Running with sudo privileges"
fi

# Get actual user
ACTUAL_USER="${SUDO_USER:-${USER:-pi}}"
test_pass "Detected user: $ACTUAL_USER"

#############################################################################
# TEST 2: Workspace Structure
#############################################################################
test_header "2. Workspace Structure"

cd "$SCRIPT_DIR" || { test_fail "Cannot cd to $SCRIPT_DIR"; exit 1; }

# Check core directories
check_dir "$SCRIPT_DIR/setup_launchers"
check_dir "$SCRIPT_DIR/docs"
check_dir "$SCRIPT_DIR/data"
check_dir "$SCRIPT_DIR/data/csv"
check_dir "$SCRIPT_DIR/logs"
check_dir "$SCRIPT_DIR/packages_folder"
check_dir "$SCRIPT_DIR/usb_download_mvp"
check_dir "$SCRIPT_DIR/compat"
check_dir "$SCRIPT_DIR/tools"
check_dir "$SCRIPT_DIR/examples"

# Check symlinks
if [ -L "$SCRIPT_DIR/quick_start" ]; then
    test_pass "Symlink exists: quick_start"
    TARGET=$(readlink "$SCRIPT_DIR/quick_start")
    test_pass "  → Points to: $TARGET"
else
    test_fail "Symlink missing: quick_start"
fi

if [ -L "$SCRIPT_DIR/complete_setup" ]; then
    test_pass "Symlink exists: complete_setup"
    TARGET=$(readlink "$SCRIPT_DIR/complete_setup")
    test_pass "  → Points to: $TARGET"
else
    test_fail "Symlink missing: complete_setup"
fi

if [ -L "$SCRIPT_DIR/QUICKSTART.md" ]; then
    test_pass "Symlink exists: QUICKSTART.md"
else
    test_warn "Symlink missing: QUICKSTART.md"
fi

#############################################################################
# TEST 3: Setup Scripts
#############################################################################
test_header "3. Setup Scripts"

# Check setup scripts exist and are executable
check_file "$SCRIPT_DIR/setup_launchers/master_setup.sh"
check_executable "$SCRIPT_DIR/setup_launchers/master_setup.sh"

check_file "$SCRIPT_DIR/setup_launchers/quick_setup.sh"
check_executable "$SCRIPT_DIR/setup_launchers/quick_setup.sh"

check_file "$SCRIPT_DIR/setup_launchers/enable_auto_start.sh"
check_executable "$SCRIPT_DIR/setup_launchers/enable_auto_start.sh"

check_file "$SCRIPT_DIR/setup_launchers/setup_static_ethernet.sh"
check_executable "$SCRIPT_DIR/setup_launchers/setup_static_ethernet.sh"

# Check core scripts
check_file "$SCRIPT_DIR/terminal_ui.sh"
check_file "$SCRIPT_DIR/one_click_system_py313.sh"
check_file "$SCRIPT_DIR/download_meter_data.sh"

#############################################################################
# TEST 4: Core Python Files
#############################################################################
test_header "4. Core Python Files"

declare -a CORE_FILES=(
    "simple_rpi_dashboard.py"
    "simple_meter_ui.py"
    "terminal_meter_ui.py"
    "meter_manager.py"
    "meter_device.py"
    "mqtt_client.py"
    "cloud_sync.py"
    "configure_device.py"
    "macros.py"
    "paths.py"
)

for file in "${CORE_FILES[@]}"; do
    check_file "$SCRIPT_DIR/$file"
done

# Check device drivers
check_file "$SCRIPT_DIR/elmeasure_EN8410.py"
check_file "$SCRIPT_DIR/elmeasure_iELR300.py"
check_file "$SCRIPT_DIR/elmeasure_LG5220.py"
check_file "$SCRIPT_DIR/elmeasure_LG5310.py"
check_file "$SCRIPT_DIR/elmeasure_LG6400.py"

#############################################################################
# TEST 5: Configuration Files
#############################################################################
test_header "5. Configuration Files"

if [ -f "$SCRIPT_DIR/config.json" ]; then
    test_pass "Config file exists: config.json"
    # Validate JSON
    if python3 -c "import json; json.load(open('$SCRIPT_DIR/config.json'))" 2>/dev/null; then
        test_pass "config.json is valid JSON"
    else
        test_fail "config.json is invalid JSON"
    fi
else
    test_warn "config.json not found (will be created by setup)"
fi

if [ -f "$SCRIPT_DIR/device_config.json" ]; then
    test_pass "Device config exists: device_config.json"
    if python3 -c "import json; json.load(open('$SCRIPT_DIR/device_config.json'))" 2>/dev/null; then
        test_pass "device_config.json is valid JSON"
    else
        test_fail "device_config.json is invalid JSON"
    fi
else
    test_warn "device_config.json not found (will be created by setup)"
fi

#############################################################################
# TEST 6: Documentation
#############################################################################
test_header "6. Documentation"

check_file "$SCRIPT_DIR/README.md"
check_file "$SCRIPT_DIR/WORKSPACE_ORGANIZATION.md"
check_file "$SCRIPT_DIR/docs/SETUP_GUIDE.md"
check_file "$SCRIPT_DIR/docs/QUICKSTART_SSH_UI.md"
check_file "$SCRIPT_DIR/docs/README_SSH_TERMINAL_UI.md"

#############################################################################
# TEST 7: Desktop Files
#############################################################################
test_header "7. Desktop Shortcuts"

check_file "$SCRIPT_DIR/setup_launchers/MasterSetup_Admin.desktop"
check_file "$SCRIPT_DIR/setup_launchers/SimpleMeterUI_Admin.desktop"

# Check if desktop files have correct paths
if grep -q "setup_launchers/master_setup.sh" "$SCRIPT_DIR/setup_launchers/MasterSetup_Admin.desktop"; then
    test_pass "MasterSetup_Admin.desktop has correct path"
else
    test_fail "MasterSetup_Admin.desktop has incorrect path"
fi

#############################################################################
# TEST 8: Offline Packages
#############################################################################
test_header "8. Offline Python Packages"

declare -a REQUIRED_WHEELS=(
    "pymodbus"
    "paho_mqtt"
    "pandas"
    "pyserial"
)

for pkg in "${REQUIRED_WHEELS[@]}"; do
    if ls "$SCRIPT_DIR/packages_folder/"*"$pkg"*.whl &> /dev/null; then
        test_pass "Found wheel for: $pkg"
    else
        test_fail "Missing wheel for: $pkg"
    fi
done

#############################################################################
# TEST 9: Run Master Setup (Interactive)
#############################################################################
test_header "9. Master Setup Execution"

echo ""
echo -e "${YELLOW}Ready to run master_setup.sh${NC}"
echo "This will:"
echo "  1. Make all scripts executable"
echo "  2. Create required directories"
echo "  3. Set up Python venv with offline packages"
echo "  4. Configure static Ethernet IP"
echo "  5. Enable systemd auto-start service"
echo "  6. Set up USB download server"
echo "  7. Create default config files"
echo "  8. Add user to dialout/gpio groups"
echo ""
read -p "Continue with master_setup.sh? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Running master_setup.sh..."
    echo "========================================="
    
    if bash "$SCRIPT_DIR/setup_launchers/master_setup.sh"; then
        test_pass "master_setup.sh completed successfully"
    else
        test_fail "master_setup.sh failed with exit code $?"
        echo ""
        echo "Check the log for details"
    fi
else
    test_warn "Skipped master_setup.sh execution"
    echo ""
    echo -e "${YELLOW}Note: Remaining tests require master_setup.sh to have run${NC}"
fi

#############################################################################
# TEST 10: Python Virtual Environment
#############################################################################
test_header "10. Python Virtual Environment"

if [ -d "$SCRIPT_DIR/venv" ]; then
    test_pass "Virtual environment exists"
    
    # Check venv Python
    if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
        test_pass "venv Python executable exists"
        
        # Activate and check modules
        source "$SCRIPT_DIR/venv/bin/activate"
        
        check_python_module "serial"
        check_python_module "pymodbus"
        check_python_module "paho.mqtt.client"
        check_python_module "pandas"
        
        deactivate
    else
        test_fail "venv Python executable not found"
    fi
else
    test_warn "Virtual environment not found (master_setup.sh needed)"
fi

#############################################################################
# TEST 11: Systemd Services
#############################################################################
test_header "11. Systemd Services"

# Check meter-dashboard service
if systemctl list-unit-files | grep -q "meter-dashboard.service"; then
    check_service "meter-dashboard"
    
    # Check service file content
    if systemctl cat meter-dashboard.service | grep -q "$SCRIPT_DIR"; then
        test_pass "Service file has correct WorkingDirectory"
    else
        test_warn "Service file may have incorrect paths"
    fi
else
    test_warn "meter-dashboard.service not installed (master_setup.sh needed)"
fi

# Check USB download server service
if systemctl list-unit-files | grep -q "usb-download-server.service"; then
    test_pass "usb-download-server.service exists"
else
    test_warn "usb-download-server.service not installed"
fi

#############################################################################
# TEST 12: Network Configuration
#############################################################################
test_header "12. Network Configuration"

if [ -f "/etc/dhcpcd.conf" ]; then
    if grep -q "192.168.137.2" "/etc/dhcpcd.conf"; then
        test_pass "Static Ethernet IP configured (192.168.137.2)"
    else
        test_warn "Static Ethernet IP not configured"
    fi
else
    test_warn "/etc/dhcpcd.conf not found"
fi

# Check network interfaces
if ip addr show eth0 &> /dev/null; then
    test_pass "Ethernet interface (eth0) exists"
    
    ETH_IP=$(ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
    if [ -n "$ETH_IP" ]; then
        test_pass "Ethernet has IP: $ETH_IP"
    else
        test_warn "Ethernet has no IP (cable may not be connected)"
    fi
else
    test_warn "Ethernet interface (eth0) not found"
fi

#############################################################################
# TEST 13: User Groups
#############################################################################
test_header "13. User Groups"

if groups "$ACTUAL_USER" | grep -q "dialout"; then
    test_pass "User '$ACTUAL_USER' in dialout group"
else
    test_fail "User '$ACTUAL_USER' NOT in dialout group"
fi

if groups "$ACTUAL_USER" | grep -q "gpio"; then
    test_pass "User '$ACTUAL_USER' in gpio group"
else
    test_warn "User '$ACTUAL_USER' NOT in gpio group"
fi

#############################################################################
# TEST 14: Terminal UI Test
#############################################################################
test_header "14. Terminal UI Validation"

check_file "$SCRIPT_DIR/terminal_meter_ui.py"

# Syntax check
if python3 -m py_compile "$SCRIPT_DIR/terminal_meter_ui.py" 2>/dev/null; then
    test_pass "terminal_meter_ui.py syntax is valid"
else
    test_fail "terminal_meter_ui.py has syntax errors"
fi

# Check terminal_ui.sh wrapper
if [ -f "$SCRIPT_DIR/terminal_ui.sh" ]; then
    if grep -q "terminal_meter_ui.py" "$SCRIPT_DIR/terminal_ui.sh"; then
        test_pass "terminal_ui.sh wrapper is correct"
    else
        test_fail "terminal_ui.sh wrapper incorrect"
    fi
else
    test_fail "terminal_ui.sh not found"
fi

#############################################################################
# TEST 15: Simple Meter UI Test
#############################################################################
test_header "15. Simple Meter UI Validation"

check_file "$SCRIPT_DIR/simple_meter_ui.py"

if python3 -m py_compile "$SCRIPT_DIR/simple_meter_ui.py" 2>/dev/null; then
    test_pass "simple_meter_ui.py syntax is valid"
else
    test_fail "simple_meter_ui.py has syntax errors"
fi

#############################################################################
# TEST 16: Dashboard Test
#############################################################################
test_header "16. Dashboard Validation"

check_file "$SCRIPT_DIR/simple_rpi_dashboard.py"

if python3 -m py_compile "$SCRIPT_DIR/simple_rpi_dashboard.py" 2>/dev/null; then
    test_pass "simple_rpi_dashboard.py syntax is valid"
else
    test_fail "simple_rpi_dashboard.py has syntax errors"
fi

#############################################################################
# TEST 17: Log Files
#############################################################################
test_header "17. Log Files Analysis"

# Check for setup logs
LATEST_SETUP_LOG=$(ls -t "$SCRIPT_DIR/logs/"master_setup*.log 2>/dev/null | head -1)
if [ -n "$LATEST_SETUP_LOG" ]; then
    test_pass "Found setup log: $(basename "$LATEST_SETUP_LOG")"
    
    # Check for errors in log
    if grep -qi "error" "$LATEST_SETUP_LOG"; then
        ERROR_COUNT=$(grep -ci "error" "$LATEST_SETUP_LOG")
        test_warn "Found $ERROR_COUNT 'error' mentions in setup log"
        echo "  Last 5 error lines:"
        grep -i "error" "$LATEST_SETUP_LOG" | tail -5 | sed 's/^/    /'
    else
        test_pass "No errors found in setup log"
    fi
    
    # Check for failures
    if grep -qi "fail" "$LATEST_SETUP_LOG"; then
        FAIL_COUNT=$(grep -ci "fail" "$LATEST_SETUP_LOG")
        test_warn "Found $FAIL_COUNT 'fail' mentions in setup log"
    else
        test_pass "No failures found in setup log"
    fi
else
    test_warn "No setup log found (master_setup.sh not run yet)"
fi

# Check enable_auto_start logs
if ls "$SCRIPT_DIR/logs/"enable_auto_start*.log &> /dev/null; then
    LATEST_AUTOSTART_LOG=$(ls -t "$SCRIPT_DIR/logs/"enable_auto_start*.log 2>/dev/null | head -1)
    test_pass "Found auto-start log: $(basename "$LATEST_AUTOSTART_LOG")"
else
    test_warn "No auto-start logs found"
fi

#############################################################################
# TEST 18: File Permissions
#############################################################################
test_header "18. File Permissions"

# Check script permissions
SCRIPT_COUNT=0
EXEC_COUNT=0

for script in "$SCRIPT_DIR/setup_launchers/"*.sh; do
    ((SCRIPT_COUNT++))
    if [ -x "$script" ]; then
        ((EXEC_COUNT++))
    fi
done

if [ $EXEC_COUNT -eq $SCRIPT_COUNT ]; then
    test_pass "All $SCRIPT_COUNT scripts in setup_launchers/ are executable"
else
    test_fail "Only $EXEC_COUNT of $SCRIPT_COUNT scripts are executable"
fi

# Check Python files
for pyfile in terminal_meter_ui.py simple_meter_ui.py simple_rpi_dashboard.py; do
    if [ -r "$SCRIPT_DIR/$pyfile" ]; then
        test_pass "Python file readable: $pyfile"
    else
        test_fail "Python file not readable: $pyfile"
    fi
done

#############################################################################
# TEST 19: USB Download Server
#############################################################################
test_header "19. USB Download Server"

check_dir "$SCRIPT_DIR/usb_download_mvp"
check_file "$SCRIPT_DIR/usb_download_mvp/server.py"
check_file "$SCRIPT_DIR/usb_download_mvp/config.py"

if [ -d "$SCRIPT_DIR/usb_download_mvp/scripts" ]; then
    test_pass "USB download scripts directory exists"
else
    test_fail "USB download scripts directory missing"
fi

#############################################################################
# TEST 20: Data Directory
#############################################################################
test_header "20. Data Directory"

if [ -f "$SCRIPT_DIR/data/csv/readings_all.csv" ]; then
    test_pass "readings_all.csv exists"
    
    # Check if file has content
    if [ -s "$SCRIPT_DIR/data/csv/readings_all.csv" ]; then
        LINE_COUNT=$(wc -l < "$SCRIPT_DIR/data/csv/readings_all.csv")
        test_pass "readings_all.csv has $LINE_COUNT lines"
    else
        test_warn "readings_all.csv is empty (no data collected yet)"
    fi
else
    test_warn "readings_all.csv not found (no data collected yet)"
fi

# Check CSV file permissions
if touch "$SCRIPT_DIR/data/csv/test_write.csv" 2>/dev/null; then
    rm "$SCRIPT_DIR/data/csv/test_write.csv"
    test_pass "CSV directory is writable"
else
    test_fail "CSV directory is not writable"
fi

#############################################################################
# FINAL SUMMARY
#############################################################################
echo ""
echo "========================================="
echo "TEST SUMMARY"
echo "========================================="
echo -e "${GREEN}Passed:${NC}   $TESTS_PASSED"
echo -e "${YELLOW}Warnings:${NC} $TESTS_WARNING"
echo -e "${RED}Failed:${NC}   $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}FAILED TESTS:${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  - $test"
    done
    echo ""
fi

if [ $TESTS_WARNING -gt 0 ]; then
    echo -e "${YELLOW}WARNINGS:${NC}"
    for test in "${WARNING_TESTS[@]}"; do
        echo "  - $test"
    done
    echo ""
fi

echo "Full log saved to: $TEST_LOG"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}ALL CRITICAL TESTS PASSED!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    exit 0
else
    echo -e "${RED}=========================================${NC}"
    echo -e "${RED}SOME TESTS FAILED - REVIEW REQUIRED${NC}"
    echo -e "${RED}=========================================${NC}"
    exit 1
fi
