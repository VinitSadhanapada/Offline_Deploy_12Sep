#!/usr/bin/env bash
set -euo pipefail

# Create a default AP SSID based on the configured AP gateway IP.
# We prefer a static AP IP as configured in the repo (25-wlan0-ap.network)
# so the SSID is predictable for users. Fallback to 192.168.50.1.

get_ap_ip() {
  # Try to read configured Address= from the systemd network file if present
  cfg="/etc/systemd/network/25-wlan0-ap.network"
  if [[ -f "$cfg" ]]; then
    awk -F= '/^Address=/ {print $2; exit}' "$cfg" | cut -d'/' -f1
    return
  fi
  # Fallback to the canonical AP gateway
  echo "192.168.50.1"
}

AP_IP=$(get_ap_ip)
SSID="Elmeasure_Meter_${AP_IP}"
CONF_DIR=/etc/hostapd
CONF_FILE=${CONF_DIR}/hostapd.conf

sudo mkdir -p "$CONF_DIR"

# Choose a sane channel (1) and country code (IN by default; adjust as needed)
COUNTRY=${WIFI_COUNTRY:-IN}

cat <<EOF | sudo tee "$CONF_FILE" >/dev/null
country_code=${COUNTRY}
interface=wlan0
driver=nl80211
ssid=${SSID}
hw_mode=g
channel=1
auth_algs=1
wmm_enabled=0
wpa=0
ignore_broadcast_ssid=0
EOF

# Ensure hostapd uses this conf
sudo sed -i 's|^#*DAEMON_CONF=.*|DAEMON_CONF=/etc/hostapd/hostapd.conf|' /etc/default/hostapd || true

# Bring down any client connection and start AP

# Allow radio but do not forcibly take down the interface; bringing the
# interface down here made the Pi unreachable over Wi‑Fi. We keep rfkill
# unblock so the radio is available but avoid forcing link state changes.
sudo rfkill unblock wifi || true

sudo systemctl restart hostapd

# Provide a tiny DHCP range via dnsmasq (optional, so phones can see SSID without connecting)
# We only need SSID visible; dnsmasq not strictly required unless connecting.

# Ensure dnsmasq has an AP config so clients receive DHCP leases.
DNS_CONF=/etc/dnsmasq.d/simplemeter-ap.conf
if [ ! -f "$DNS_CONF" ]; then
    cat > /tmp/simplemeter-ap.conf.$$ <<'DNSCONF'
interface=wlan0
bind-interfaces
domain-needed
bogus-priv
dhcp-range=192.168.50.10,192.168.50.200,12h
dhcp-option=3,192.168.50.1
DNSCONF
    sudo mv /tmp/simplemeter-ap.conf.$$ "$DNS_CONF" || true
    sudo systemctl restart dnsmasq || true
fi
