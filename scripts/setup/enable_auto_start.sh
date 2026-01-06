#!/bin/bash
# Helper to install the dashboard and auxiliary services (USB copy, cloud sync).
# Usage: sudo bash enable_auto_start.sh

set -euo pipefail

# Get the actual project root (two levels up from scripts/setup/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SETUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pushd "$SCRIPT_DIR" >/dev/null

mkdir -p "$SCRIPT_DIR/logs"

# Logfile for installer runs (append-only)
LOGFILE="$SCRIPT_DIR/logs/enable_auto_start.run.log"
mkdir -p "$(dirname "$LOGFILE")"
touch "$LOGFILE" || true

# Helper to run a command and tee its output to LOGFILE while
# also letting the output appear on stdout (so the Technician UI shows it).
run_and_log() {
	echo "[CMD] $*" | tee -a "$LOGFILE"
	# Use a subshell to preserve exit code
	("$@") 2>&1 | tee -a "$LOGFILE"
	return ${PIPESTATUS[0]:-0}
}

TARGET_USER="${SUDO_USER:-$USER}"
echo "[INFO] Preparing meter-dashboard environment for user: ${TARGET_USER}"

# Prefer Python from venv313 if available, else generic venv, else system python3
VENV_DIR_DEFAULT="${SCRIPT_DIR}/venv313"
if [[ ! -x "${VENV_DIR_DEFAULT}/bin/python" ]] && [[ -x "${SCRIPT_DIR}/venv/bin/python" ]]; then
	VENV_DIR_DEFAULT="${SCRIPT_DIR}/venv"
fi
VENV_PY="${VENV_DIR_DEFAULT}/bin/python"
if [[ -x "$VENV_PY" ]]; then
	PY_EXEC="$VENV_PY"
else
	PY_EXEC="/usr/bin/python3"
fi
echo "[INFO] Using Python interpreter: ${PY_EXEC}"

# Allow a primary authoritative path for the USB copy script. If the
# developer's "offline-setup-12Sep" folder exists (project canonical copy),
# prefer that as the source of truth for the service ExecStart. This ensures
# the systemd unit always calls the expected copy script regardless of which
# helper script was invoked.
PRIMARY_DIR="$SCRIPT_DIR"
if [[ -d "${SCRIPT_DIR%/*}/offline-setup-12Sep" ]]; then
	PRIMARY_DIR="${SCRIPT_DIR%/*}/offline-setup-12Sep"
fi
echo "[INFO] Primary service directory set to: ${PRIMARY_DIR}"
CONFIG_DIR="${METER_CONFIG_DIR:-$HOME/meter_config}"

# Dashboard script is now in src/dashboard/
DASHBOARD_SCRIPT="$SCRIPT_DIR/src/dashboard/simple_rpi_dashboard.py"

# 1) Create/repair the venv and app directories as the target (non-root) user so
#    runtime directories (logs, data) are owned by the service user.
run_and_log sudo -u "$TARGET_USER" -H "$PY_EXEC" "$DASHBOARD_SCRIPT" --setup || {
	echo "[ERROR] Env setup failed. Try manually as ${TARGET_USER}:" | tee -a "$LOGFILE"
	echo "        $PY_EXEC $DASHBOARD_SCRIPT --setup" | tee -a "$LOGFILE"
	exit 1
}

# 2) Create and enable the systemd service (requires root)
echo "[INFO] Creating/enabling meter-dashboard systemd service" | tee -a "$LOGFILE"
run_and_log "$PY_EXEC" "$DASHBOARD_SCRIPT" --create-service || {
	echo "[ERROR] Failed to create service. You can run manually:" | tee -a "$LOGFILE"
	echo "        sudo $PY_EXEC $DASHBOARD_SCRIPT --create-service" | tee -a "$LOGFILE"
	exit 1
}

# 2b) Force service to use venv313 interpreter if available
SERVICE_FILE="/etc/systemd/system/meter-dashboard.service"
if [[ -x "${SCRIPT_DIR}/venv313/bin/python" && -f "$SERVICE_FILE" ]]; then
  echo "[INFO] Patching meter-dashboard.service to use venv313 interpreter"
  sudo sed -i "s#${SCRIPT_DIR}/venv/bin/python#${SCRIPT_DIR}/venv313/bin/python#g" "$SERVICE_FILE" || true
  sudo systemctl daemon-reload || true
fi

# 3) Ensure runtime directories are writable by the service user
mkdir -p "$SCRIPT_DIR/logs" "$SCRIPT_DIR/data/csv"
chown -R "$TARGET_USER":"$TARGET_USER" "$SCRIPT_DIR/logs" "$SCRIPT_DIR/data" || true
chmod -R u+rwX,g+rwX,o+rX "$SCRIPT_DIR/logs" "$SCRIPT_DIR/data" || true

# Helper: parse JSONC in bash via python to extract a value
jsonc_get() {
	local key_path="$1" # e.g. usb_copy.enabled
	"$PY_EXEC" "$SCRIPT_DIR/tools/jsonc_get.py" "$key_path" "$CONFIG_DIR/config.json" || true
}

USB_ENABLED="$(jsonc_get usb_copy.enabled || true)"
CLOUD_ENABLED="$(jsonc_get cloud_sync.enabled || true)"
CLOUD_INTERVAL_MIN="$(jsonc_get cloud_sync.interval_minutes || true)"
CLOUD_INTERVAL_SEC="$(jsonc_get cloud_sync.interval_seconds || true)"
if [[ -z "${CLOUD_INTERVAL_MIN}" ]]; then CLOUD_INTERVAL_MIN=10; fi
if [[ -z "${CLOUD_INTERVAL_SEC}" ]]; then CLOUD_INTERVAL_SEC=""; fi

echo "[INFO] Installing USB auto-copy service"
# USB copy script is now in scripts/system/ or src/services/
USB_COPY_SCRIPT="${SCRIPT_DIR}/scripts/system/usb_csv_auto_copy.py"
if [[ ! -f "$USB_COPY_SCRIPT" ]]; then
    USB_COPY_SCRIPT="${SCRIPT_DIR}/src/services/usb_csv_auto_copy.py"
fi

sudo tee /etc/systemd/system/usb_csv_auto_copy.service >/dev/null <<UNIT
[Unit]
Description=USB CSV Auto-Copy Service
After=multi-user.target

[Service]
Type=simple
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/python3 ${USB_COPY_SCRIPT} --daemon
Restart=on-failure
RestartSec=5
Nice=10
IOSchedulingClass=idle

[Install]
WantedBy=multi-user.target
UNIT

echo "[INFO] Installing Cloud Sync service and timer"
# Cloud sync script is now in src/network/
CLOUD_SYNC_SCRIPT="${SCRIPT_DIR}/src/network/cloud_sync.py"

sudo tee /etc/systemd/system/cloud_sync.service >/dev/null <<UNIT
[Unit]
Description=Cloud Sync (oneshot) for CSV
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PY_EXEC} ${CLOUD_SYNC_SCRIPT} --run-once

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

# If the usb_download_mvp helper installer exists, run it and capture logs
if [[ -x "${SCRIPT_DIR}/usb_download_mvp/scripts/install_service.sh" ]]; then
	echo "[INFO] Running usb_download_mvp/scripts/install_service.sh" | tee -a "$LOGFILE"
	run_and_log sudo bash "${SCRIPT_DIR}/usb_download_mvp/scripts/install_service.sh" || {
		echo "[WARN] usb_download_mvp installer returned non-zero exit code" | tee -a "$LOGFILE"
	}
else
	echo "[INFO] usb_download_mvp installer script not present or not executable; skipping" | tee -a "$LOGFILE"
fi

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
ExecStart=${PY_EXEC} ${SCRIPT_DIR}/netwatch_trigger.py
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
