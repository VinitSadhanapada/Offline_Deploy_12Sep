#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/usb_ap_enable.log
echo "[$(date +%FT%T%z)] enable_ap_mode.sh invoked: $*" | tee -a "$LOG"

# Resolve project root (one level up from usb_download_mvp/scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/usb_download_mvp/scripts"

usage() {
    cat <<USAGE
Usage: $0 [--install|--run|--uninstall|--status] [--force]

Options:
  --force    Stop common network managers (NetworkManager, wpa_supplicant, dhcpcd)
             so hostapd can claim the wireless interface. WARNING: this may
             disconnect remote SSH sessions.
USAGE
    exit 2
}

# If the user supplies --force anywhere, enable destructive mode which will
# stop NetworkManager/wpa_supplicant/dhcpcd so hostapd can claim wlan0.
FORCE=false
if [[ "${*}" == *"--force"* ]]; then
    FORCE=true
fi

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

        # Optionally stop competing network managers so hostapd can claim the
        # wireless interface. This is destructive and may drop SSH connections.
        MARKER=/run/usb_ap_stopped_services
        if $FORCE; then
            echo "--force supplied: stopping, masking, and killing NetworkManager/wpa_supplicant/dhcpcd" | tee -a "$LOG"
            rm -f "$MARKER" || true
            for svc in NetworkManager wpa_supplicant dhcpcd; do
                if systemctl list-unit-files | grep -q "^${svc}\.service"; then
                    if systemctl is-active --quiet "$svc"; then
                        echo "Stopping $svc" | tee -a "$LOG"
                        sudo systemctl stop "$svc" 2>&1 | tee -a "$LOG" || true
                    else
                        echo "$svc not active; skipping stop" | tee -a "$LOG"
                    fi
                    echo "Masking $svc to prevent auto-restart" | tee -a "$LOG"
                    sudo systemctl mask "$svc" 2>&1 | tee -a "$LOG" || true
                    sudo systemctl disable "$svc" 2>&1 | tee -a "$LOG" || true
                    echo "$svc" >> "$MARKER" || true
                else
                    echo "$svc not installed; skipping" | tee -a "$LOG"
                fi
            done

            # Kill any lingering processes that might respawn the interface
            echo "Killing lingering processes: wpa_supplicant, dhcpcd, dhclient, NetworkManager" | tee -a "$LOG"
            sudo pkill -f wpa_supplicant || true
            sudo pkill -f dhcpcd || true
            sudo pkill -f dhclient || true
            sudo pkill -f NetworkManager || true

            echo "Recorded stopped/masked services to $MARKER" | tee -a "$LOG"
        fi

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
