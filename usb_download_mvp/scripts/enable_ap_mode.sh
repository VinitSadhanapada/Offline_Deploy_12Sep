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
        #!/usr/bin/env bash
        set -euo pipefail

        LOG=/var/log/usb_ap_enable.log
        echo "[$(date +%FT%T%z)] enable_ap_mode.sh invoked: $*" | tee -a "$LOG"

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
                echo "Installing usb_ap.service (wrapper will call enforce_ap_mode)" | tee -a "$LOG"
                sudo tee /etc/systemd/system/usb_ap.service >/dev/null <<UNIT
        [Unit]
        Description=USB AP Mode helper
        After=network.target

        [Service]
        Type=oneshot
        ExecStart=/usr/bin/bash $SCRIPTS_DIR/enable_ap_mode_wrapper.sh
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
                if [[ -x "$ENFORCE_SCRIPT" ]]; then
                    echo "Delegating to enforce_ap_mode.sh start" | tee -a "$LOG"
                    set +e
                    sudo bash "$ENFORCE_SCRIPT" start 2>&1 | tee -a "$LOG"
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
esac
