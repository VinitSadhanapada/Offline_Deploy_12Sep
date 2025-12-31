# SSH Terminal UI Guide

## Overview
This guide explains how to access your Raspberry Pi meter reading system via SSH from a laptop connected via Ethernet, view live data, and download CSV files without needing a desktop environment.

## Connection Setup

### 1. Physical Connection
- Connect your laptop to the Raspberry Pi using an Ethernet cable
- The Pi should be configured with a static IP or DHCP

### 2. Finding the Pi's IP Address

**Option A: If you can briefly connect a monitor to the Pi:**
```bash
hostname -I
```

**Option B: From your laptop, scan the network:**
```bash
# On Linux/Mac
arp -a
# or
nmap -sn 192.168.1.0/24

# On Windows
arp -a
```

**Option C: Common default addresses:**
- If Pi acts as DHCP server: `192.168.4.1`
- Otherwise: Check your router's DHCP leases

### 3. SSH Connection

From your laptop terminal:
```bash
ssh pi@<PI_IP_ADDRESS>
```

Default password is usually `devi` (change this for security!).

**Example:**
```bash
ssh pi@192.168.1.100
```

## Using the Terminal UI

### Quick Start

Once connected via SSH, run:
```bash
cd ~/Desktop/offline-setup-12Sep
python3 terminal_meter_ui.py
```

### Features

The Terminal UI provides:

1. **Live Meter Readings** - View real-time data from all configured meters
2. **Export CSV Data** - Prepare files for easy download with SCP commands shown
3. **View Latest Readings** - Quick snapshot of current values
4. **System Status** - Check disk space, services, and logs
5. **View Configuration** - Display current config and device setup
6. **Start Manual Reading** - Trigger a one-time meter read
7. **View Logs** - Show recent log entries with color coding
8. **Help & Info** - SSH download instructions with your Pi's IP

### Navigation

- **↑/↓ Arrow keys** - Move through menu
- **ENTER** - Select option
- **Number keys (1-8)** - Quick select
- **Q** - Quit to SSH terminal
- **B** - Back to main menu (in sub-screens)
- **R** - Refresh (in live readings)

## Downloading Data via SCP

### Download All CSV Files
```bash
# From your laptop (not in SSH session)
scp pi@<PI_IP>:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./meter_data/
```

### Download Single File
```bash
scp pi@<PI_IP>:~/Desktop/offline-setup-12Sep/data/csv/readings_all.csv ./
```

### Download Entire Data Folder
```bash
scp -r pi@<PI_IP>:~/Desktop/offline-setup-12Sep/data ./pi_meter_data/
```

### Download Logs
```bash
scp -r pi@<PI_IP>:~/Desktop/offline-setup-12Sep/logs ./pi_logs/
```

### Use the Export Feature
The Terminal UI's "Export CSV Data" option (menu #2):
1. Copies all CSV files to an `exports/` directory
2. Shows the exact SCP command with your Pi's IP
3. Makes files ready for quick download

## Alternative: Direct CSV Viewing

### View Live CSV Updates via SSH
```bash
# Connect via SSH, then:
tail -f ~/Desktop/offline-setup-12Sep/data/csv/readings_all.csv
```

Press `Ctrl+C` to stop.

### View Last 50 Lines
```bash
tail -n 50 ~/Desktop/offline-setup-12Sep/data/csv/readings_all.csv
```

### Search for Specific Meter
```bash
grep "MeterName" ~/Desktop/offline-setup-12Sep/data/csv/readings_all.csv | tail -n 10
```

## Troubleshooting

### Can't Connect via SSH

1. **Check if SSH is enabled:**
   ```bash
   # If you have monitor access to Pi:
   sudo systemctl status ssh
   sudo systemctl enable ssh
   sudo systemctl start ssh
   ```

2. **Check firewall (if enabled):**
   ```bash
   sudo ufw allow ssh
   ```

3. **Verify network connection:**
   ```bash
   # From your laptop:
   ping <PI_IP>
   ```

### Terminal UI Issues

**Colors not showing:**
- Your terminal might not support colors
- Try: `export TERM=xterm-256color` before running

**Screen too small:**
- Resize your terminal window to at least 80x24
- Or use: `resize` command

**Crashes on startup:**
- Check Python version: `python3 --version` (needs 3.6+)
- Try running directly: `python3 -m curses`

### Permission Issues

If you get "Permission denied" when downloading:
```bash
# On the Pi, make exports directory accessible:
mkdir -p ~/Desktop/offline-setup-12Sep/exports
chmod 755 ~/Desktop/offline-setup-12Sep/exports
```

## Advanced: Automated Data Sync

### Create a Sync Script on Your Laptop

Save as `sync_meter_data.sh`:
```bash
#!/bin/bash
PI_IP="192.168.1.100"  # Change to your Pi's IP
LOCAL_DIR="./meter_data_$(date +%Y%m%d)"

mkdir -p "$LOCAL_DIR"
scp -r pi@$PI_IP:~/Desktop/offline-setup-12Sep/data/csv/*.csv "$LOCAL_DIR/"

echo "Data synced to: $LOCAL_DIR"
ls -lh "$LOCAL_DIR"
```

Make it executable:
```bash
chmod +x sync_meter_data.sh
./sync_meter_data.sh
```

### Schedule Regular Syncs (Optional)

On your laptop, add to crontab:
```bash
# Sync every hour
0 * * * * /path/to/sync_meter_data.sh >> /path/to/sync.log 2>&1
```

## Quick Reference Card

```
┌─────────────────────────────────────────────────────┐
│  SSH QUICK REFERENCE                                │
├─────────────────────────────────────────────────────┤
│  Connect:       ssh pi@<IP>                         │
│  Run UI:        python3 terminal_meter_ui.py        │
│  View CSV:      tail -f data/csv/readings_all.csv   │
│  Download:      scp pi@<IP>:path/*.csv ./           │
│  Exit SSH:      exit  or  Ctrl+D                    │
│  Exit UI:       Press Q                             │
└─────────────────────────────────────────────────────┘
```

## Security Recommendations

1. **Change default password:**
   ```bash
   passwd
   ```

2. **Use SSH keys instead of passwords:**
   ```bash
   # On your laptop:
   ssh-keygen
   ssh-copy-id pi@<PI_IP>
   ```

3. **Disable password authentication (after setting up keys):**
   ```bash
   # On Pi:
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart ssh
   ```

## Getting Help

- Press **8** in the Terminal UI for help screen
- View system status with option **4**
- Check logs with option **7**
- For MQTT troubleshooting, see `README_MQTT_TROUBLESHOOT.md`

---

**Pro Tip:** Bookmark this command on your laptop:
```bash
alias pi-connect='ssh pi@192.168.1.100'  # Change IP
alias pi-ui='ssh -t pi@192.168.1.100 "cd ~/Desktop/offline-setup-12Sep && python3 terminal_meter_ui.py"'
```

Then just type `pi-ui` to connect and launch the interface in one command!
