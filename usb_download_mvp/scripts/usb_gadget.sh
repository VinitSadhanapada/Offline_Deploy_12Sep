#!/usr/bin/env bash
set -euo pipefail

# Configure USB gadget (RNDIS) so phone sees Pi as a USB Ethernet device.
# Requires: dtoverlay=dwc2 enabled and libcomposite available.

modprobe libcomposite || true
GCFG=/sys/kernel/config/usb_gadget
mkdir -p "$GCFG"
cd "$GCFG"

if [[ ! -d g1 ]]; then
  mkdir g1
fi
cd g1

# IDs (Linux Foundation Ethernet)
echo 0x1d6b > idVendor
echo 0x0104 > idProduct

echo 0x0200 > bcdUSB
mkdir -p strings/0x409

echo "$(tr -dc 'A-F0-9' </dev/urandom | head -c 16)" > strings/0x409/serialnumber
echo "Raspberry Pi" > strings/0x409/manufacturer
echo "USB Ethernet" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409

echo "Config 1: RNDIS" > configs/c.1/strings/0x409/configuration

echo 120 > configs/c.1/MaxPower

# RNDIS function
mkdir -p functions/rndis.usb0
ln -sf functions/rndis.usb0 configs/c.1/

# Bind to UDC
UDC=$(ls /sys/class/udc | head -n1)
if [[ -z "$UDC" ]]; then
  echo "No UDC found; ensure dwc2 overlay is enabled and rebooted." >&2
  exit 1
fi

echo "$UDC" > UDC

echo "USB gadget configured and bound to $UDC"
