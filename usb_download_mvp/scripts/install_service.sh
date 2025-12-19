#!/usr/bin/env bash
set -e

# Install Flask
python3 -m venv /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/.venv
/home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/.venv/bin/pip install -r /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/requirements.txt

# Install Avahi for .local hostname resolution
sudo apt-get update -y
sudo apt-get install -y avahi-daemon hostapd dnsmasq

# Configure USB network
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/network/05-usb0.network /etc/systemd/network/05-usb0.network

# Deploy systemd service
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/systemd/download-server.service /etc/systemd/system/download-server.service
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/systemd/ssid-hint.service /etc/systemd/system/ssid-hint.service
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/systemd/ssid-hint@.service /etc/systemd/system/ssid-hint@.service
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/udev/99-usb0-ssid.rules /etc/udev/rules.d/99-usb0-ssid.rules
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/network/25-wlan0-ap.network /etc/systemd/network/25-wlan0-ap.network
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/dnsmasq/simplemeter-ap.conf /etc/dnsmasq.d/simplemeter-ap.conf
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/systemd/usb_ap.service /etc/systemd/system/usb_ap.service || true
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/systemd/usb_ap_disable.service /etc/systemd/system/usb_ap_disable.service || true

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
sudo chmod +x /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/scripts/*.sh || true
sudo chmod 644 /etc/systemd/system/usb_ap.service || true
sudo chmod 644 /etc/systemd/system/usb_ap_disable.service || true

# Restart services
sudo systemctl restart systemd-networkd avahi-daemon hostapd dnsmasq download-server ssid-hint
sudo systemctl daemon-reload || true
sudo systemctl restart usb_ap.service || true
sudo systemctl restart usb_ap_disable.service || true

echo "MVP Download Server installed and started. Access http://raspberrypi.local or http://192.168.7.2" 
