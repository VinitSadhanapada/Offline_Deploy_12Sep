#!/bin/bash
# Meter Data Download Helper Script
# Run this on your laptop to download data from the Raspberry Pi
# Usage: ./download_meter_data.sh [PI_IP_ADDRESS]

# Configuration
PI_IP="${1:-192.168.1.100}"  # Use first argument or default
PI_USER="pi"
PI_PATH="~/Desktop/offline-setup-12Sep"
LOCAL_DIR="./meter_data_$(date +%Y%m%d_%H%M%S)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Meter Data Download Helper                  ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Check if scp is available
if ! command -v scp &> /dev/null; then
    echo -e "${RED}✗ Error: scp command not found${NC}"
    echo "  Please install OpenSSH client"
    exit 1
fi

echo -e "Target Pi: ${CYAN}$PI_USER@$PI_IP${NC}"
echo -e "Local directory: ${CYAN}$LOCAL_DIR${NC}"
echo ""

# Test connection
echo -e "${YELLOW}Testing connection...${NC}"
if ssh -o ConnectTimeout=5 -o BatchMode=yes $PI_USER@$PI_IP "echo 'Connection OK'" 2>/dev/null; then
    echo -e "${GREEN}✓ Connection successful${NC}"
else
    echo -e "${YELLOW}⚠ Cannot connect without password prompt${NC}"
    echo "  You will be asked for the password"
fi
echo ""

# Create local directory
mkdir -p "$LOCAL_DIR"

# Menu
echo "What would you like to download?"
echo ""
echo "  1) CSV data files only (data/csv/*.csv)"
echo "  2) All data (entire data/ folder)"
echo "  3) Log files (logs/*.log)"
echo "  4) Everything (data + logs)"
echo "  5) Exported files (exports/*.csv) - Use after running 'Export' in Terminal UI"
echo "  6) Custom path"
echo "  7) Connect to Terminal UI directly"
echo ""
read -p "Select option [1-7]: " OPTION

case $OPTION in
    1)
        echo ""
        echo -e "${YELLOW}Downloading CSV files...${NC}"
        scp $PI_USER@$PI_IP:$PI_PATH/data/csv/*.csv "$LOCAL_DIR/" 2>/dev/null
        ;;
    2)
        echo ""
        echo -e "${YELLOW}Downloading all data...${NC}"
        scp -r $PI_USER@$PI_IP:$PI_PATH/data "$LOCAL_DIR/" 2>/dev/null
        ;;
    3)
        echo ""
        echo -e "${YELLOW}Downloading logs...${NC}"
        scp -r $PI_USER@$PI_IP:$PI_PATH/logs "$LOCAL_DIR/" 2>/dev/null
        ;;
    4)
        echo ""
        echo -e "${YELLOW}Downloading everything...${NC}"
        scp -r $PI_USER@$PI_IP:$PI_PATH/data "$LOCAL_DIR/" 2>/dev/null
        scp -r $PI_USER@$PI_IP:$PI_PATH/logs "$LOCAL_DIR/" 2>/dev/null
        ;;
    5)
        echo ""
        echo -e "${YELLOW}Downloading exported files...${NC}"
        scp $PI_USER@$PI_IP:$PI_PATH/exports/*.csv "$LOCAL_DIR/" 2>/dev/null
        ;;
    6)
        echo ""
        read -p "Enter remote path (relative to $PI_PATH): " CUSTOM_PATH
        echo -e "${YELLOW}Downloading $CUSTOM_PATH...${NC}"
        scp -r $PI_USER@$PI_IP:$PI_PATH/$CUSTOM_PATH "$LOCAL_DIR/" 2>/dev/null
        ;;
    7)
        echo ""
        echo -e "${GREEN}Connecting to Terminal UI...${NC}"
        echo "Press Q to quit the UI and return here"
        sleep 1
        ssh -t $PI_USER@$PI_IP "cd $PI_PATH && python3 terminal_meter_ui.py"
        echo ""
        echo -e "${GREEN}Disconnected from Terminal UI${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

# Check result
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Download completed!${NC}"
    echo ""
    echo "Files saved to: $LOCAL_DIR"
    echo ""
    
    # Show what was downloaded
    echo -e "${CYAN}Downloaded files:${NC}"
    if command -v tree &> /dev/null; then
        tree "$LOCAL_DIR" | head -n 20
    else
        ls -lhR "$LOCAL_DIR" | head -n 20
    fi
    
    # Show summary
    TOTAL_SIZE=$(du -sh "$LOCAL_DIR" 2>/dev/null | cut -f1)
    FILE_COUNT=$(find "$LOCAL_DIR" -type f 2>/dev/null | wc -l)
    echo ""
    echo -e "${GREEN}Summary:${NC}"
    echo "  Files: $FILE_COUNT"
    echo "  Total size: $TOTAL_SIZE"
    echo ""
    
    # Offer to open
    if [[ "$OSTYPE" == "darwin"* ]]; then
        read -p "Open folder in Finder? [y/N] " OPEN
        if [[ "$OPEN" =~ ^[Yy]$ ]]; then
            open "$LOCAL_DIR"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]] && command -v xdg-open &> /dev/null; then
        read -p "Open folder in file manager? [y/N] " OPEN
        if [[ "$OPEN" =~ ^[Yy]$ ]]; then
            xdg-open "$LOCAL_DIR"
        fi
    fi
else
    echo ""
    echo -e "${RED}✗ Download failed${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check Pi IP address: $PI_IP"
    echo "  2. Verify SSH access: ssh $PI_USER@$PI_IP"
    echo "  3. Check if files exist on Pi"
    echo "  4. Try option 7 to connect to Terminal UI"
    echo ""
    exit 1
fi

echo ""
echo -e "${CYAN}Tip: Add this to your ~/.bashrc or ~/.zshrc:${NC}"
echo "  alias download-meter='$PWD/$(basename $0) $PI_IP'"
echo ""
