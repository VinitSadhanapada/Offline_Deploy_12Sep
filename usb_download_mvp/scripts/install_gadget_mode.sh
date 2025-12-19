#!/usr/bin/env bash
set -e

# Enable USB gadget mode for RPi (RNDIS over USB-C), assign fixed IP 192.168.7.2,
# and install a systemd unit to configure the gadget at boot.

# 1) Enable dwc2 overlay and module
if ! grep -q '^dtoverlay=dwc2' /boot/config.txt; then
  echo 'dtoverlay=dwc2' | sudo tee -a /boot/config.txt >/dev/null
  echo 'Added dtoverlay=dwc2 to /boot/config.txt'
fi

sudo mkdir -p /etc/modules-load.d
if ! grep -q '^dwc2$' /etc/modules-load.d/dwc2.conf 2>/dev/null; then
  echo 'dwc2' | sudo tee /etc/modules-load.d/dwc2.conf >/dev/null
  echo 'Enabled dwc2 module autoload.'
fi

# 2) Install gadget config script and service
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/scripts/usb_gadget.sh /usr/local/sbin/usb_gadget.sh
sudo chmod +x /usr/local/sbin/usb_gadget.sh

sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/systemd/usb-gadget.service /etc/systemd/system/usb-gadget.service
sudo systemctl daemon-reload
sudo systemctl enable usb-gadget.service

# 3) Set static IP + DHCP server for usb0 (Pi side 192.168.7.2)
sudo cp /home/pi/Desktop/offline-setup-12Sep/usb_download_mvp/network/05-usb0-gadget.network /etc/systemd/network/05-usb0.network
sudo systemctl enable systemd-networkd

# 4) Inform user to reboot to take effect
echo 'USB gadget mode prepared. Please reboot to activate USB device mode.'
echo 'After reboot: connect phone via USB-C to Pi, then open http://192.168.7.2 on the phone.'
