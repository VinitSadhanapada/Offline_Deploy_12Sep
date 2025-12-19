# Technician USB Access System — MVP

USB plug → Browser → One-click "Download All Data" button.

## What This Provides
- ✅ USB network connection
- ✅ Browser access without SSH
- ✅ Single button to download ALL data as ZIP
- ✅ Auto-starts on boot via systemd
- ❌ No authentication (MVP)

## Folder Overview
- `server.py`: Flask app serving the one-click ZIP download
- `config.py` + `config.json`: Data directory config (env-var override supported)
- `templates/index.html`: Single-page UI
- `systemd/download-server.service`: Systemd unit file
- `network/05-usb0.network`: USB network config template
- `scripts/install_service.sh`: Quick installer (Flask + systemd + network)
- `requirements.txt`: Python dependency list

## Data Directory
Default path: `/home/pi/Desktop/offline-setup-12Sep/data/csv`
- Override via env var `USB_MVP_DATA_DIR`
- Or edit `usb_download_mvp/config.json`

## Quick Install (5 minutes)
```bash
# 1) Optional: create venv (recommended)
python3 -m venv ~/venvs/usb_mvp && source ~/venvs/usb_mvp/bin/activate

# 2) Install Flask
pip3 install -r /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/requirements.txt

# 3) Test run (foreground)
python3 /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/server.py
# Visit http://192.168.7.2:8080 or http://raspberrypi.local:8080

# 4) Install as a service (auto-start)
chmod +x /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/scripts/install_service.sh
/home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/scripts/install_service.sh
```

## Systemd Service (template)
The bundled service enables binding to port 80 without root using capabilities.
Path: `/home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/systemd/download-server.service`

```ini
[Unit]
Description=MVP Download Server
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/Desktop/offline-setup-12Sep/usb_download_mvp
ExecStart=/usr/bin/python3 /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/server.py
Restart=always
Environment=USB_MVP_PORT=8080
Environment=USB_MVP_DATA_DIR=/home/pi/Desktop/offline-setup-12Sep/data/csv
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
```

## USB Network Config (template)
Path: `/home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/network/05-usb0.network`
```ini
[Match]
Name=usb0

[Network]
Address=192.168.7.2/24
DHCPServer=yes
```
Enable services:
```bash
sudo systemctl enable systemd-networkd
sudo systemctl enable avahi-daemon
sudo systemctl restart systemd-networkd avahi-daemon
```

## Technician Instructions
Two ways to connect on RPi 4B:

- Phone Tethering Mode (DHCP client)
	- Phone gives Pi a dynamic IP on `usb0`.
	- On Pi, check `ip -brief address show usb0` and use that IP on the phone.

- Wi‑Fi SSID Hint (for headless discovery)
	- Pi sets a temporary hotspot SSID like `PI-USB-10.201.29.56` that shows the current `usb0` IP.
	- You don’t need to connect to this hotspot; just read the SSID and then open that IP in the browser while USB tethering stays enabled.
	- Control the hint service:
	  ```bash
	  sudo systemctl restart ssid-hint
	  ```

## Notes
- Data is read-only; no upload/delete
- Local-only access via USB network
- For production, add password protection
 - Android typically does not resolve `.local` mDNS over USB; use the IP.
 - RPi 4B does not support USB gadget networking via its USB-C power port; use Phone Tethering + SSID Hint.
