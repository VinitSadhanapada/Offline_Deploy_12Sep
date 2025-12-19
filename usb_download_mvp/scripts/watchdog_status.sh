#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/usb_watchdog.log
mkdir -p "$(dirname "$LOG")"
touch "$LOG" || true

echo "==== Watchdog run: $(date -u '+%Y-%m-%d %H:%M:%SZ') ====" | tee -a "$LOG"

# Systemd units to monitor (services and timers)
units=(
  meter-dashboard.service
  usb_csv_auto_copy.service
  download-server.service
  hostapd.service
  dnsmasq.service
  ssid-hint.service
  netwatch-trigger.service
  cloud_sync.timer
  usb_ap.service
  usb_ap_disable.service
  usb-gadget.service
)

echo "-- Systemd units status --" | tee -a "$LOG"
for u in "${units[@]}"; do
  if systemctl list-unit-files | grep -q "^${u}"; then
    state=$(systemctl is-active "$u" 2>/dev/null || echo inactive)
    aent=$(systemctl show -p ActiveEnterTimestamp "$u" 2>/dev/null | sed -n 's/^ActiveEnterTimestamp=//p')
    echo "$u: $state (active since: ${aent:-N/A})" | tee -a "$LOG"
  else
    echo "$u: unit not present" | tee -a "$LOG"
  fi
done

echo "-- Process-level checks --" | tee -a "$LOG"
# Processes to check by simple name/pgrep (may match multiple pids)
procs=(
  meter_device.py
  meter_manager.py
  simple_rpi_dashboard.py
  usb_csv_auto_copy.py
  cloud_sync.py
  netwatch_trigger.py
  server.py
  hostapd
  dnsmasq
  python3
)

for p in "${procs[@]}"; do
  pids=$(pgrep -f "$p" || true)
  if [ -z "$pids" ]; then
    echo "$p: not running" | tee -a "$LOG"
  else
    for pid in $pids; do
      etime=$(ps -o etime= -p "$pid" 2>/dev/null || echo N/A)
      cmd=$(ps -p "$pid" -o cmd= 2>/dev/null || echo N/A)
      echo "$p: pid=$pid up=$etime cmd='$cmd'" | tee -a "$LOG"
    done
  fi
done

echo "-- Network interfaces --" | tee -a "$LOG"
ip -brief addr show wlan0 || true | tee -a "$LOG"
ip -brief addr show usb0 || true | tee -a "$LOG"

echo "==== End watchdog run ====" | tee -a "$LOG"

exit 0
