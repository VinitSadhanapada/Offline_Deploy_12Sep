#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/usb_ap_enable.log
echo "[$(date +%FT%T%z)] disable_ap_mode.sh invoked: $*" | tee -a "$LOG"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/usb_download_mvp/scripts"

echo "Stopping AP services and disabling usb_ap.service" | tee -a "$LOG"
for svc in hostapd dnsmasq; do
    if systemctl list-unit-files | grep -q "^${svc}\.service"; then
        echo "Stopping ${svc}" | tee -a "$LOG"
        sudo systemctl stop "${svc}" 2>&1 | tee -a "$LOG" || true
    fi
done

if ip link show wlan0 >/dev/null 2>&1; then
    sudo ip link set wlan0 up || true
    echo "wlan0 set up" | tee -a "$LOG"
fi

if systemctl list-unit-files | grep -q "^usb_ap.service"; then
    echo "Disabling usb_ap.service" | tee -a "$LOG"
    sudo systemctl disable --now usb_ap.service || true
fi

echo "AP disabled (attempted) at $(date +%FT%T%z)" | tee -a "$LOG"
