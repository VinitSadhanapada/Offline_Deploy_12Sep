#!/usr/bin/env bash
echo "This helper script has been removed; systemd units call enforce_ap_mode.sh directly." >&2
echo "Use: sudo systemctl start usb_ap_disable.service or sudo systemctl start usb_ap.service" >&2
exit 2
