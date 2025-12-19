#!/usr/bin/env bash
set -euo pipefail

# Wrapper to run enable_ap_mode.sh and produce clear logs to both
# systemd journal and a persistent logfile for troubleshooting.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null && pwd)"
WRAP_LOG="/var/log/usb_ap_enable.log"
INNER_SCRIPT="$SCRIPT_DIR/scripts/enforce_ap_mode.sh"

mkdir -p "$(dirname "$WRAP_LOG")"
touch "$WRAP_LOG" || true

echo "==== USB AP enable wrapper started: $(date -u '+%Y-%m-%d %H:%M:%SZ') ====" | tee -a "$WRAP_LOG"
echo "SCRIPT_DIR=$SCRIPT_DIR" | tee -a "$WRAP_LOG"
echo "Running: $INNER_SCRIPT" | tee -a "$WRAP_LOG"

if [[ ! -x "$INNER_SCRIPT" ]]; then
    echo "ERROR: inner script not found or not executable: $INNER_SCRIPT" | tee -a "$WRAP_LOG" >&2
    exit 2
fi

# Run the enforce script in start mode
set +e
"$INNER_SCRIPT" start 2>&1 | tee -a "$WRAP_LOG"
RC=${PIPESTATUS[0]:-0}
set -e

if [[ $RC -eq 0 ]]; then
    echo "USB AP enable succeeded (rc=$RC) at: $(date -u '+%Y-%m-%d %H:%M:%SZ')" | tee -a "$WRAP_LOG"
else
    echo "USB AP enable FAILED (rc=$RC) at: $(date -u '+%Y-%m-%d %H:%M:%SZ')" | tee -a "$WRAP_LOG" >&2
fi

exit $RC
