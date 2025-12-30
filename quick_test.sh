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

# Core files
check "master_setup.sh exists" "[ -f setup_launchers/master_setup.sh ]"
check "terminal_meter_ui.py exists" "[ -f terminal_meter_ui.py ]"
check "simple_meter_ui.py exists" "[ -f simple_meter_ui.py ]"

# Symlinks
check "quick_start symlink works" "[ -L quick_start ]"
check "complete_setup symlink works" "[ -L complete_setup ]"

# Executability
check "master_setup.sh executable" "[ -x setup_launchers/master_setup.sh ]"
check "terminal_ui.sh executable" "[ -x terminal_ui.sh ]"

# Python syntax
check "terminal_meter_ui.py syntax" "python3 -m py_compile terminal_meter_ui.py"
check "simple_meter_ui.py syntax" "python3 -m py_compile simple_meter_ui.py"

# Config files
check "config.json valid JSON" "python3 -c 'import json; json.load(open(\"config.json\"))'"
check "device_config.json valid JSON" "python3 -c 'import json; json.load(open(\"device_config.json\"))'"

# Documentation
check "README.md exists" "[ -f README.md ]"
check "TESTING_GUIDE.md exists" "[ -f TESTING_GUIDE.md ]"

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
