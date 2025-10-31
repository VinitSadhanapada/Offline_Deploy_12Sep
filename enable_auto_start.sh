#!/bin/bash
# Helper to install the dashboard and auxiliary services (USB copy, cloud sync).
# Usage: sudo bash enable_auto_start.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pushd "$SCRIPT_DIR" >/dev/null

mkdir -p "$SCRIPT_DIR/logs"

echo "[INFO] Installing meter-dashboard service via simple_rpi_dashboard.py --install"
sudo python3 simple_rpi_dashboard.py --install || {
	echo "[ERROR] Failed to install service. You can run manually:"
	echo "        sudo python3 $SCRIPT_DIR/simple_rpi_dashboard.py --install"
	exit 1
}

# Helper: parse JSONC in bash via python to extract a value
jsonc_get() {
	local key_path="$1" # e.g. usb_copy.enabled
	python3 - "$key_path" <<'PY'
import json, re, sys, pathlib
cfg = pathlib.Path('config.jsonc').read_text()
def strip(line):
	in_str = False
	esc = False
	out = []
	i = 0
	while i < len(line):
		ch = line[i]
		if ch == '"' and not esc:
			in_str = not in_str
		if not in_str and i+1 < len(line) and line[i:i+2] == '//':
			break
		esc = (ch == '\\') and not esc
		out.append(ch)
		i += 1
	return ''.join(out)
clean = '\n'.join(strip(l) for l in cfg.splitlines())
data = json.loads(clean or '{}')
key = sys.argv[1]
cur = data
for part in key.split('.'):
	if isinstance(cur, dict) and part in cur:
		cur = cur[part]
	else:
		cur = None
		break
if isinstance(cur, bool):
	print('true' if cur else 'false')
elif isinstance(cur, (int, float)):
	print(cur)
elif isinstance(cur, str):
	print(cur)
else:
	print('')
PY
}

USB_ENABLED="$(jsonc_get usb_copy.enabled || true)"
CLOUD_ENABLED="$(jsonc_get cloud_sync.enabled || true)"
CLOUD_INTERVAL_MIN="$(jsonc_get cloud_sync.interval_minutes || true)"
CLOUD_INTERVAL_SEC="$(jsonc_get cloud_sync.interval_seconds || true)"
if [[ -z "${CLOUD_INTERVAL_MIN}" ]]; then CLOUD_INTERVAL_MIN=10; fi
if [[ -z "${CLOUD_INTERVAL_SEC}" ]]; then CLOUD_INTERVAL_SEC=""; fi

echo "[INFO] Installing USB auto-copy service"
sudo tee /etc/systemd/system/usb_csv_auto_copy.service >/dev/null <<UNIT
[Unit]
Description=USB CSV Auto-Copy Service
After=multi-user.target

[Service]
Type=simple
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/usb_csv_auto_copy.py --daemon
Restart=on-failure
RestartSec=5
Nice=10
IOSchedulingClass=idle

[Install]
WantedBy=multi-user.target
UNIT

echo "[INFO] Installing Cloud Sync service and timer"
sudo tee /etc/systemd/system/cloud_sync.service >/dev/null <<UNIT
[Unit]
Description=Cloud Sync (oneshot) for CSV
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/cloud_sync.py --run-once

[Install]
WantedBy=multi-user.target
UNIT

sudo tee /etc/systemd/system/cloud_sync.timer >/dev/null <<UNIT
[Unit]
Description=Run Cloud Sync periodically

[Timer]
OnBootSec=10s
OnUnitActiveSec=$([[ -n "${CLOUD_INTERVAL_SEC}" ]] && echo "${CLOUD_INTERVAL_SEC}s" || echo "${CLOUD_INTERVAL_MIN}min")
Unit=cloud_sync.service

[Install]
WantedBy=timers.target
UNIT

echo "[INFO] Reloading systemd daemon"
sudo systemctl daemon-reload

if [[ "${USB_ENABLED}" == "true" ]]; then
	echo "[INFO] Enabling and starting usb_csv_auto_copy.service"
	sudo systemctl enable usb_csv_auto_copy.service
	sudo systemctl restart usb_csv_auto_copy.service || sudo systemctl start usb_csv_auto_copy.service
else
	echo "[INFO] usb_copy.enabled=false; disabling usb_csv_auto_copy.service"
	sudo systemctl disable usb_csv_auto_copy.service || true
	sudo systemctl stop usb_csv_auto_copy.service || true
fi

if [[ "${CLOUD_ENABLED}" == "true" ]]; then
	echo "[INFO] Enabling cloud_sync.timer"
	sudo systemctl enable cloud_sync.timer
	sudo systemctl restart cloud_sync.timer || sudo systemctl start cloud_sync.timer
	echo "[INFO] Enabling netwatch-trigger.service"
	sudo systemctl enable netwatch-trigger.service
	sudo systemctl restart netwatch-trigger.service || sudo systemctl start netwatch-trigger.service
else
	echo "[INFO] cloud_sync.enabled=false; disabling cloud-related services (timer + netwatch)"
	sudo systemctl disable cloud_sync.timer || true
	sudo systemctl stop cloud_sync.timer || true
	sudo systemctl disable netwatch-trigger.service || true
	sudo systemctl stop netwatch-trigger.service || true
fi

sudo tee /etc/systemd/system/netwatch-trigger.service >/dev/null <<UNIT
[Unit]
Description=Network Watcher (trigger cloud sync on connect)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/netwatch_trigger.py
Restart=always
RestartSec=5
Nice=10

[Install]
WantedBy=multi-user.target
UNIT

# Note: enabling/disabling of netwatch-trigger.service is handled above based on cloud config
echo "[INFO] netwatch-trigger.service unit installed (activation follows cloud_sync.enabled)"

echo "[INFO] Done. Services configured:"
echo "       - meter-dashboard.service (from simple_rpi_dashboard.py)"
echo "       - usb_csv_auto_copy.service (copies CSVs to USB when present)"
if [[ -n "${CLOUD_INTERVAL_SEC}" ]]; then
	echo "       - cloud_sync.timer (triggers cloud_sync.service every ${CLOUD_INTERVAL_SEC} sec)"
else
	echo "       - cloud_sync.timer (triggers cloud_sync.service every ${CLOUD_INTERVAL_MIN} min)"
fi
echo "       - netwatch-trigger.service (runs cloud sync immediately when internet returns)"

popd >/dev/null
