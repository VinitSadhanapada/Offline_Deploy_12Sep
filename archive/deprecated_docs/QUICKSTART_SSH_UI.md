# Quick Start: SSH Terminal UI

## For Field Technicians - 5 Minute Guide

### What You Need
- Laptop with Ethernet port
- Ethernet cable
- Raspberry Pi already installed in the field

### Steps

#### 1. Connect Physically
```
Laptop <--[Ethernet Cable]--> Raspberry Pi
```

#### 2. Find the Pi's IP Address

**Easy method - the Pi should show IP on boot:**
- If you see a monitor briefly: note the IP shown at login
- Common IPs: `192.168.1.100`, `192.168.4.1`, `10.0.0.1`

**Or scan from laptop:**
```bash
# Linux/Mac
arp -a | grep -i "b8:27:eb\|dc:a6:32"  # Raspberry Pi MAC prefixes

# Windows PowerShell
arp -a | findstr "b8-27-eb dc-a6-32"
```

#### 3. Connect via SSH

Open terminal on your laptop:
```bash
ssh pi@<IP_ADDRESS>
# Example: ssh pi@192.168.1.100
```

Default password: `raspberry` (or as configured)

#### 4. Launch Terminal UI

Once connected:
```bash
cd ~/Desktop/offline-setup-12Sep
./terminal_ui.sh
```

Or directly:
```bash
python3 ~/Desktop/offline-setup-12Sep/terminal_meter_ui.py
```

### Using the UI

```
┌─────────────────────────────────────┐
│  Press number or arrow keys         │
│  1 = Live readings                  │
│  2 = Export CSV (shows download cmd)│
│  3 = View latest data               │
│  4 = System status                  │
│  Q = Quit                            │
└─────────────────────────────────────┘
```

### Download Data to Your Laptop

#### Method 1: Use Option 2 in UI
1. In Terminal UI, press `2`
2. Copy the `scp` command shown
3. Exit UI with `Q`
4. Exit SSH with `exit`
5. Paste the scp command in your laptop terminal

#### Method 2: Use Helper Script

Copy the `download_meter_data.sh` script to your laptop, then:
```bash
# On your laptop (not in SSH)
./download_meter_data.sh 192.168.1.100
```

#### Method 3: Direct SCP

```bash
# Download all CSV files
scp pi@192.168.1.100:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./

# Download specific file
scp pi@192.168.1.100:~/Desktop/offline-setup-12Sep/data/csv/readings_all.csv ./
```

### One-Command Quick View

Connect and launch UI in one command:
```bash
ssh -t pi@192.168.1.100 "cd ~/Desktop/offline-setup-12Sep && python3 terminal_meter_ui.py"
```

### Troubleshooting

**Can't connect:**
- Check cable connection
- Try pinging: `ping 192.168.1.100`
- Check if SSH is enabled on Pi
- Verify IP address

**UI doesn't display properly:**
- Resize terminal to 80x24 minimum
- Check terminal supports colors
- Try: `export TERM=xterm-256color`

**No data showing:**
- Check if dashboard is running: Option 4 (System Status)
- Start manual reading: Option 6
- Check logs: Option 7

### Advanced: Save Connection Alias

Add to your `~/.bashrc` or `~/.zshrc` on laptop:
```bash
alias pi-meter='ssh -t pi@192.168.1.100 "cd ~/Desktop/offline-setup-12Sep && python3 terminal_meter_ui.py"'
```

Then just type: `pi-meter`

---

## Complete Workflow Example

```bash
# 1. Connect to Pi
$ ssh pi@192.168.1.100

# 2. Launch UI
pi@raspberrypi:~ $ cd ~/Desktop/offline-setup-12Sep
pi@raspberrypi:~/Desktop/offline-setup-12Sep $ ./terminal_ui.sh

# 3. In UI, press:
#    - 1 to view live readings
#    - 2 to export and get download command
#    - Q to quit

# 4. Exit SSH
pi@raspberrypi:~/Desktop/offline-setup-12Sep $ exit

# 5. Download data (on your laptop)
$ scp pi@192.168.1.100:~/Desktop/offline-setup-12Sep/exports/*.csv ./meter_data/

# Done! Data is now on your laptop in ./meter_data/
```

## Files Reference

**On the Pi:**
- `terminal_meter_ui.py` - Main terminal interface
- `terminal_ui.sh` - Launcher script
- `README_SSH_TERMINAL_UI.md` - Detailed guide
- `data/csv/` - Meter reading CSV files
- `exports/` - Files prepared for download (via UI option 2)
- `logs/` - System and error logs

**For Your Laptop:**
- `download_meter_data.sh` - Interactive download helper
- Copy this from Pi or create from README

## Need More Help?

- Full guide: `README_SSH_TERMINAL_UI.md`
- MQTT issues: `README_MQTT_TROUBLESHOOT.md`
- In UI, press `8` for help screen
