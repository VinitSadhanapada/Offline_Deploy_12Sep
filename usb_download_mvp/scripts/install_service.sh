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
# Deploy dnsmasq AP config from the repo. Overwrite if missing or empty
REPO_DNS_CONF="$REPO_DIR/dnsmasq/simplemeter-ap.conf"
TARGET_DNS_CONF="/etc/dnsmasq.d/simplemeter-ap.conf"
if [ -f "$REPO_DNS_CONF" ]; then
	# Copy unconditionally but be defensive: if a placeholder file exists
	# with no meaningful contents, overwrite it.
	sudo cp "$REPO_DNS_CONF" "$TARGET_DNS_CONF"
	# If target is unexpectedly tiny (e.g. 0/1 bytes), overwrite from repo again
	if [ -f "$TARGET_DNS_CONF" ] && [ $(stat -c%s "$TARGET_DNS_CONF") -le 8 ]; then
		echo "Warning: $TARGET_DNS_CONF seems empty; overwriting from repo"
		sudo cp "$REPO_DNS_CONF" "$TARGET_DNS_CONF"
	fi
else
	echo "Repository dnsmasq template $REPO_DNS_CONF missing; skipping copy"
fi
sudo cp "$REPO_DIR/systemd/usb_ap.service" /etc/systemd/system/usb_ap.service || true
sudo cp "$REPO_DIR/systemd/usb_ap_disable.service" /etc/systemd/system/usb_ap_disable.service || true

# Enable services
	# Ensure hostapd will be startable: unmask (package installs may leave
	# hostapd masked) and create a hostapd.conf if missing using the
	# included ssid_hint helper. This guarantees the service can be enabled
	# and will come back after reboot.
	sudo systemctl unmask hostapd || true
	if [ ! -f /etc/hostapd/hostapd.conf ] && [ -x "$REPO_DIR/usb_download_mvp/scripts/ssid_hint.sh" ]; then
			echo "Creating /etc/hostapd/hostapd.conf using ssid_hint.sh"
			sudo bash "$REPO_DIR/usb_download_mvp/scripts/ssid_hint.sh" || true
	else
			echo "/etc/hostapd/hostapd.conf already exists or ssid_hint.sh not present; skipping generation"
	fi

	  # Prevent dhcpcd from automatically configuring wlan0 (avoids
	  # conflicting client IPs when AP mode is enabled). This is
	  # intentionally idempotent and does not restart dhcpcd to avoid
	  # disrupting remote sessions during install.
	  DHCPCD_CONF=/etc/dhcpcd.conf
	  if [ -f "$DHCPCD_CONF" ]; then
		  if ! grep -q '^denyinterfaces wlan0' "$DHCPCD_CONF"; then
			  echo 'denyinterfaces wlan0' | sudo tee -a "$DHCPCD_CONF" >/dev/null || true
			  echo "Appended 'denyinterfaces wlan0' to $DHCPCD_CONF (will take effect after dhcpcd restart or reboot)"
		  else
			  echo "$DHCPCD_CONF already contains denyinterfaces wlan0; skipping"
		  fi
	  fi

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
sudo cp "$REPO_DIR/systemd/watchdog.service" /etc/systemd/system/watchdog.service || true
sudo cp "$REPO_DIR/systemd/watchdog.timer" /etc/systemd/system/watchdog.timer || true
sudo chmod 644 /etc/systemd/system/watchdog.service || true
sudo chmod 644 /etc/systemd/system/watchdog.timer || true
sudo systemctl daemon-reload || true
sudo systemctl enable --now watchdog.timer || true

echo "Installed watchdog.timer — status will be appended to /var/log/usb_watchdog.log every hour" | tee -a /dev/stderr || true

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
