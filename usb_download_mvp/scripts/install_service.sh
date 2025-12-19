#!/usr/bin/env bash
set -euo pipefail

# Repository root (parent of this scripts/ directory)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null && pwd)"
VENV="$REPO_DIR/.venv"
REQ_FILE="$REPO_DIR/requirements.txt"

# Determine non-root user to create / populate venv when script is run via sudo
RUN_AS="${SUDO_USER:-${USER:-pi}}"

echo "Using repo dir: $REPO_DIR"

# Install Avahi / hostapd / dnsmasq (requires sudo)
sudo apt-get update -y
sudo apt-get install -y avahi-daemon hostapd dnsmasq

 # Create or reuse a top-level venv so other components share the same environment.
if [ -x "$VENV/bin/python" ]; then
	echo "Using existing venv at $VENV"
else
	echo "Creating venv at $VENV as user $RUN_AS (using copies to avoid symlink failures)"
	if [ "$(id -u)" -eq 0 ]; then
		sudo -u "$RUN_AS" python3 -m venv --copies "$VENV" || true
	else
		python3 -m venv --copies "$VENV" || true
	fi
	# If venv creation left an incomplete tree (no python), try recreating with --clear
	if [ ! -x "$VENV/bin/python" ]; then
		echo "Venv creation incomplete; recreating $VENV with --clear --copies"
		rm -rf "$VENV"
		if [ "$(id -u)" -eq 0 ]; then
			sudo -u "$RUN_AS" python3 -m venv --clear --copies "$VENV"
		else
			python3 -m venv --clear --copies "$VENV"
		fi
	fi
fi

# Install (upgrade) pip and requirements into the venv using the venv python
if [ "$(id -u)" -eq 0 ]; then
	sudo -u "$RUN_AS" "$VENV/bin/python" -m pip install --upgrade pip
	sudo -u "$RUN_AS" "$VENV/bin/python" -m pip install -r "$REQ_FILE"
else
	"$VENV/bin/python" -m pip install --upgrade pip
	"$VENV/bin/python" -m pip install -r "$REQ_FILE"
fi

# Configure USB network

sudo cp "$REPO_DIR/network/05-usb0.network" /etc/systemd/network/05-usb0.network

# Deploy systemd service files and other config
sudo cp "$REPO_DIR/systemd/download-server.service" /etc/systemd/system/download-server.service
sudo cp "$REPO_DIR/systemd/ssid-hint.service" /etc/systemd/system/ssid-hint.service
sudo cp "$REPO_DIR/systemd/ssid-hint@.service" /etc/systemd/system/ssid-hint@.service
sudo cp "$REPO_DIR/udev/99-usb0-ssid.rules" /etc/udev/rules.d/99-usb0-ssid.rules
sudo cp "$REPO_DIR/network/25-wlan0-ap.network" /etc/systemd/network/25-wlan0-ap.network
sudo cp "$REPO_DIR/dnsmasq/simplemeter-ap.conf" /etc/dnsmasq.d/simplemeter-ap.conf
sudo cp "$REPO_DIR/systemd/usb_ap.service" /etc/systemd/system/usb_ap.service || true
sudo cp "$REPO_DIR/systemd/usb_ap_disable.service" /etc/systemd/system/usb_ap_disable.service || true

# Enable services
sudo systemctl enable systemd-networkd
sudo systemctl enable avahi-daemon
sudo systemctl daemon-reload
sudo systemctl enable download-server
sudo systemctl enable hostapd
sudo systemctl enable ssid-hint
sudo systemctl enable dnsmasq
sudo systemctl enable usb_ap.service || true
sudo systemctl enable usb_ap_disable.service || true
# NOTE: Previously this script stopped/disabled wpa_supplicant which made
# the device unreachable over Wi‑Fi. That behaviour is unsafe for remote
# devices and has been removed. If you intentionally want to switch the
# device into AP-only mode, handle that manually on a local console.
# sudo systemctl stop wpa_supplicant || true
# sudo systemctl disable wpa_supplicant || true
sudo udevadm control --reload-rules

# Ensure scripts that need execution permission are executable. On a
# fresh clone the executable bit may be missing; set it explicitly so
# systemd units and manual invocations work.
sudo chmod +x "$REPO_DIR/scripts/"*.sh || true
sudo chmod 644 /etc/systemd/system/usb_ap.service || true
sudo chmod 644 /etc/systemd/system/usb_ap_disable.service || true
sudo chmod +x "$REPO_DIR/scripts/enforce_ap_mode.sh" || true

# Restart services
sudo systemctl restart systemd-networkd avahi-daemon hostapd dnsmasq download-server ssid-hint
sudo systemctl daemon-reload || true
sudo systemctl restart usb_ap.service || true
sudo systemctl restart usb_ap_disable.service || true

echo "MVP Download Server installed and started. Access the server on port 8080:" \
	| tee -a /dev/stderr || true
echo "  - Wi‑Fi AP gateway: http://192.168.50.1:8080" \
	| tee -a /dev/stderr || true
echo "  - USB gadget:      http://192.168.7.2:8080" \
	| tee -a /dev/stderr || true
echo "  - mDNS:            http://raspberrypi.local:8080" \
	| tee -a /dev/stderr || true
