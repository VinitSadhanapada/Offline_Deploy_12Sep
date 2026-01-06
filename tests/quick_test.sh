#!/bin/bash
# Quick Test - Fast validation of critical components
# Use this for rapid iteration testing
# Usage: bash quick_test.sh

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
    if eval "$2" &>/dev/null; then
        echo -e "${GREEN}✓${NC} $1"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $1"
        ((FAIL++))
    fi
}

echo "Quick Test - Critical Components"
echo "=================================="

# Core files (now in src/dashboard/)
check "master_setup.sh exists" "[ -f scripts/setup/master_setup.sh ]"
check "terminal_meter_ui.py exists" "[ -f src/dashboard/terminal_meter_ui.py ]"
check "simple_meter_ui.py exists" "[ -f src/dashboard/simple_meter_ui.py ]"

# Launcher scripts
check "terminal_ui.sh exists" "[ -f scripts/launchers/terminal_ui.sh ]"

# Executability
check "master_setup.sh executable" "[ -x scripts/setup/master_setup.sh ]"
check "terminal_ui.sh executable" "[ -x scripts/launchers/terminal_ui.sh ]"

# Python syntax
check "terminal_meter_ui.py syntax" "python3 -m py_compile src/dashboard/terminal_meter_ui.py"
check "simple_meter_ui.py syntax" "python3 -m py_compile src/dashboard/simple_meter_ui.py"

# Config files (now in config/ directory)
check "config.json valid JSON" "python3 -c 'import json; json.load(open(\"config/config.json\"))'"
check "device_config.json valid JSON" "python3 -c 'import json; json.load(open(\"config/device_config.json\"))'"

# Documentation
check "README.md exists" "[ -f README.md ]"

echo ""
echo "=================================="
echo -e "Passed: ${GREEN}$PASS${NC}  Failed: ${RED}$FAIL${NC}"

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}Ready for full test!${NC}"
    echo "Run: sudo bash test_complete_setup.sh"
    exit 0
else
    echo -e "${RED}Fix failures before full test${NC}"
    exit 1
fi
