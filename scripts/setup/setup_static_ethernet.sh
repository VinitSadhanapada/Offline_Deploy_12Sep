#!/bin/bash
# Setup Static Ethernet IP for Direct Laptop Connection
# This configures eth0 with a static IP while preserving WiFi connectivity
# IMPORTANT: Does NOT set a default gateway on eth0 to preserve WiFi internet
# Safe to run alongside WiFi AP mode (usb_download_mvp) which uses wlan0
# Supports both dhcpcd and NetworkManager

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/setup_ethernet_$(date +%Y%m%d_%H%M%S).log"

# Configuration
ETH_INTERFACE="eth0"
STATIC_IP="192.168.137.100"
STATIC_SUBNET="24"
# NOTE: No gateway - this is intentional! We don't want eth0 to become the default route
# The laptop will set itself as 192.168.137.1 for direct connection only

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
echo "NOTE: No gateway will be set - WiFi remains the internet route" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Detect which network manager is in use
USING_DHCPCD=false
USING_NETWORKMANAGER=false

if systemctl is-active --quiet NetworkManager; then
    USING_NETWORKMANAGER=true
    echo "✓ Detected: NetworkManager is running" | tee -a "$LOG_FILE"
elif systemctl is-active --quiet dhcpcd; then
    USING_DHCPCD=true
    echo "✓ Detected: dhcpcd is running" | tee -a "$LOG_FILE"
elif [ -f /etc/dhcpcd.conf ]; then
    USING_DHCPCD=true
    echo "✓ Detected: dhcpcd config exists (service may be inactive)" | tee -a "$LOG_FILE"
else
    echo "⚠ Warning: Could not detect network manager" | tee -a "$LOG_FILE"
    echo "Will attempt NetworkManager configuration..." | tee -a "$LOG_FILE"
    USING_NETWORKMANAGER=true
fi

echo "" | tee -a "$LOG_FILE"

#############################################################################
# NetworkManager Configuration
#############################################################################
if [ "$USING_NETWORKMANAGER" = true ]; then
    echo "Configuring via NetworkManager..." | tee -a "$LOG_FILE"
    
    # Find or create a connection for eth0
    CON_NAME="Ethernet-Static"
    
    # Check if our Ethernet-Static connection already exists
    if nmcli -t -f NAME con show | grep -q "^${CON_NAME}$"; then
        echo "Using existing connection: $CON_NAME" | tee -a "$LOG_FILE"
    else
        # Check if eth0 has any connection
        EXISTING_CON=$(nmcli -t -f NAME,DEVICE con show | grep ":$ETH_INTERFACE$" | cut -d: -f1 | head -1)
        if [ -n "$EXISTING_CON" ]; then
            echo "Using existing connection: $EXISTING_CON" | tee -a "$LOG_FILE"
            CON_NAME="$EXISTING_CON"
        else
            echo "Creating new connection: $CON_NAME" | tee -a "$LOG_FILE"
            nmcli con add type ethernet con-name "$CON_NAME" ifname "$ETH_INTERFACE" 2>&1 | tee -a "$LOG_FILE"
        fi
    fi
    
    # Configure static IP WITHOUT gateway (critical for preserving WiFi internet)
    echo "Setting static IP configuration (no gateway)..." | tee -a "$LOG_FILE"
    nmcli con mod "$CON_NAME" ipv4.addresses "$STATIC_IP/$STATIC_SUBNET" 2>&1 | tee -a "$LOG_FILE"
    nmcli con mod "$CON_NAME" ipv4.method manual 2>&1 | tee -a "$LOG_FILE"
    
    # CRITICAL: Prevent eth0 from becoming the default route
    nmcli con mod "$CON_NAME" ipv4.never-default yes 2>&1 | tee -a "$LOG_FILE"
    echo "✓ Set ipv4.never-default=yes (WiFi remains internet gateway)" | tee -a "$LOG_FILE"
    
    # Remove any gateway setting (we don't need one for direct laptop connection)
    nmcli con mod "$CON_NAME" ipv4.gateway "" 2>&1 | tee -a "$LOG_FILE" || true
    
    # Don't need DNS on eth0 either - WiFi provides it
    nmcli con mod "$CON_NAME" ipv4.dns "" 2>&1 | tee -a "$LOG_FILE" || true
    
    # Autoconnect when cable is plugged in
    nmcli con mod "$CON_NAME" connection.autoconnect yes 2>&1 | tee -a "$LOG_FILE"
    
    # Bring up the connection (may fail if cable not connected - that's OK)
    echo "Activating connection..." | tee -a "$LOG_FILE"
    nmcli con up "$CON_NAME" 2>&1 | tee -a "$LOG_FILE" || echo "⚠ Connection activation deferred (will activate when cable connected)" | tee -a "$LOG_FILE"
    
    echo "✓ NetworkManager configuration complete" | tee -a "$LOG_FILE"
fi

#############################################################################
# dhcpcd Configuration  
#############################################################################
if [ "$USING_DHCPCD" = true ]; then
    echo "Configuring via dhcpcd..." | tee -a "$LOG_FILE"
    
    # Backup existing dhcpcd.conf
    if [ -f /etc/dhcpcd.conf ]; then
        BACKUP="/etc/dhcpcd.conf.backup.$(date +%Y%m%d_%H%M%S)"
        echo "Backing up /etc/dhcpcd.conf to $BACKUP" | tee -a "$LOG_FILE"
        cp /etc/dhcpcd.conf "$BACKUP"
    fi

    # Remove any existing eth0 config
    if grep -q "^interface $ETH_INTERFACE" /etc/dhcpcd.conf 2>/dev/null; then
        echo "Removing old $ETH_INTERFACE configuration..." | tee -a "$LOG_FILE"
        # Remove the interface block (from "interface eth0" to next blank line or interface)
        sed -i "/^# Static IP for Ethernet/,/^$/d" /etc/dhcpcd.conf
        sed -i "/^interface $ETH_INTERFACE/,/^$/d" /etc/dhcpcd.conf
    fi
    
    # Add static IP configuration WITHOUT router/gateway
    echo "Adding static IP configuration to /etc/dhcpcd.conf..." | tee -a "$LOG_FILE"
    
    cat >> /etc/dhcpcd.conf << EOF

# Static IP for Ethernet - Added by setup_static_ethernet.sh on $(date)
# This allows direct laptop connection via Ethernet cable
# NOTE: No 'static routers' line - WiFi remains the default gateway for internet
interface $ETH_INTERFACE
static ip_address=$STATIC_IP/$STATIC_SUBNET
# No gateway/router - preserves WiFi as internet route
nogateway
EOF
    
    echo "✓ Configuration added successfully" | tee -a "$LOG_FILE"
    
    # Restart dhcpcd to apply changes
    if systemctl is-active --quiet dhcpcd; then
        echo "Restarting dhcpcd service..." | tee -a "$LOG_FILE"
        systemctl restart dhcpcd 2>&1 | tee -a "$LOG_FILE"
        sleep 2
    fi
    
    echo "✓ dhcpcd configuration complete" | tee -a "$LOG_FILE"
fi

#############################################################################
# Verification
#############################################################################
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "Current $ETH_INTERFACE status:" | tee -a "$LOG_FILE"
ip addr show $ETH_INTERFACE 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "WiFi (wlan0) status (should be unchanged):" | tee -a "$LOG_FILE"
ip addr show wlan0 2>&1 | tee -a "$LOG_FILE" || echo "wlan0 not available" | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "Default routes (WiFi should remain default):" | tee -a "$LOG_FILE"
ip route show default 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "✓ Setup Complete!" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Ethernet Interface: $ETH_INTERFACE" | tee -a "$LOG_FILE"
echo "Static IP: $STATIC_IP/$STATIC_SUBNET" | tee -a "$LOG_FILE"
echo "Gateway: NONE (WiFi remains internet route)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "From your Windows laptop:" | tee -a "$LOG_FILE"
echo "  1. Set Windows Ethernet adapter to: 192.168.137.1/24" | tee -a "$LOG_FILE"
echo "  2. Connect Ethernet cable" | tee -a "$LOG_FILE"
echo "  3. SSH: ssh pi@$STATIC_IP" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "✓ WiFi internet connectivity is PRESERVED" | tee -a "$LOG_FILE"
echo "  - eth0 is for direct laptop connection only" | tee -a "$LOG_FILE"
echo "  - wlan0 remains the default gateway for internet" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Log saved to: $LOG_FILE" | tee -a "$LOG_FILE"

exit 0
