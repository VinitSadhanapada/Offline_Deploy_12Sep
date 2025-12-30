#!/bin/bash
# Quick Setup Launcher - For Terminal/SSH Access
# This is a simplified entry point for first-time setup via SSH

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

clear
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Raspberry Pi Meter System - Quick Setup Menu             ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "What would you like to do?"
echo ""
echo "  1) ${GREEN}Complete First-Time Setup${NC} (Run master_setup.sh)"
echo "     - Configure all system components"
echo "     - Enable auto-start, WiFi AP, static Ethernet"
echo "     - Requires sudo/root access"
echo ""
echo "  2) ${GREEN}Launch Terminal UI${NC} (View data, export CSV)"
echo "     - Interactive menu for meter readings"
echo "     - Download data via SCP"
echo "     - No sudo required"
echo ""
echo "  3) ${GREEN}Launch Desktop UI${NC} (If desktop available)"
echo "     - Full graphical interface"
echo "     - Meter configuration tool"
echo ""
echo "  4) ${GREEN}View System Status${NC}"
echo "     - Check services"
echo "     - View recent logs"
echo ""
echo "  5) ${GREEN}Exit${NC}"
echo ""
read -p "Select option [1-5]: " OPTION

case $OPTION in
    1)
        echo ""
        echo -e "${YELLOW}Running complete system setup...${NC}"
        echo "You will be prompted for sudo password"
        sleep 1
        sudo ./master_setup.sh
        ;;
    2)
        echo ""
        echo -e "${GREEN}Launching Terminal UI...${NC}"
        sleep 1
        ./terminal_ui.sh
        ;;
    3)
        echo ""
        if command -v python3 &> /dev/null; then
            echo -e "${GREEN}Launching Desktop UI...${NC}"
            python3 simple_meter_ui.py
        else
            echo -e "${YELLOW}Python3 not found. Install it first.${NC}"
        fi
        ;;
    4)
        echo ""
        echo -e "${CYAN}System Status:${NC}"
        echo ""
        echo "Dashboard Service:"
        systemctl is-active meter-dashboard 2>/dev/null || echo "  Not installed/running"
        echo ""
        echo "USB Download Service:"
        systemctl is-active usb-download-server 2>/dev/null || echo "  Not installed/running"
        echo ""
        echo "Disk Space:"
        df -h . | tail -1
        echo ""
        echo "Recent Logs (last 10 lines):"
        if [ -d logs ]; then
            tail -n 10 logs/*.log 2>/dev/null | head -20 || echo "  No logs found"
        else
            echo "  No logs directory"
        fi
        echo ""
        read -p "Press ENTER to continue..."
        ;;
    5)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo -e "${YELLOW}Invalid option${NC}"
        exit 1
        ;;
esac

exit 0
