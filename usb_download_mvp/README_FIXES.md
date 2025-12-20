# Fixes applied to make the AP & download server work on fresh installs

This document summarizes the small but important fixes applied during debugging so you can reproduce them on another Raspberry Pi (fresh install) or audit what changed.

Paths referenced are relative to the repository root: `usb_download_mvp/...`.

## Summary of issues seen
- `hostapd` could not start because `/etc/hostapd/hostapd.conf` was missing.
- `dnsmasq` had no DHCP range configured for the AP because `/etc/dnsmasq.d/simplemeter-ap.conf` was missing or an empty placeholder, so clients associated but never received an IP.
- `hostapd` and `dnsmasq` were transiently stopped by a service/GUI action while clients were trying to obtain DHCP leases (causing timeouts).
- Installer scripts sometimes left conflicting network managers active or did not deploy the repo-provided dnsmasq AP config.

## Files we changed (what & why)

- `usb_download_mvp/dnsmasq/simplemeter-ap.conf`
  - Added a DHCP config for the AP:
    - `interface=wlan0`, `bind-interfaces`, `dhcp-range=192.168.50.10,192.168.50.200,12h`, `dhcp-option=3,192.168.50.1`
  - Purpose: ensure `dnsmasq` has an AP DHCP pool on fresh installs.

- `usb_download_mvp/scripts/ssid_hint.sh` (patched)
  - Now creates `/etc/hostapd/hostapd.conf` (existing behavior) and also ensures `/etc/dnsmasq.d/simplemeter-ap.conf` exists with the DHCP range.
  - Important defensive change: if `/etc/dnsmasq.d/simplemeter-ap.conf` exists but is empty or tiny (placeholder), the script overwrites it with the correct AP DHCP config. This prevents a zero-byte placeholder file from blocking DHCP.

- `usb_download_mvp/scripts/install_service.sh` (patched)
  - Deploys `usb_download_mvp/dnsmasq/simplemeter-ap.conf` into `/etc/dnsmasq.d/` during install and defensively overwrites empty/placeholder targets.
  - Unmasks `hostapd` so it can be enabled on systems where the package left it masked.
  - Ensures `denyinterfaces wlan0` is appended to `/etc/dhcpcd.conf` (idempotent) so `dhcpcd` won't automatically configure `wlan0` and conflict with AP mode.
  - Enables and restarts systemd services: `hostapd`, `dnsmasq`, `download-server`, `ssid-hint`, `usb_ap.service`, etc.

- `scripts/restore_wlan.sh` (added earlier)
  - Safe helper to restore the client WLAN state if you accidentally put the Pi into AP-only mode and lose remote SSH.

## Why these changes fix the symptoms
- `hostapd` needs a config file in `/etc/hostapd/hostapd.conf` (systemd unit often has ConditionFileNotEmpty). `ssid_hint.sh` ensures that file exists.
- `dnsmasq` must have a DHCP range on the AP interface; without it, phones will associate with the AP radio but never get an IP. Deploying `simplemeter-ap.conf` fixes that.
- Empty/placeholder files can block automated generators; both `install_service.sh` and `ssid_hint.sh` now overwrite placeholder/empty files.
- Preventing `dhcpcd` from configuring `wlan0` avoids IP address conflicts when switching to AP mode.

## Exact commands to apply the fixes on another Pi

Assuming you have the repo copied to `/home/pi/Desktop/offline-setup-12Sep` on the other Pi (recommended):

1) Copy dnsmasq config and make scripts executable, then run the installer (idempotent):

```bash
cd ~/Desktop/offline-setup-12Sep
sudo cp usb_download_mvp/dnsmasq/simplemeter-ap.conf /etc/dnsmasq.d/simplemeter-ap.conf
sudo chmod +x usb_download_mvp/scripts/*.sh
sudo bash usb_download_mvp/scripts/install_service.sh
```

2) If you don't want to run the full installer, manually ensure the two small pieces are present:

```bash
# Hostapd config (generate if missing)
sudo bash /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/scripts/ssid_hint.sh

# Ensure dnsmasq has the AP DHCP range (overwrite any placeholder)
sudo tee /etc/dnsmasq.d/simplemeter-ap.conf > /dev/null <<'EOF'
interface=wlan0
bind-interfaces
domain-needed
bogus-priv
dhcp-range=192.168.50.10,192.168.50.200,12h
dhcp-option=3,192.168.50.1
EOF

# Restart services
sudo systemctl restart dnsmasq hostapd
```

3) Safety: If you are SSH'd into the Pi remotely, avoid running scripts that forcibly disable `wpa_supplicant` or NetworkManager. Use the installer above which avoids unsafe remote-only changes.

## How to verify it worked (quick checks on the Pi)

```bash
# AP interface address
ip -4 addr show dev wlan0

# Watch association + DHCP activity
sudo journalctl -u hostapd -f
sudo journalctl -u dnsmasq -f
sudo tail -f /var/lib/misc/dnsmasq.leases

# Verify the download server is reachable (on Pi)
curl -I http://192.168.50.1:8080/
```

When your phone connects you should see hostapd log lines like:

```
wlan0: STA <MAC> IEEE 802.11: associated
```

and dnsmasq DHCP log lines like:

```
DHCPDISCOVER(wlan0) <MAC>
DHCPOFFER(wlan0) 192.168.50.xxx <MAC>
DHCPREQUEST(wlan0) 192.168.50.xxx <MAC>
DHCPACK(wlan0) 192.168.50.xxx <MAC> <hostname>
```

## Notes & troubleshooting
- If you still see `Error: ipv4: Address already assigned.` when assigning `192.168.50.1`, check for `dhcpcd` or another manager that still configures `wlan0` — ensure `denyinterfaces wlan0` is present in `/etc/dhcpcd.conf` or restart the Pi.
- The GUI (`simple_meter_ui.py`) will call `systemctl disable --now usb_ap.service` when you toggle AP off; avoid disabling the AP from the UI during tests or add a short delay before disabling. We updated the installer message to clarify URLs and added defensive script behaviour.
- We recommend keeping `download-server` on port `8080` for now. If you want to serve on port 80, set `Environment=USB_MVP_PORT=80` in `/etc/systemd/system/download-server.service` (unit already allows CAP_NET_BIND_SERVICE).

## Commits and branch
- Branch: `temp-usb-copy-fixes-2025-12-03`
- Commit examples for reference:
  - `93bcda9` — dnsmasq: add AP DHCP config for wlan0
  - `235e03f` — ssid_hint: ensure dnsmasq AP DHCP config is created when generating hostapd.conf
  - `6e8b8f9` — installer: deploy dnsmasq AP config; ssid_hint: overwrite empty dnsmasq config
  - `005d252` — docs: clarify USB gadget URL is optional in installer output

If you want, I can prepare a small patch bundle you can copy to the fresh Pi (or open a pull request); tell me the other Pi's repo path and I will either (a) push these commits into a PR, or (b) create a patch file you can apply with `git am`.

---
Location: `usb_download_mvp/README_FIXES.md`

If you want this README expanded with exact diffs (unified patch snippets) or a `PATCH.md` with copy/paste-ready `sed`/`tee` commands for each edit, I can add that too.
