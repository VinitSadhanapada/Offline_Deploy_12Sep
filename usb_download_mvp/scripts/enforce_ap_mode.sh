#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/usb_ap_enforce.log
MARKER=/run/usb_ap_enforce_stopped_services

echo "[$(date +%FT%T%z)] enforce_ap_mode.sh invoked: $*" | tee -a "$LOG"

usage() {
    cat <<USAGE
Usage: $0 start|stop

start:  Force wlan0 into AP mode (stops/masks common network managers,
        starts hostapd/dnsmasq and assigns 192.168.50.1/24). THIS MAY DROP
        REMOTE SSH SESSIONS. Use only with local access if concerned.

stop:   Restore previously-stopped services and unmask them.
USAGE
    exit 2
}

if [ "$#" -lt 1 ]; then
    usage
fi

CMD=$1

case "$CMD" in
    start)
        echo "Starting enforce AP procedure" | tee -a "$LOG"

        # Stop and mask competing services and record which were stopped
        rm -f "$MARKER" || true
        for svc in NetworkManager wpa_supplicant dhcpcd connman iwd; do
            if systemctl list-unit-files | grep -q "^${svc}\.service"; then
                if systemctl is-active --quiet "$svc"; then
                    echo "Stopping $svc" | tee -a "$LOG"
                    sudo systemctl stop "$svc" 2>&1 | tee -a "$LOG" || true
                else
                    echo "$svc not active; skipping stop" | tee -a "$LOG"
                fi
                echo "Masking $svc" | tee -a "$LOG"
                sudo systemctl mask "$svc" 2>&1 | tee -a "$LOG" || true
                sudo systemctl disable "$svc" 2>&1 | tee -a "$LOG" || true
                echo "$svc" >> "$MARKER" || true
            else
                echo "$svc not installed; skipping" | tee -a "$LOG"
            fi
        done

        # Kill lingering processes
        echo "Killing lingering processes" | tee -a "$LOG"
        sudo pkill -f wpa_supplicant || true
        sudo pkill -f dhcpcd || true
        sudo pkill -f dhclient || true
        sudo pkill -f NetworkManager || true
        sudo pkill -f connman || true
        sudo pkill -f iwd || true

        # Bring interface down, flush addresses, then try to set AP mode
        if ip link show wlan0 >/dev/null 2>&1; then
            echo "Bringing wlan0 down and flushing addresses" | tee -a "$LOG"
            sudo ip link set wlan0 down || true
            sudo ip addr flush dev wlan0 || true

            # Attempt to set interface to AP type. Some drivers accept this,
            # others require creating a new interface; ignore failures.
            echo "Attempting to set wlan0 type to __ap" | tee -a "$LOG"
            sudo iw dev wlan0 set type __ap 2>&1 | tee -a "$LOG" || true
        else
            echo "wlan0 not present" | tee -a "$LOG"
        fi

        # Start hostapd and dnsmasq
        echo "Starting hostapd and dnsmasq" | tee -a "$LOG"
        sudo systemctl daemon-reload || true
        sudo systemctl restart hostapd 2>&1 | tee -a "$LOG" || true
        sudo systemctl restart dnsmasq 2>&1 | tee -a "$LOG" || true

        # Assign AP IP and bring interface up
        echo "Assigning 192.168.50.1/24 to wlan0 and bringing up" | tee -a "$LOG"
        sudo ip addr add 192.168.50.1/24 dev wlan0 2>&1 | tee -a "$LOG" || true
        sudo ip link set wlan0 up 2>&1 | tee -a "$LOG" || true

        echo "Post-start status:" | tee -a "$LOG"
        sudo iw dev wlan0 info 2>&1 | tee -a "$LOG" || true
        ip addr show wlan0 2>&1 | tee -a "$LOG" || true
        sudo systemctl status hostapd dnsmasq --no-pager 2>&1 | sed -n '1,200p' | tee -a "$LOG" || true

        echo "enforce_ap_mode: start complete" | tee -a "$LOG"
        ;;

    stop)
        echo "Stopping enforce AP and restoring services" | tee -a "$LOG"

        # Stop hostapd/dnsmasq and bring wlan0 down
        sudo systemctl stop hostapd dnsmasq 2>&1 | tee -a "$LOG" || true
        if ip link show wlan0 >/dev/null 2>&1; then
            sudo ip link set wlan0 down 2>&1 | tee -a "$LOG" || true
        fi

        # Restore services recorded in marker
        if [ -f "$MARKER" ]; then
            echo "Restoring services listed in $MARKER" | tee -a "$LOG"
            while IFS= read -r svc; do
                if [ -n "$svc" ]; then
                    echo "Unmasking and starting $svc" | tee -a "$LOG"
                    sudo systemctl unmask "$svc" 2>&1 | tee -a "$LOG" || true
                    sudo systemctl enable "$svc" 2>&1 | tee -a "$LOG" || true
                    sudo systemctl restart "$svc" 2>&1 | tee -a "$LOG" || true
                fi
            done < "$MARKER"
            rm -f "$MARKER" || true
        else
            echo "No marker file; nothing to restore" | tee -a "$LOG"
        fi

        # Final restart of common managers to be safe
        sudo systemctl restart NetworkManager wpa_supplicant dhcpcd 2>&1 | tee -a "$LOG" || true

        echo "enforce_ap_mode: stop complete" | tee -a "$LOG"
        ;;

    *)
        usage
        ;;
esac

exit 0
