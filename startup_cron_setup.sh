#!/bin/bash
# This script sets up an @reboot cron job for the current dashboard only.
# Usage: sudo bash startup_cron_setup.sh

set -euo pipefail

SCRIPT_DIR="/home/$USER/Desktop/offline-setup-12Sep"
PYTHON="$(which python3)"
DASHBOARD="$SCRIPT_DIR/simple_rpi_dashboard.py"

# Remove any previous @reboot lines for this dashboard
crontab -l | grep -v "$DASHBOARD --run" > /tmp/cron_tmp_$$ || true

# Add new @reboot line
# Ensure logs directory exists and log to a consistent location
mkdir -p "$SCRIPT_DIR/logs"
{
    cat /tmp/cron_tmp_$$ 2>/dev/null || true
    echo "@reboot $PYTHON $DASHBOARD --run > $SCRIPT_DIR/logs/cron_run.log 2>&1 &"
} | crontab -

rm -f /tmp/cron_tmp_$$

echo "[INFO] Cron job set for dashboard. It will run on every reboot."
