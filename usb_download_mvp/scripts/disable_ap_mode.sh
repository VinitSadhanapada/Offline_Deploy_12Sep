#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/usb_ap_disable.log
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
    # When disabling the AP, bring the interface down to release any AP mode
    # allocations. Users may re-enable client mode afterward as needed.
    sudo ip link set wlan0 down || true
    echo "wlan0 set down" | tee -a "$LOG"
fi

if systemctl list-unit-files | grep -q "^usb_ap.service"; then
    echo "Disabling usb_ap.service" | tee -a "$LOG"
    sudo systemctl disable --now usb_ap.service || true
fi

MARKER=/run/usb_ap_stopped_services
if [ -f "$MARKER" ]; then
    echo "Found marker of previously stopped services: $MARKER" | tee -a "$LOG"
    while IFS= read -r svc; do
        if [ -n "$svc" ]; then
            echo "Unmasking and starting $svc" | tee -a "$LOG"
            sudo systemctl unmask "$svc" 2>&1 | tee -a "$LOG" || true
            sudo systemctl enable "$svc" 2>&1 | tee -a "$LOG" || true
            sudo systemctl start "$svc" 2>&1 | tee -a "$LOG" || true
        fi
    done < "$MARKER"
    rm -f "$MARKER" || true
    echo "Restored stopped services and removed marker" | tee -a "$LOG"
fi

# Ensure common network managers are restarted so networking comes back reliably.
# This line specifically restarts NetworkManager, wpa_supplicant and dhcpcd if
# they exist; `|| true` prevents failures from aborting the script.
sudo systemctl restart NetworkManager wpa_supplicant dhcpcd 2>&1 | tee -a "$LOG" || true

echo "AP disabled (attempted) at $(date +%FT%T%z)" | tee -a "$LOG"
