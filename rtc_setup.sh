#!/bin/bash
# ============================================================
# rtc_setup.sh — One-time DS3231 RTC setup for Raspberry Pi
# ============================================================
#
# Run ONCE on each RPI after connecting the DS3231 module.
#
# Wiring:
#   DS3231 VCC  →  RPi Pin 1  (3.3V)
#   DS3231 GND  →  RPi Pin 6  (GND)
#   DS3231 SDA  →  RPi Pin 3  (GPIO2/SDA)
#   DS3231 SCL  →  RPi Pin 5  (GPIO3/SCL)
#
# Usage:
#   sudo bash rtc_setup.sh
#
# ============================================================

set -e

# Must run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Run with sudo:  sudo bash rtc_setup.sh"
    exit 1
fi

echo "============================================"
echo "  DS3231 RTC Setup for Raspberry Pi"
echo "============================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }

# ── Detect config.txt location ──────────────────────────────
# Bookworm uses /boot/firmware/config.txt, older uses /boot/config.txt
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_TXT="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    CONFIG_TXT="/boot/config.txt"
else
    fail "Cannot find config.txt"
fi
echo "Using config: $CONFIG_TXT"
echo ""

# ── Step 1: Enable I2C ──────────────────────────────────────
echo "Step 1: Enabling I2C..."
if raspi-config nonint do_i2c 0 2>/dev/null; then
    ok "I2C enabled via raspi-config"
else
    # Manual fallback
    if ! grep -q "^dtparam=i2c_arm=on" "$CONFIG_TXT" 2>/dev/null; then
        echo "dtparam=i2c_arm=on" >> "$CONFIG_TXT"
    fi
    ok "I2C enabled manually in config.txt"
fi

# Load I2C module now (so we can test without reboot)
modprobe i2c-dev 2>/dev/null || true
modprobe i2c-bcm2835 2>/dev/null || true

# ── Step 2: Install I2C tools ───────────────────────────────
echo "Step 2: Installing I2C tools..."
apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq i2c-tools python3-smbus >/dev/null 2>&1
ok "i2c-tools and python3-smbus installed"

# Try to install smbus2 via pip (optional, for better API)
pip3 install smbus2 2>/dev/null || true

# ── Step 3: Add DS3231 overlay ──────────────────────────────
echo "Step 3: Adding DS3231 device tree overlay..."
if grep -q "dtoverlay=i2c-rtc,ds3231" "$CONFIG_TXT" 2>/dev/null; then
    ok "DS3231 overlay already present"
else
    echo "dtoverlay=i2c-rtc,ds3231" >> "$CONFIG_TXT"
    ok "DS3231 overlay added to config.txt"
fi

# ── Step 4: Remove fake-hwclock ─────────────────────────────
echo "Step 4: Removing fake-hwclock..."
if dpkg -l fake-hwclock >/dev/null 2>&1; then
    apt-get remove -y -qq fake-hwclock >/dev/null 2>&1
    ok "fake-hwclock removed"
else
    ok "fake-hwclock not installed (good)"
fi

# Disable fake-hwclock service if it exists
systemctl disable fake-hwclock.service 2>/dev/null || true
systemctl stop fake-hwclock.service 2>/dev/null || true

# ── Step 5: Verify DS3231 detection ─────────────────────────
echo "Step 5: Checking for DS3231 on I2C bus..."

# Load the RTC driver manually for immediate testing
dtoverlay i2c-rtc ds3231 2>/dev/null || true

I2C_RESULT=$(i2cdetect -y 1 2>/dev/null | grep -o "68\|UU" | head -1)
if [ "$I2C_RESULT" = "68" ] || [ "$I2C_RESULT" = "UU" ]; then
    ok "DS3231 detected at 0x68 ($I2C_RESULT)"
else
    warn "DS3231 NOT detected — check wiring! Will work after reboot if overlay is set."
fi

# ── Step 6: Set RTC from current system time ────────────────
echo "Step 6: Setting RTC from system time..."
echo "  Current system time: $(date '+%Y-%m-%d %H:%M:%S')"

# Try hwclock first (works if kernel driver loaded)
if hwclock -w 2>/dev/null; then
    ok "RTC set via hwclock"
else
    # Try Python module
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    if python3 "$SCRIPT_DIR/set_rtc.py" 2>/dev/null; then
        ok "RTC set via Python I2C"
    else
        warn "Could not set RTC now — will work after reboot"
    fi
fi

# ── Step 7: Create udev rule for boot sync ──────────────────
echo "Step 7: Creating boot-sync udev rule..."
cat > /etc/udev/rules.d/85-hwclock.rules << 'EOF'
# Sync system clock from RTC as soon as /dev/rtc0 appears
KERNEL=="rtc0", RUN+="/sbin/hwclock --hctosys"
EOF
ok "Udev rule created at /etc/udev/rules.d/85-hwclock.rules"

# ── Step 8: Create systemd service for early boot sync ──────
echo "Step 8: Creating rtc-sync systemd service..."
cat > /etc/systemd/system/rtc-sync.service << 'EOF'
[Unit]
Description=Sync system clock from DS3231 RTC
DefaultDependencies=no
After=sysinit.target
Before=network.target systemd-timesyncd.service

[Service]
Type=oneshot
ExecStart=/sbin/hwclock --hctosys --utc
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
EOF

systemctl daemon-reload
systemctl enable rtc-sync.service 2>/dev/null
ok "rtc-sync.service installed and enabled"

# ── Done ────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  Setup complete!"
echo ""
echo "  IMPORTANT: Reboot is required for the"
echo "  device tree overlay to take effect."
echo ""
echo "  After reboot, verify with:"
echo "    bash rtc_health_check.sh"
echo ""
echo "  To fix time anytime, run:"
echo "    sudo bash fix_time.sh"
echo "============================================"
echo ""
read -p "Reboot now? (y/N): " REBOOT
if [ "$REBOOT" = "y" ] || [ "$REBOOT" = "Y" ]; then
    echo "Rebooting..."
    reboot
fi
