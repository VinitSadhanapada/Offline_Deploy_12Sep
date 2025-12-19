#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/usb_ap_disable.log
echo "[$(date +%FT%T%z)] disable_ap_mode.sh invoked: $*" | tee -a "$LOG"

# Resolve project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/usb_download_mvp/scripts"
ENFORCE_SCRIPT="$SCRIPTS_DIR/enforce_ap_mode.sh"

usage() {
    echo "Usage: $0 [--install|--run|--uninstall|--status]" | tee -a "$LOG"
    exit 2
}

case "${1:-}" in
    --install)
        echo "Installing usb_ap_disable.service (wrapper will call enforce_ap_mode stop)" | tee -a "$LOG"
        sudo tee /etc/systemd/system/usb_ap_disable.service >/dev/null <<UNIT
[Unit]
Description=USB AP Mode disable helper (wrapper)
After=network.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/bash $SCRIPTS_DIR/disable_ap_mode_wrapper.sh
WorkingDirectory=$SCRIPT_DIR
StandardOutput=journal
StandardError=journal
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT

        sudo systemctl daemon-reload
        sudo systemctl enable --now usb_ap_disable.service || true
        echo "Installed and enabled usb_ap_disable.service" | tee -a "$LOG"
        exit 0
        ;;
    --uninstall)
        echo "Uninstalling usb_ap_disable.service" | tee -a "$LOG"
        sudo systemctl disable --now usb_ap_disable.service || true
        sudo rm -f /etc/systemd/system/usb_ap_disable.service || true
        sudo systemctl daemon-reload || true
        echo "usb_ap_disable.service removed" | tee -a "$LOG"
        exit 0
        ;;
    --status)
        echo "Status (journal tail):" | tee -a "$LOG"
        sudo journalctl -u usb_ap_disable.service -n 200 --no-pager | sed -n '1,200p' | tee -a "$LOG"
        exit 0
        ;;
    --run|"")
        if [[ -x "$ENFORCE_SCRIPT" ]]; then
            echo "Delegating to enforce_ap_mode.sh stop" | tee -a "$LOG"
            set +e
            sudo bash "$ENFORCE_SCRIPT" stop 2>&1 | tee -a "$LOG"
            RC=${PIPESTATUS[0]:-0}
            set -e
            exit $RC
        else
            echo "enforce_ap_mode.sh not found or not executable; nothing to run" | tee -a "$LOG"
            exit 2
        fi
        ;;
    *)
        usage
        ;;
esac
echo "AP disabled (attempted) at $(date +%FT%T%z)" | tee -a "$LOG"
