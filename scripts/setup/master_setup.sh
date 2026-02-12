#!/bin/bash
# Master Setup Script for Raspberry Pi Meter Dashboard
# This script runs ALL necessary setup steps in the correct order
# Usage: sudo bash master_setup.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Detect if running from project root or from scripts/setup/
if [[ -d "$SCRIPT_DIR/scripts/setup" ]]; then
    # Running from project root
    PROJECT_ROOT="$SCRIPT_DIR"
    SETUP_DIR="$PROJECT_ROOT/scripts/setup"
else
    # Running from scripts/setup/
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    SETUP_DIR="$SCRIPT_DIR"
fi
cd "$PROJECT_ROOT"

# Create logs directory
mkdir -p "$PROJECT_ROOT/logs"
LOG_FILE="$PROJECT_ROOT/logs/master_setup_$(date +%Y%m%d_%H%M%S).log"

# Logging functions
log_info() {
    echo -e "${CYAN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1" | tee -a "$LOG_FILE"
}

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    log_error "This script must be run with sudo"
    echo "Usage: sudo bash master_setup.sh"
    exit 1
fi

TARGET_USER="${SUDO_USER:-pi}"
log_info "Running setup for user: $TARGET_USER"
log_info "Log file: $LOG_FILE"

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Raspberry Pi Meter Dashboard - Master Setup              ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Track setup steps
STEPS_COMPLETED=0
STEPS_TOTAL=8

#############################################################################
# STEP 1: Make all scripts executable
#############################################################################
log_info "Step 1/$STEPS_TOTAL: Making scripts executable..."
echo ""

declare -a SCRIPTS=(
    "scripts/setup/enable_auto_start.sh"
    "scripts/setup/setup_static_ethernet.sh"
    "scripts/launchers/terminal_ui.sh"
    "scripts/system/update_pull.sh"
    "scripts/setup/one_click_system_py313.sh"
    "scripts/system/download_meter_data.sh"
    "usb_download_mvp/scripts/install_service.sh"
    "usb_download_mvp/scripts/enable_ap_mode.sh"
    "usb_download_mvp/scripts/enable_ap_mode_wrapper.sh"
    "usb_download_mvp/scripts/disable_ap_mode.sh"
    "usb_download_mvp/scripts/disable_ap_mode_wrapper.sh"
    "usb_download_mvp/scripts/install_gadget_mode.sh"
    "usb_download_mvp/scripts/enforce_ap_mode.sh"
    "usb_download_mvp/scripts/usb_gadget.sh"
    "usb_download_mvp/scripts/watchdog_status.sh"
    "usb_download_mvp/scripts/ssid_hint.sh"
    "scripts/system/rtc_check.sh"
)

for script in "${SCRIPTS[@]}"; do
    if [ -f "$PROJECT_ROOT/$script" ]; then
        chmod +x "$PROJECT_ROOT/$script"
        log_success "Made executable: $script"
    else
        log_warning "Script not found: $script"
    fi
done

# Make Python files executable (now in src/dashboard/)
chmod +x "$PROJECT_ROOT/src/dashboard/terminal_meter_ui.py" 2>/dev/null || true
chmod +x "$PROJECT_ROOT/src/dashboard/simple_meter_ui.py" 2>/dev/null || true
chmod +x "$PROJECT_ROOT/src/dashboard/simple_rpi_dashboard.py" 2>/dev/null || true

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
log_success "Step 1 complete: Scripts are executable"
echo ""

#############################################################################
# STEP 2: Create necessary directories and set permissions
#############################################################################
log_info "Step 2/$STEPS_TOTAL: Creating directories and setting permissions..."
echo ""

mkdir -p "$PROJECT_ROOT/data/csv"
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/exports"
mkdir -p "$PROJECT_ROOT/venv313"

# Set ownership
chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/data" 2>/dev/null || true
chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/logs" 2>/dev/null || true
chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/exports" 2>/dev/null || true

# Set permissions
chmod 755 "$PROJECT_ROOT/exports"
chmod 755 "$PROJECT_ROOT/data"
chmod 755 "$PROJECT_ROOT/logs"

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
log_success "Step 2 complete: Directories created"
echo ""

#############################################################################
# STEP 2b: Install I2C tools for DS3231 RTC support
#############################################################################
log_info "Step 2b: Installing I2C tools for RTC support..."
echo ""

# Enable I2C interface if not already enabled
if [ -e /boot/config.txt ]; then
    if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
        echo "dtparam=i2c_arm=on" >> /boot/config.txt
        log_success "Enabled I2C in /boot/config.txt (reboot required)"
    else
        log_info "I2C already enabled in /boot/config.txt"
    fi
elif [ -e /boot/firmware/config.txt ]; then
    if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null; then
        echo "dtparam=i2c_arm=on" >> /boot/firmware/config.txt
        log_success "Enabled I2C in /boot/firmware/config.txt (reboot required)"
    else
        log_info "I2C already enabled in /boot/firmware/config.txt"
    fi
fi

# Load i2c kernel modules now (if available)
modprobe i2c-dev 2>/dev/null || true
modprobe i2c-bcm2835 2>/dev/null || true

# Ensure i2c-dev loads on boot
if [ -f /etc/modules ]; then
    grep -q "^i2c-dev" /etc/modules 2>/dev/null || echo "i2c-dev" >> /etc/modules
fi

# Install i2c-tools and python3-smbus via apt
for pkg in i2c-tools python3-smbus; do
    if dpkg -s "$pkg" &>/dev/null; then
        log_info "$pkg already installed"
    else
        log_info "Installing $pkg..."
        if apt-get install -y "$pkg" >> "$LOG_FILE" 2>&1; then
            log_success "Installed $pkg"
        else
            log_warning "Could not install $pkg (may need internet or apt cache)"
        fi
    fi
done

# Quick I2C sanity check
if [ -e /dev/i2c-1 ]; then
    log_success "I2C bus /dev/i2c-1 is available"
    if command -v i2cdetect &>/dev/null; then
        if i2cdetect -y 1 2>/dev/null | grep -q "68"; then
            log_success "DS3231 RTC detected at address 0x68"
        else
            log_warning "DS3231 RTC not detected at 0x68 (check wiring or reboot if I2C was just enabled)"
        fi
    fi
else
    log_warning "I2C bus not available yet (will be available after reboot)"
fi

log_success "Step 2b complete: I2C/RTC tools ready"
echo ""

#############################################################################
# STEP 3: Setup Python environment (venv and packages)
#############################################################################
log_info "Step 3/$STEPS_TOTAL: Setting up Python environment..."
echo ""

if [ -f "$SETUP_DIR/one_click_system_py313.sh" ]; then
    log_info "Running one_click_system_py313.sh..."
    sudo -u "$TARGET_USER" bash "$SETUP_DIR/one_click_system_py313.sh" 2>&1 | tee -a "$LOG_FILE" || {
        log_warning "Python 3.13 setup had issues, continuing..."
    }
    STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
    log_success "Step 3 complete: Python environment ready"
else
    log_warning "one_click_system_py313.sh not found, skipping Python setup"
    STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
fi
echo ""

#############################################################################
# STEP 4: Setup static Ethernet IP for SSH access
#############################################################################
log_info "Step 4/$STEPS_TOTAL: Configuring static Ethernet IP..."
echo ""

read -p "Do you want to setup static Ethernet IP for laptop SSH access? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "$SETUP_DIR/setup_static_ethernet.sh" ]; then
        bash "$SETUP_DIR/setup_static_ethernet.sh" 2>&1 | tee -a "$LOG_FILE"
        log_success "Step 4 complete: Static Ethernet IP configured"
    else
        log_error "setup_static_ethernet.sh not found"
    fi
else
    log_info "Skipping static Ethernet setup"
fi

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
echo ""

#############################################################################
# STEP 5: Install meter dashboard service (auto-start)
#############################################################################
log_info "Step 5/$STEPS_TOTAL: Installing meter dashboard service..."
echo ""

read -p "Do you want to enable dashboard auto-start on boot? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "$SETUP_DIR/enable_auto_start.sh" ]; then
        bash "$SETUP_DIR/enable_auto_start.sh" 2>&1 | tee -a "$LOG_FILE"
        log_success "Step 5 complete: Dashboard service enabled"
    else
        log_error "enable_auto_start.sh not found"
    fi
else
    log_info "Skipping dashboard auto-start setup"
fi

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
echo ""

#############################################################################
# STEP 6: Install USB download server and WiFi AP mode
#############################################################################
log_info "Step 6/$STEPS_TOTAL: Installing USB download server and WiFi AP..."
echo ""

read -p "Do you want to install USB download server and WiFi AP mode? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "$PROJECT_ROOT/usb_download_mvp/scripts/install_service.sh" ]; then
        bash "$PROJECT_ROOT/usb_download_mvp/scripts/install_service.sh" 2>&1 | tee -a "$LOG_FILE"
        log_success "Step 6 complete: USB download server installed"
    else
        log_error "USB download install script not found"
    fi
else
    log_info "Skipping USB download server setup"
fi

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
echo ""

#############################################################################
# STEP 7: Configure device settings
#############################################################################
log_info "Step 7/$STEPS_TOTAL: Configuring device settings..."
echo ""

# Ensure config directory exists
CONFIG_DIR="/home/$TARGET_USER/meter_config"
mkdir -p "$CONFIG_DIR"
chown "$TARGET_USER:$TARGET_USER" "$CONFIG_DIR"

# Create default config files if they don't exist
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    log_info "Creating default config.json..."
    cat > "$CONFIG_DIR/config.json" <<'EOF'
{
  "SIMULATION_MODE": false,
  "READING_INTERVAL": 10,
  "INTER_DEVICE_DELAY": 0.1,
  "PORT": "/dev/ttyUSB0",
  "ENABLE_MQTT": false,
  "ENABLE_RTC": true,
  "LOG_LEVEL": "INFO",
  "usb_copy": {
    "enabled": true,
    "eject_after_copy": true
  }
}
EOF
    chown "$TARGET_USER:$TARGET_USER" "$CONFIG_DIR/config.json"
    log_success "Created default config.json"
fi

if [ ! -f "$CONFIG_DIR/device_config.json" ]; then
    log_info "Creating default device_config.json..."
    echo "[]" > "$CONFIG_DIR/device_config.json"
    chown "$TARGET_USER:$TARGET_USER" "$CONFIG_DIR/device_config.json"
    log_success "Created default device_config.json"
fi

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
log_success "Step 7 complete: Configuration files ready"
echo ""

#############################################################################
# STEP 8: System permissions and user groups
#############################################################################
log_info "Step 8/$STEPS_TOTAL: Setting up system permissions..."
echo ""

# Add user to dialout group for serial port access
if ! groups "$TARGET_USER" | grep -q dialout; then
    usermod -a -G dialout "$TARGET_USER"
    log_success "Added $TARGET_USER to dialout group (for serial ports)"
else
    log_info "User already in dialout group"
fi

# Add user to i2c group for RTC access
if ! groups "$TARGET_USER" | grep -q i2c; then
    usermod -a -G i2c "$TARGET_USER" 2>/dev/null || log_warning "i2c group not available"
else
    log_info "User already in i2c group"
fi

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
log_success "Step 8 complete: User permissions configured"
echo ""

#############################################################################
# FINAL SUMMARY
#############################################################################
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Setup Complete!                                           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_success "All $STEPS_COMPLETED/$STEPS_TOTAL steps completed successfully!"
echo ""

echo "Next Steps:"
echo ""
echo "1. ${CYAN}Configure your meters:${NC}"
echo "   - Edit: /home/$TARGET_USER/meter_config/device_config.json"
echo "   - Or use Desktop UI: SimpleMeterUI_Admin.desktop"
echo ""
echo "2. ${CYAN}SSH Terminal Access:${NC}"
echo "   - From laptop: ssh $TARGET_USER@<PI_IP>"
echo "   - Run Terminal UI: ./terminal_ui.sh"
echo "   - See: QUICKSTART_SSH_UI.md"
echo ""
echo "3. ${CYAN}Desktop Access:${NC}"
echo "   - Double-click: SimpleMeterUI_Admin.desktop"
echo "   - Or run: python3 src/dashboard/simple_meter_ui.py"
echo ""
echo "4. ${CYAN}Reboot recommended:${NC}"
echo "   - sudo reboot"
echo "   - This activates all services and group memberships"
echo ""

read -p "Do you want to reboot now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Rebooting system..."
    sync
    reboot
else
    log_info "Setup complete. Please reboot when convenient."
fi

exit 0
