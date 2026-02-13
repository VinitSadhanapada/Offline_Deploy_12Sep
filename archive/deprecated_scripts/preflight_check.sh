#!/bin/bash
# Pre-flight checks before running full test
# This validates the workspace is ready for testing

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Pre-Flight Checklist"
echo "===================="
echo ""

# 1. Check we're in the right directory
if [ ! -f "README.md" ] || [ ! -d "setup_launchers" ]; then
    echo -e "${RED}ERROR: Not in correct directory${NC}"
    echo "Please run from: ~/Desktop/offline-setup-12Sep"
    exit 1
fi
echo -e "${GREEN}✓${NC} In correct directory: $SCRIPT_DIR"

# 2. Check Python version
PYTHON_VER=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo -e "${GREEN}✓${NC} Python version: $PYTHON_VER"

# 3. Check git status (if in repo)
if [ -d ".git" ]; then
    GIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
    GIT_STATUS=$(git status --porcelain 2>/dev/null | wc -l)
    echo -e "${GREEN}✓${NC} Git branch: $GIT_BRANCH"
    if [ "$GIT_STATUS" -gt 0 ]; then
        echo -e "${YELLOW}⚠${NC} Uncommitted changes: $GIT_STATUS files"
    else
        echo -e "${GREEN}✓${NC} Git status: clean"
    fi
else
    echo -e "${YELLOW}⚠${NC} Not a git repository"
fi

# 4. Check if this is a fresh system or existing setup
if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠${NC} Virtual environment exists (previous setup detected)"
    echo "   This appears to be an EXISTING installation"
    echo "   Test will validate current setup"
else
    echo -e "${GREEN}✓${NC} No venv found (fresh system)"
    echo "   This appears to be a FRESH installation"
    echo "   Test will run full setup"
fi

# 5. Check for systemd service
if systemctl list-unit-files | grep -q "meter-dashboard"; then
    SERVICE_STATUS=$(systemctl is-active meter-dashboard 2>/dev/null || echo "inactive")
    echo -e "${YELLOW}⚠${NC} Service 'meter-dashboard' exists (status: $SERVICE_STATUS)"
else
    echo -e "${GREEN}✓${NC} No service installed (fresh system)"
fi

# 6. Check disk space
DISK_AVAIL=$(df -h "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
echo -e "${GREEN}✓${NC} Available disk space: $DISK_AVAIL"

# 7. Check if running as sudo
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}✗${NC} Running as root/sudo"
    echo "   Pre-flight should run as normal user"
    echo "   (Test script will ask for sudo when needed)"
else
    echo -e "${GREEN}✓${NC} Running as normal user"
fi

# 8. Check test dependencies
if [ -f "test_complete_setup.sh" ]; then
    echo -e "${GREEN}✓${NC} Test script exists"
    if [ -x "test_complete_setup.sh" ]; then
        echo -e "${GREEN}✓${NC} Test script is executable"
    else
        echo -e "${RED}✗${NC} Test script not executable"
        echo "   Run: chmod +x test_complete_setup.sh"
    fi
else
    echo -e "${RED}✗${NC} Test script not found"
fi

echo ""
echo "===================="
echo "Pre-Flight Complete"
echo "===================="
echo ""
echo "Next steps:"
echo "1. Review any warnings above"
echo "2. Run comprehensive test:"
echo "   sudo bash test_complete_setup.sh"
echo ""
echo "Or run quick test first:"
echo "   bash quick_test.sh"
echo ""
