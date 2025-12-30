#!/bin/bash
# Setup Static Ethernet IP for Direct Laptop Connection
# This configures eth0 with a static IP while preserving WiFi functionality
# Safe to run alongside WiFi AP mode (usb_download_mvp) which uses wlan0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/setup_ethernet_$(date +%Y%m%d_%H%M%S).log"

# Create logs directory if needed
mkdir -p "$SCRIPT_DIR/logs"

# Configuration
ETH_INTERFACE="eth0"
STATIC_IP="192.168.137.100"
STATIC_SUBNET="24"
GATEWAY="192.168.137.1"

echo "========================================" | tee -a "$LOG_FILE"
echo "Ethernet Static IP Setup" | tee -a "$LOG_FILE"
echo "$(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script needs sudo privileges. Rerunning with sudo..." | tee -a "$LOG_FILE"
    sudo "$0" "$@"
    exit $?
fi

echo "Configuring $ETH_INTERFACE with static IP: $STATIC_IP/$STATIC_SUBNET" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Backup existing dhcpcd.conf
if [ -f /etc/dhcpcd.conf ]; then
    BACKUP="/etc/dhcpcd.conf.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Backing up /etc/dhcpcd.conf to $BACKUP" | tee -a "$LOG_FILE"
    cp /etc/dhcpcd.conf "$BACKUP"
fi

# Check if eth0 static IP already configured
if grep -q "^interface $ETH_INTERFACE" /etc/dhcpcd.conf 2>/dev/null; then
    echo "⚠ Warning: $ETH_INTERFACE already configured in /etc/dhcpcd.conf" | tee -a "$LOG_FILE"
    echo "Checking configuration..." | tee -a "$LOG_FILE"
    
    if grep -A3 "^interface $ETH_INTERFACE" /etc/dhcpcd.conf | grep -q "$STATIC_IP"; then
        echo "✓ Configuration already correct!" | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
        echo "Current $ETH_INTERFACE configuration:" | tee -a "$LOG_FILE"
        ip addr show $ETH_INTERFACE | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
        echo "No changes needed. Exiting." | tee -a "$LOG_FILE"
        exit 0
    else
        echo "Configuration differs. Removing old configuration..." | tee -a "$LOG_FILE"
        # Remove old eth0 configuration (lines starting with "interface eth0" and next 3 lines)
        sed -i "/^interface $ETH_INTERFACE/,+3d" /etc/dhcpcd.conf
    fi
fi

# Add static IP configuration for eth0
echo "" | tee -a "$LOG_FILE"
echo "Adding static IP configuration to /etc/dhcpcd.conf..." | tee -a "$LOG_FILE"

cat >> /etc/dhcpcd.conf << EOF

# Static IP for Ethernet - Added by setup_static_ethernet.sh on $(date)
# This allows direct laptop connection via Ethernet cable
# Does NOT affect wlan0 (WiFi) or AP mode functionality
interface $ETH_INTERFACE
static ip_address=$STATIC_IP/$STATIC_SUBNET
static routers=$GATEWAY
static domain_name_servers=8.8.8.8 1.1.1.1
EOF

echo "✓ Configuration added successfully" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Show the added configuration
echo "Added configuration:" | tee -a "$LOG_FILE"
echo "-------------------" | tee -a "$LOG_FILE"
tail -7 /etc/dhcpcd.conf | tee -a "$LOG_FILE"
echo "-------------------" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Apply immediately (temporary until reboot)
echo "Applying configuration temporarily (will persist after reboot)..." | tee -a "$LOG_FILE"
ip addr flush dev $ETH_INTERFACE 2>&1 | tee -a "$LOG_FILE" || true
ip addr add $STATIC_IP/$STATIC_SUBNET dev $ETH_INTERFACE 2>&1 | tee -a "$LOG_FILE" || true
ip link set $ETH_INTERFACE up 2>&1 | tee -a "$LOG_FILE" || true

echo "" | tee -a "$LOG_FILE"
echo "Current $ETH_INTERFACE status:" | tee -a "$LOG_FILE"
ip addr show $ETH_INTERFACE | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Check if wlan0 is still working (if configured)
if ip link show wlan0 >/dev/null 2>&1; then
    echo "WiFi (wlan0) status (unchanged):" | tee -a "$LOG_FILE"
    ip addr show wlan0 2>&1 | head -n 5 | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
fi

echo "========================================" | tee -a "$LOG_FILE"
echo "✓ Setup Complete!" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Ethernet Interface: $ETH_INTERFACE" | tee -a "$LOG_FILE"
echo "Static IP: $STATIC_IP/$STATIC_SUBNET" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "From your Windows laptop:" | tee -a "$LOG_FILE"
echo "  1. Set Windows Ethernet adapter to: 192.168.137.1/24" | tee -a "$LOG_FILE"
echo "  2. Connect Ethernet cable" | tee -a "$LOG_FILE"
echo "  3. SSH: ssh pi@$STATIC_IP" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Note: WiFi (wlan0) and AP mode are NOT affected." | tee -a "$LOG_FILE"
echo "      Both Ethernet and WiFi can work simultaneously." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "A reboot is recommended to ensure configuration persists." | tee -a "$LOG_FILE"
echo "Run: sudo reboot" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Log saved to: $LOG_FILE" | tee -a "$LOG_FILE"
