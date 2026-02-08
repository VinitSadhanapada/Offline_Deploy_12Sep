#!/bin/bash
# ============================================================================
# Master Setup Script for Raspberry Pi Meter Dashboard
# ============================================================================
# This is the SINGLE entry point for complete system setup.
# All sub-scripts in scripts/setup/ are called automatically.
#
# Usage:
#   sudo bash master_setup.sh            # Full setup (all steps, no prompts)
#   sudo bash master_setup.sh --help     # Show options
#
# Skip flags (opt-out of specific steps):
#   --skip-ethernet     Skip static Ethernet IP configuration
#   --skip-services     Skip systemd service installation (dashboard, USB, cloud)
#   --skip-usb-server   Skip USB download server / WiFi AP installation
#   --skip-reboot       Skip the automatic reboot at the end
# ============================================================================

set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Always resolve to project root regardless of where the script lives
if [[ -d "$SCRIPT_DIR/scripts/setup" ]]; then
    PROJECT_ROOT="$SCRIPT_DIR"
elif [[ -d "$SCRIPT_DIR/../../scripts/setup" ]]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
else
    echo "ERROR: Cannot determine project root. Run from the project directory."
    exit 1
fi
SETUP_DIR="$PROJECT_ROOT/scripts/setup"
PACKAGES_DIR="$PROJECT_ROOT/packages_folder"
VENV_DIR="$PROJECT_ROOT/venv"
CONFIG_DIR="$PROJECT_ROOT/config"
cd "$PROJECT_ROOT"

# ── Colors ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Logging ────────────────────────────────────────────────────────────────
mkdir -p "$PROJECT_ROOT/logs"
LOG_FILE="$PROJECT_ROOT/logs/master_setup_$(date +%Y%m%d_%H%M%S).log"

log_info()    { echo -e "${CYAN}[INFO]${NC} $1" | tee -a "$LOG_FILE"; }
log_success() { echo -e "${GREEN}[OK]${NC}   $1" | tee -a "$LOG_FILE"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"; }
log_error()   { echo -e "${RED}[FAIL]${NC} $1" | tee -a "$LOG_FILE"; }

step_header() {
    local num="$1" title="$2"
    echo "" | tee -a "$LOG_FILE"
    echo -e "${BOLD}── Step ${num}/${STEPS_TOTAL}: ${title} ──${NC}" | tee -a "$LOG_FILE"
}

# ── Parse flags ────────────────────────────────────────────────────────────
SKIP_ETHERNET=0
SKIP_SERVICES=0
SKIP_USB_SERVER=0
SKIP_REBOOT=0

for arg in "$@"; do
    case "$arg" in
        --skip-ethernet)   SKIP_ETHERNET=1 ;;
        --skip-services)   SKIP_SERVICES=1 ;;
        --skip-usb-server) SKIP_USB_SERVER=1 ;;
        --skip-reboot)     SKIP_REBOOT=1 ;;
        --help|-h)
            echo "Usage: sudo bash master_setup.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-ethernet     Skip static Ethernet IP setup"
            echo "  --skip-services     Skip all systemd service installation"
            echo "  --skip-usb-server   Skip USB download server / WiFi AP"
            echo "  --skip-reboot       Skip automatic reboot at the end"
            echo "  --help, -h          Show this help"
            exit 0
            ;;
    esac
done

# ── Pre-flight ─────────────────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    log_error "This script must be run with sudo"
    echo "Usage: sudo bash master_setup.sh"
    exit 1
fi

TARGET_USER="${SUDO_USER:-pi}"

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Raspberry Pi Meter Dashboard — Master Setup              ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
log_info "User: $TARGET_USER"
log_info "Project: $PROJECT_ROOT"
log_info "Log: $LOG_FILE"

STEPS_COMPLETED=0
STEPS_TOTAL=8

# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: Make all scripts executable
# ═══════════════════════════════════════════════════════════════════════════
step_header 1 "Making scripts executable"

# Find and chmod all .sh files anywhere in the project
find "$PROJECT_ROOT" -name "*.sh" -type f -exec chmod +x {} + 2>/dev/null || true
# Python entry points
chmod +x "$PROJECT_ROOT/src/dashboard/terminal_meter_ui.py" 2>/dev/null || true
chmod +x "$PROJECT_ROOT/src/dashboard/simple_meter_ui.py" 2>/dev/null || true
chmod +x "$PROJECT_ROOT/src/dashboard/simple_rpi_dashboard.py" 2>/dev/null || true

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
log_success "All .sh and Python entry-point scripts are executable"

# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: Create directories and set ownership
# ═══════════════════════════════════════════════════════════════════════════
step_header 2 "Creating directories and setting permissions"

mkdir -p "$PROJECT_ROOT/data/csv"
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/exports"

# Remove empty legacy venv313 directory if it exists and is unused
if [[ -d "$PROJECT_ROOT/venv313" ]] && [[ ! -x "$PROJECT_ROOT/venv313/bin/python" ]]; then
    rmdir "$PROJECT_ROOT/venv313" 2>/dev/null || true
fi

chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/data"    2>/dev/null || true
chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/logs"    2>/dev/null || true
chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/exports" 2>/dev/null || true
chmod 755 "$PROJECT_ROOT/data" "$PROJECT_ROOT/logs" "$PROJECT_ROOT/exports"

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
log_success "Directories ready"

# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: Python virtual environment + offline packages
# ═══════════════════════════════════════════════════════════════════════════
step_header 3 "Setting up Python virtual environment and packages"

if [[ -f "$SETUP_DIR/one_click_system_py313.sh" ]]; then
    # Run as target user (venv should be owned by them, not root)
    sudo -u "$TARGET_USER" bash "$SETUP_DIR/one_click_system_py313.sh" 2>&1 | tee -a "$LOG_FILE" || {
        log_warning "one_click_system_py313.sh had issues — attempting direct install"
    }
fi

# Verify venv exists; create if one_click failed or was missing
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log_info "Creating venv manually..."
    sudo -u "$TARGET_USER" python3 -m venv "$VENV_DIR"
fi

# Ensure ALL required wheels are installed (idempotent / safe to re-run)
if [[ -d "$PACKAGES_DIR" ]]; then
    log_info "Installing offline packages into venv..."
    sudo -u "$TARGET_USER" "$VENV_DIR/bin/python" -m pip install --no-index \
        --find-links="$PACKAGES_DIR" \
        numpy pandas pymodbus pyserial paho-mqtt termcolor \
        python-dateutil tzdata six pytz smbus2 jinja2 markupsafe werkzeug \
        2>&1 | tee -a "$LOG_FILE" || log_warning "Some packages may have failed"
fi

# Smoke test
log_info "Smoke test..."
sudo -u "$TARGET_USER" "$VENV_DIR/bin/python" -c \
    "import numpy, pandas, pymodbus, serial, paho.mqtt, termcolor; print('All core packages OK')" 2>&1 | tee -a "$LOG_FILE" || {
    log_warning "Smoke test had import failures — check wheels in packages_folder/"
}

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
log_success "Python environment ready  ($VENV_DIR)"

# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: Static Ethernet IP for laptop SSH access
# ═══════════════════════════════════════════════════════════════════════════
step_header 4 "Configuring static Ethernet IP (192.168.137.100)"

if [[ "$SKIP_ETHERNET" -eq 1 ]]; then
    log_info "Skipped (--skip-ethernet)"
else
    if [[ -f "$SETUP_DIR/setup_static_ethernet.sh" ]]; then
        bash "$SETUP_DIR/setup_static_ethernet.sh" 2>&1 | tee -a "$LOG_FILE" || {
            log_warning "Static Ethernet setup had issues"
        }
        log_success "Static Ethernet configured"
    else
        log_warning "setup_static_ethernet.sh not found — skipping"
    fi
fi

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))

# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: Systemd services (dashboard, USB copy, cloud sync)
# ═══════════════════════════════════════════════════════════════════════════
step_header 5 "Installing systemd services (dashboard + helpers)"

if [[ "$SKIP_SERVICES" -eq 1 ]]; then
    log_info "Skipped (--skip-services)"
else
    if [[ -f "$SETUP_DIR/enable_auto_start.sh" ]]; then
        bash "$SETUP_DIR/enable_auto_start.sh" 2>&1 | tee -a "$LOG_FILE" || {
            log_warning "enable_auto_start.sh had issues"
        }
        log_success "Systemd services installed and enabled"
    else
        log_warning "enable_auto_start.sh not found — skipping"
    fi
fi

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))

# ═══════════════════════════════════════════════════════════════════════════
# STEP 6: USB download server + WiFi AP
# ═══════════════════════════════════════════════════════════════════════════
step_header 6 "Installing USB download server and WiFi AP"

if [[ "$SKIP_USB_SERVER" -eq 1 ]]; then
    log_info "Skipped (--skip-usb-server)"
else
    if [[ -f "$PROJECT_ROOT/usb_download_mvp/scripts/install_service.sh" ]]; then
        bash "$PROJECT_ROOT/usb_download_mvp/scripts/install_service.sh" 2>&1 | tee -a "$LOG_FILE" || {
            log_warning "USB download server install had issues"
        }
        log_success "USB download server installed"
    else
        log_warning "usb_download_mvp/scripts/install_service.sh not found — skipping"
    fi
fi

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))

# ═══════════════════════════════════════════════════════════════════════════
# STEP 7: Default configuration files
# ═══════════════════════════════════════════════════════════════════════════
step_header 7 "Ensuring configuration files exist"

# Use the in-project config/ directory as the source of truth
if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
    log_info "Creating default config/config.json..."
    mkdir -p "$CONFIG_DIR"
    cat > "$CONFIG_DIR/config.json" <<'CONF'
{
  "SIMULATION_MODE": false,
  "READING_INTERVAL": 10,
  "CSV_LOG_INTERVAL": 60,
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
CONF
    log_success "Created config/config.json"
else
    log_info "config/config.json already exists"
fi

if [[ ! -f "$CONFIG_DIR/device_config.json" ]]; then
    log_info "Creating default config/device_config.json..."
    echo "[]" > "$CONFIG_DIR/device_config.json"
    log_success "Created config/device_config.json"
else
    log_info "config/device_config.json already exists"
fi

chown -R "$TARGET_USER:$TARGET_USER" "$CONFIG_DIR" 2>/dev/null || true

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
log_success "Configuration files ready"

# ═══════════════════════════════════════════════════════════════════════════
# STEP 8: User groups and system permissions
# ═══════════════════════════════════════════════════════════════════════════
step_header 8 "Setting up user groups and permissions"

# dialout — required for RS-485 / serial port access
if ! groups "$TARGET_USER" | grep -q dialout; then
    usermod -a -G dialout "$TARGET_USER"
    log_success "Added $TARGET_USER to dialout group (serial ports)"
else
    log_info "$TARGET_USER already in dialout group"
fi

# i2c — required for DS3231 RTC
if ! groups "$TARGET_USER" | grep -q i2c; then
    usermod -a -G i2c "$TARGET_USER" 2>/dev/null || log_warning "i2c group not available"
else
    log_info "$TARGET_USER already in i2c group"
fi

# gpio — useful for future hardware
if ! groups "$TARGET_USER" | grep -q gpio 2>/dev/null; then
    usermod -a -G gpio "$TARGET_USER" 2>/dev/null || true
fi

STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
log_success "User permissions configured"

# ═══════════════════════════════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Setup Complete — $STEPS_COMPLETED/$STEPS_TOTAL steps finished                        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BOLD}Quick reference:${NC}"
echo ""
echo -e "  ${CYAN}Terminal UI:${NC}  ./terminal_ui.sh"
echo -e "  ${CYAN}SSH access :${NC}  ssh $TARGET_USER@192.168.137.100"
echo -e "  ${CYAN}Config     :${NC}  $CONFIG_DIR/config.json"
echo -e "  ${CYAN}Devices    :${NC}  $CONFIG_DIR/device_config.json"
echo -e "  ${CYAN}Logs       :${NC}  $PROJECT_ROOT/logs/"
echo -e "  ${CYAN}Setup log  :${NC}  $LOG_FILE"
echo ""

if [[ "$SKIP_REBOOT" -eq 1 ]]; then
    log_info "Reboot skipped (--skip-reboot). Reboot manually to activate group memberships and services."
else
    log_info "Rebooting in 5 seconds to activate services and group memberships..."
    log_info "Press Ctrl+C to cancel."
    sleep 5
    sync
    reboot
fi

exit 0
