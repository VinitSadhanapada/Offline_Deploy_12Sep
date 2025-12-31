# SSH Access & Remote Management

Complete guide for accessing your Raspberry Pi meter system remotely via SSH.

---

## Table of Contents
- [Network Configuration](#network-configuration)
- [SSH Connection Methods](#ssh-connection-methods)
- [Terminal UI Usage](#terminal-ui-usage)
- [File Download Methods](#file-download-methods)
- [WiFi Access Point Control](#wifi-access-point-control)
- [Troubleshooting](#troubleshooting)

---

## Network Configuration

The system supports multiple network access methods:

### Ethernet Static IP (Recommended for Laptop Access)

**Default Static IP:** `192.168.137.100/24`

**Setup during installation:**
```bash
sudo ./setup_launchers/setup_static_ethernet.sh
```

**Manual laptop network configuration:**
- IP Address: `192.168.137.10` (any IP in range except .100)
- Subnet Mask: `255.255.255.0`
- Gateway: `192.168.137.100` (the Pi)

**Connect:**
```bash
ssh pi@192.168.137.100
```

### WiFi Access Point Mode

**Default AP Settings:**
- SSID: `SimpleMeter-<hostname>`
- Password: `iotlabsdev`
- IP Address: `192.168.4.1`

**Connect:**
1. Connect laptop WiFi to the SimpleMeter network
2. SSH to Pi:
   ```bash
   ssh pi@192.168.4.1
   ```

**Enable/Disable AP:**
```bash
# Enable
sudo systemctl start usb_ap.service

# Disable
sudo systemctl stop usb_ap.service

# Enable auto-start on boot
sudo systemctl enable usb_ap.service
```

### Local Network (DHCP)

If Pi is connected to your local network:

**Find IP address:**
```bash
# Method 1: From Pi (if you have console access)
hostname -I

# Method 2: From laptop - scan network
sudo nmap -sn 192.168.1.0/24

# Method 3: Check router DHCP leases
# Access your router web interface (usually 192.168.1.1)

# Method 4: Use hostname (if mDNS/Avahi enabled)
ping raspberrypi.local
```

**Connect:**
```bash
ssh pi@<PI_IP_ADDRESS>
# or
ssh pi@raspberrypi.local
```

---

## SSH Connection Methods

### Basic SSH Connection

```bash
ssh pi@<IP_ADDRESS>
```

Default password: `raspberry` (change immediately!)

**Example:**
```bash
# Via Ethernet static IP
ssh pi@192.168.137.100

# Via WiFi AP
ssh pi@192.168.4.1

# Via local network
ssh pi@192.168.1.100
```

### Change Default Password

**First login:**
```bash
passwd
```

### SSH Key Authentication (Recommended)

**On your laptop, generate key:**
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

**Copy key to Pi:**
```bash
ssh-copy-id pi@192.168.137.100
```

**Now connect without password:**
```bash
ssh pi@192.168.137.100
```

### One-Command Launch Terminal UI

```bash
ssh -t pi@192.168.137.100 "cd ~/Desktop/offline-setup-12Sep && sudo bash terminal_ui.sh"
```

### X11 Forwarding (Desktop GUI over SSH)

**On laptop, enable X11:**
```bash
ssh -X pi@192.168.137.100
```

**Launch desktop UI:**
```bash
cd ~/Desktop/offline-setup-12Sep
python3 simple_meter_ui.py
```

---

## Terminal UI Usage

### Launch Terminal UI

```bash
# Method 1: Via launcher script
cd ~/Desktop/offline-setup-12Sep
sudo bash terminal_ui.sh

# Method 2: Direct Python
python3 terminal_meter_ui.py

# Method 3: Via quick setup menu
./setup_launchers/quick_setup.sh
# Select option 2
```

### Terminal UI Features

**Main Menu Options:**
1. **Live Meter Readings** - Real-time data from all meters
2. **Export CSV Data** - Prepare files with download commands
3. **View Latest Readings** - Quick snapshot
4. **System Status** - Disk space, services, logs
5. **View Configuration** - Config files and device setup
6. **Start Manual Reading** - Trigger one-time read
7. **View Logs** - Recent entries with color coding
8. **Help & Info** - SSH download instructions
9. **WiFi AP Control** - Enable/disable Access Point
Q. **Quit** - Exit to terminal

**Navigation:**
- `↑/↓` - Navigate menu
- `ENTER` - Select
- `1-9` - Quick select
- `Q` - Quit
- `B` - Back (in sub-menus)
- `R` - Refresh (in live view)

For detailed Terminal UI guide, see [TERMINAL_UI.md](TERMINAL_UI.md)

---

## File Download Methods

### Method 1: SCP (Recommended)

**Download all CSV files:**
```bash
# From your laptop (not in SSH session)
scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./meter_data/
```

**Download specific file:**
```bash
scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/csv/readings_all.csv ./
```

**Download entire data folder:**
```bash
scp -r pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data ./pi_meter_data/
```

**Download logs:**
```bash
scp -r pi@192.168.137.100:~/Desktop/offline-setup-12Sep/logs ./pi_logs/
```

### Method 2: RSYNC (Better for large files)

**Sync data folder:**
```bash
rsync -avz --progress pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/ ./meter_data/
```

**Sync only new/modified files:**
```bash
rsync -avz --progress --update pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/csv/ ./csv_backup/
```

### Method 3: Terminal UI Export Feature

1. Launch Terminal UI via SSH
2. Select option **2** (Export CSV Data)
3. Terminal will show exact SCP command with your Pi's IP
4. Exit UI with `Q`
5. Exit SSH with `exit`
6. Paste the SCP command in your laptop terminal

**Example output:**
```
Files exported to: /home/pi/Desktop/offline-setup-12Sep/exports/

To download from your laptop, run:
scp -r pi@192.168.137.100:~/Desktop/offline-setup-12Sep/exports/*.csv ./
```

### Method 4: Helper Script

Use the included download script:

**On your laptop:**
```bash
# Download the script first (one-time)
scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/download_meter_data.sh ./

# Make it executable
chmod +x download_meter_data.sh

# Run it
./download_meter_data.sh 192.168.137.100
```

### Method 5: USB Auto-Copy

**Enable USB download server:**
```bash
sudo systemctl enable --now usb-download-server
```

**Usage:**
1. Insert USB drive into Pi
2. Server automatically copies CSV files to USB
3. Safely remove USB drive

See [DATA_EXPORT.md](DATA_EXPORT.md) for more details.

---

## WiFi Access Point Control

### Via Terminal UI

1. Launch Terminal UI
2. Select option **9** (WiFi AP Control)
3. Choose action:
   - **[1]** Start AP (one-time)
   - **[2]** Stop AP (one-time)
   - **[3]** Enable AP auto-start on boot
   - **[4]** Disable AP auto-start

### Via Command Line

**Start AP:**
```bash
sudo systemctl start usb_ap.service
```

**Stop AP:**
```bash
sudo systemctl stop usb_ap.service
```

**Enable auto-start:**
```bash
sudo systemctl enable usb_ap.service
```

**Disable auto-start:**
```bash
sudo systemctl disable usb_ap.service
```

**Check status:**
```bash
systemctl status usb_ap.service
```

### Change AP Password

Edit configuration file:
```bash
sudo nano /etc/hostapd/hostapd.conf
```

Find and change:
```
wpa_passphrase=iotlabsdev
```

Restart AP:
```bash
sudo systemctl restart usb_ap.service
```

---

## Troubleshooting

### Can't Connect via SSH

**1. Check if SSH is enabled:**
```bash
# On Pi (if you have console access)
sudo systemctl status ssh
sudo systemctl enable ssh
sudo systemctl start ssh
```

**2. Check firewall:**
```bash
sudo ufw status
sudo ufw allow ssh
```

**3. Verify network connection:**
```bash
# From laptop
ping 192.168.137.100
```

**4. Check SSH port:**
```bash
# Default port 22
telnet 192.168.137.100 22
```

### Connection Refused

**Check SSH service:**
```bash
sudo systemctl restart ssh
```

**Check sshd config:**
```bash
sudo nano /etc/ssh/sshd_config
# Ensure: PermitRootLogin no, PasswordAuthentication yes
sudo systemctl restart ssh
```

### Ethernet Not Working

**Check cable connection:**
```bash
# On Pi
ip link show eth0
# Should show "state UP"
```

**Reconfigure static IP:**
```bash
sudo ./setup_launchers/setup_static_ethernet.sh
```

**Check NetworkManager:**
```bash
nmcli device status
nmcli connection show
```

### WiFi AP Not Starting

**Check service status:**
```bash
systemctl status usb_ap.service -l
```

**Check hostapd:**
```bash
sudo systemctl status hostapd
```

**Check logs:**
```bash
sudo journalctl -u usb_ap.service -n 50
```

**Restart AP:**
```bash
sudo systemctl restart usb_ap.service
```

### Slow File Transfer

**Use compression with SCP:**
```bash
scp -C pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./
```

**Or use rsync:**
```bash
rsync -avz --progress pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/ ./
```

### Permission Denied

**Check file permissions on Pi:**
```bash
ls -l ~/Desktop/offline-setup-12Sep/data/csv/
```

**Fix permissions:**
```bash
chmod 644 ~/Desktop/offline-setup-12Sep/data/csv/*.csv
```

---

## Quick Reference Commands

### Connection
```bash
# Ethernet
ssh pi@192.168.137.100

# WiFi AP
ssh pi@192.168.4.1

# With key
ssh -i ~/.ssh/id_ed25519 pi@192.168.137.100

# X11 forwarding
ssh -X pi@192.168.137.100
```

### File Transfer
```bash
# Download CSV
scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./

# Upload file
scp myfile.txt pi@192.168.137.100:~/Desktop/

# Sync folder
rsync -avz pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/ ./backup/
```

### WiFi AP
```bash
# Start
sudo systemctl start usb_ap.service

# Stop
sudo systemctl stop usb_ap.service

# Status
systemctl status usb_ap.service
```

### System
```bash
# Reboot
sudo reboot

# Shutdown
sudo shutdown now

# Disk space
df -h

# Service status
systemctl status meter-dashboard
```

---

## Security Recommendations

1. **Change default password immediately**
   ```bash
   passwd
   ```

2. **Use SSH keys instead of passwords**
   ```bash
   ssh-keygen -t ed25519
   ssh-copy-id pi@192.168.137.100
   ```

3. **Disable password authentication (after setting up keys)**
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart ssh
   ```

4. **Change default WiFi AP password**
   ```bash
   sudo nano /etc/hostapd/hostapd.conf
   ```

5. **Keep system updated**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

6. **Monitor failed login attempts**
   ```bash
   sudo journalctl -u ssh -n 50
   ```

---

**Last Updated:** 31 December 2025  
**See Also:**
- [TERMINAL_UI.md](TERMINAL_UI.md) - Terminal UI detailed guide
- [DATA_EXPORT.md](DATA_EXPORT.md) - Data export methods
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
