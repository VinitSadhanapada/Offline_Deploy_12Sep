#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/usb_ap_enable.log
echo "[$(date +%FT%T%z)] enable_ap_mode.sh invoked: $*" | tee -a "$LOG"

# Resolve project root (one level up from usb_download_mvp/scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/usb_download_mvp/scripts"

usage() {
    echo "Usage: $0 [--install|--run|--uninstall|--status]"
    exit 2
}

case "${1:-}" in
    --install)
        echo "Installing usb_ap.service" | tee -a "$LOG"
        sudo tee /etc/systemd/system/usb_ap.service >/dev/null <<UNIT
[Unit]
Description=USB AP Mode helper
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/bash $SCRIPTS_DIR/enable_ap_mode.sh --run
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT

        sudo systemctl daemon-reload
        sudo systemctl enable --now usb_ap.service || true
        echo "Installed and enabled usb_ap.service" | tee -a "$LOG"
        exit 0
        ;;
    --uninstall)
        echo "Uninstalling usb_ap.service" | tee -a "$LOG"
        sudo systemctl disable --now usb_ap.service || true
        sudo rm -f /etc/systemd/system/usb_ap.service || true
        sudo systemctl daemon-reload || true
        echo "usb_ap.service removed" | tee -a "$LOG"
        exit 0
        ;;
    --status)
        echo "Status (journal tail):" | tee -a "$LOG"
        sudo journalctl -u usb_ap.service -n 200 --no-pager | sed -n '1,200p' | tee -a "$LOG"
        exit 0
        ;;
    --run|"")
        echo "Attempting to enable AP services (hostapd/dnsmasq)" | tee -a "$LOG"
        # Try to start common AP services if available
        for svc in hostapd dnsmasq; do
            if systemctl list-unit-files | grep -q "^${svc}\.service"; then
                echo "Restarting ${svc}" | tee -a "$LOG"
                sudo systemctl restart "${svc}" 2>&1 | tee -a "$LOG" || true
            else
                echo "${svc} not installed or unit not present; skipping" | tee -a "$LOG"
            fi
        done

        # Bring up wireless interface
        if ip link show wlan0 >/dev/null 2>&1; then
            sudo ip link set wlan0 up || true
            echo "wlan0 set up" | tee -a "$LOG"
        else
            echo "wlan0 not present" | tee -a "$LOG"
        fi

        echo "AP enable: done (attempted) at $(date +%FT%T%z)" | tee -a "$LOG"
        exit 0
        ;;
    *)
        usage
        ;;
esac
