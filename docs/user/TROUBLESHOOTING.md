# Troubleshooting Guide
## Raspberry Pi Meter Monitoring System

Common issues and solutions for the meter monitoring system.

---

## Installation Issues

### Git Clone Fails

**Symptoms:**
```
fatal: could not create work tree dir 'offline-setup-12Sep': Permission denied
```

**Solution:**
```bash
# Ensure you're in home directory
cd ~/Desktop

# Check permissions
ls -ld ~/Desktop

# If needed, fix permissions
chmod 755 ~/Desktop

# Retry clone
git clone https://github.com/VinitSadhanapada/Offline_Deploy_12Sep.git offline-setup-12Sep
```

---

### Setup Script Permission Denied

**Symptoms:**
```
bash: ./master_setup.sh: Permission denied
```

**Solution:**
```bash
cd ~/Desktop/offline-setup-12Sep

# Make all scripts executable
chmod +x scripts/setup/*.sh
chmod +x *.sh

# Retry
sudo bash scripts/setup/master_setup.sh
```

---

### Python Version Mismatch

**Symptoms:**
```
ERROR: Python 3.13 not found
```

**Solution:**
```bash
# Check current Python version
python3 --version

# Install Python 3.13 (if needed)
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev

# Or run offline installer
bash one_click_system_py313.sh
```

---

### Package Installation Fails

**Symptoms:**
```
ERROR: Could not find a version that satisfies the requirement pymodbus
```

**Solution:**
```bash
# Use offline packages
cd ~/Desktop/offline-setup-12Sep
source venv/bin/activate

# Install from packages_folder
pip install --no-index --find-links=packages_folder/ -r requirements.txt

# Or reinstall specific package
pip install --no-index --find-links=packages_folder/ pymodbus==3.11.3
```

---

## Network Connection Problems

### Cannot SSH to Pi

**Symptoms:**
```
ssh: connect to host 192.168.137.100 port 22: No route to host
```

**Diagnosis:**
```bash
# On Pi - check SSH service
sudo systemctl status ssh

# Check network interface
ip addr show eth0

# Check if static IP applied
ip addr | grep 192.168.137.100
```

**Solution:**

1. **Verify Ethernet cable connected**
2. **Set laptop Ethernet IP:**
   ```bash
   # Linux/Mac
   sudo ifconfig eth0 192.168.137.1 netmask 255.255.255.0
   
   # Or use NetworkManager
   nmcli con mod "Wired connection 1" ipv4.addresses 192.168.137.1/24
   nmcli con mod "Wired connection 1" ipv4.method manual
   nmcli con up "Wired connection 1"
   ```

3. **Test connectivity:**
   ```bash
   ping 192.168.137.100
   ```

4. **If still failing, reconfigure static IP on Pi:**
   ```bash
   sudo bash scripts/setup/setup_static_ethernet.sh
   ```

---

### Static IP Not Applied

**Symptoms:**
- `ip addr` doesn't show 192.168.137.100
- Cannot ping Pi from laptop

**Diagnosis:**
```bash
# Check which network manager is running
systemctl is-active NetworkManager
systemctl is-active dhcpcd

# Check eth0 configuration
ip addr show eth0
```

**Solution for NetworkManager:**
```bash
# Create connection
sudo nmcli con add type ethernet ifname eth0 con-name eth0-static \
  ipv4.method manual \
  ipv4.addresses 192.168.137.100/24 \
  ipv4.gateway 192.168.137.1

# Activate
sudo nmcli con up eth0-static
```

**Solution for dhcpcd:**
```bash
# Edit dhcpcd.conf
sudo nano /etc/dhcpcd.conf

# Add these lines:
# interface eth0
# static ip_address=192.168.137.100/24
# static routers=192.168.137.1

# Restart service
sudo systemctl restart dhcpcd
```

---

### WiFi AP Not Broadcasting

**Symptoms:**
- Cannot see `SimpleMeter-Data` WiFi network
- wlan0 interface down

**Diagnosis:**
```bash
# Check AP service status
systemctl status usb_ap.service

# Check wlan0 interface
ip addr show wlan0

# Check hostapd logs
journalctl -u usb_ap.service -n 50
```

**Solution:**
```bash
# Restart AP service
sudo systemctl restart usb_ap.service

# If still failing, check hostapd directly
sudo hostapd -dd /etc/hostapd/hostapd.conf

# Verify AP configuration
cat ~/Desktop/offline-setup-12Sep/usb_download_mvp/hostapd.conf

# Reinstall AP service
cd ~/Desktop/offline-setup-12Sep/usb_download_mvp
sudo bash scripts/install_service.sh
```

---

### WiFi AP and Ethernet Conflict

**Symptoms:**
- Can't use both Ethernet and WiFi AP simultaneously
- One interface stops working

**Diagnosis:**
```bash
# Check both interfaces
ip addr show eth0
ip addr show wlan0

# Check routing table
ip route
```

**Solution:**
- **Ethernet (eth0)** and **WiFi AP (wlan0)** can coexist
- They use different subnets:
  - eth0: 192.168.137.0/24
  - wlan0: 192.168.4.0/24
- No routing conflict should occur

```bash
# If issues persist, restart networking
sudo systemctl restart NetworkManager
# or
sudo systemctl restart dhcpcd

# Restart AP
sudo systemctl restart usb_ap.service
```

---

## Meter Communication Errors

### No Meter Readings

**Symptoms:**
- Dashboard shows "0" or "N/A" for all readings
- CSV file empty or missing data

**Diagnosis:**
```bash
# Check USB-RS485 device
ls -l /dev/ttyUSB*

# Should show: /dev/ttyUSB0 or /dev/ttyUSB1

# Check permissions
ls -l /dev/ttyUSB0

# Check dashboard logs
tail -100 ~/Desktop/offline-setup-12Sep/logs/*.log

# Look for errors like:
# - "Cannot open serial port"
# - "Modbus exception"
# - "No response from device"
```

**Solution:**

1. **Verify USB-RS485 connected:**
   ```bash
   lsusb
   # Should show CH340 or similar USB serial adapter
   ```

2. **Check user permissions:**
   ```bash
   # Add user to dialout group
   sudo usermod -a -G dialout $USER
   
   # Logout and login for group to take effect
   ```

3. **Test in simulation mode first:**
   ```bash
   # Edit config.json
   nano config/config.json
   
   # Set: "simulation_mode": true
   
   # Restart dashboard
   sudo systemctl restart meter-dashboard
   ```

4. **Verify meter addresses:**
   ```bash
   nano config/device_config.json
   
   # Check "address" field matches physical meter settings
   # Common addresses: 1, 2, 3, ...
   ```

---

### Modbus Communication Timeout

**Symptoms:**
- Logs show: "Received ModbusException from library"
- Intermittent readings

**Diagnosis:**
```bash
# Check serial port settings
stty -F /dev/ttyUSB0

# Should show: 9600 baud (or 19200 depending on meter)
```

**Solution:**

1. **Verify baud rate matches meter:**
   - Most Elmeasure meters: 9600 baud
   - Some models: 19200 baud

2. **Check RS485 wiring:**
   - A terminal → A terminal (all meters + USB adapter)
   - B terminal → B terminal (all meters + USB adapter)
   - Proper grounding
   - Termination resistor (120Ω) at ends of cable

3. **Reduce polling frequency:**
   ```bash
   nano config/config.json
   
   # Increase reading_interval from 60 to 120 seconds
   "reading_interval": 120
   ```

4. **Check cable length:**
   - RS485 max distance: ~1200 meters
   - Use twisted pair cable
   - Avoid running parallel to power cables

---

### Wrong Parameter Values

**Symptoms:**
- Values seem incorrect (e.g., voltage = 9999.9)
- Negative values where positive expected

**Diagnosis:**
```bash
# Check meter model in configuration
nano config/device_config.json

# Verify model matches physical meter label
# - LG6400, LG5310, EN8410, etc.
```

**Solution:**

1. **Verify meter model correct:**
   - Each meter model has different register mappings
   - Wrong model = wrong register addresses

2. **Check parameter names:**
   ```json
   // Valid parameters depend on meter model
   "parameters": [
     "Voltage",      // ✓ Valid
     "Current",      // ✓ Valid
     "Volt",         // ✗ Invalid - should be "Voltage"
   ]
   ```

3. **Review meter manual:**
   - Confirm supported parameters
   - Check units (V, A, kW, kWh)
   - Verify decimal places

4. **Enable debug logging:**
   ```bash
   # Check logs for raw register values
   tail -f ~/Desktop/offline-setup-12Sep/logs/*.log | grep "register"
   ```

---

## Dashboard Service Issues

### Service Won't Start

**Symptoms:**
```
Failed to start meter-dashboard.service
```

**Diagnosis:**
```bash
# Check service status
systemctl status meter-dashboard

# View full logs
journalctl -u meter-dashboard -n 100

# Check service file
cat /etc/systemd/system/meter-dashboard.service
```

**Solution:**

1. **Check Python path:**
   ```bash
   # Service file should use correct venv
   grep ExecStart /etc/systemd/system/meter-dashboard.service
   
   # Should show:
   # ExecStart=/home/pi/Desktop/offline-setup-12Sep/venv/bin/python3 ...
   ```

2. **Verify file permissions:**
   ```bash
   ls -l ~/Desktop/offline-setup-12Sep/simple_rpi_dashboard.py
   
   # Should be readable
   chmod 644 ~/Desktop/offline-setup-12Sep/simple_rpi_dashboard.py
   ```

3. **Test manual start:**
   ```bash
   cd ~/Desktop/offline-setup-12Sep
   source venv/bin/activate
   python3 simple_rpi_dashboard.py
   
   # If error, fix issue before enabling service
   ```

4. **Reinstall service:**
   ```bash
   sudo bash scripts/setup/enable_auto_start.sh
   ```

---

### Service Crashes Repeatedly

**Symptoms:**
- Service status shows "failed"
- Logs show crash loop

**Diagnosis:**
```bash
# Check crash logs
journalctl -u meter-dashboard --since "1 hour ago"

# Look for:
# - Import errors
# - Permission denied
# - File not found
# - Configuration errors
```

**Solution:**

1. **Check dependencies:**
   ```bash
   source venv/bin/activate
   pip list
   
   # Reinstall if needed
   pip install -r requirements.txt
   ```

2. **Verify configuration files:**
   ```bash
   # Test JSON syntax
   python3 -m json.tool config/config.json
   python3 -m json.tool config/device_config.json
   ```

3. **Check disk space:**
   ```bash
   df -h
   
   # If full, clean old logs/data
   find logs/ -name "*.log" -mtime +30 -delete
   find data/csv/ -name "*.csv" -mtime +90 -delete
   ```

4. **Disable auto-restart temporarily:**
   ```bash
   sudo systemctl stop meter-dashboard
   
   # Run manually to see error
   sudo python3 ~/Desktop/offline-setup-12Sep/simple_rpi_dashboard.py
   ```

---

## Data & Logging Issues

### CSV Files Not Created

**Symptoms:**
- `data/csv/` directory empty
- No readings_all.csv file

**Diagnosis:**
```bash
# Check directory exists
ls -ld ~/Desktop/offline-setup-12Sep/data/csv/

# Check permissions
ls -l ~/Desktop/offline-setup-12Sep/data/

# Check if dashboard is running
systemctl status meter-dashboard
```

**Solution:**

1. **Create directories:**
   ```bash
   mkdir -p ~/Desktop/offline-setup-12Sep/data/csv
   chmod 755 ~/Desktop/offline-setup-12Sep/data/csv
   ```

2. **Check config.json:**
   ```bash
   nano config/config.json
   
   # Verify:
   "csv_dir": "data/csv"
   ```

3. **Test write permissions:**
   ```bash
   touch ~/Desktop/offline-setup-12Sep/data/csv/test.csv
   
   # If fails, fix permissions
   sudo chown -R $USER:$USER ~/Desktop/offline-setup-12Sep/data
   ```

---

### Log Files Too Large

**Symptoms:**
- Disk space warning
- Logs directory > 1GB

**Diagnosis:**
```bash
# Check log sizes
du -sh ~/Desktop/offline-setup-12Sep/logs/*

# Find largest files
du -h ~/Desktop/offline-setup-12Sep/logs/* | sort -rh | head -10
```

**Solution:**

1. **Manual cleanup:**
   ```bash
   # Delete old logs (>30 days)
   find ~/Desktop/offline-setup-12Sep/logs/ -name "*.log" -mtime +30 -delete
   
   # Compress old logs
   find ~/Desktop/offline-setup-12Sep/logs/ -name "*.log" -mtime +7 -exec gzip {} \;
   ```

2. **Set up logrotate:**
   ```bash
   sudo nano /etc/logrotate.d/meter-dashboard
   
   # Add:
   /home/pi/Desktop/offline-setup-12Sep/logs/*.log {
       weekly
       rotate 4
       compress
       delaycompress
       missingok
       notifempty
   }
   ```

3. **Reduce logging verbosity:**
   ```bash
   nano simple_rpi_dashboard.py
   
   # Change logging level:
   # logging.basicConfig(level=logging.INFO)  # Instead of DEBUG
   ```

---

### CSV Export Fails

**Symptoms:**
- Terminal UI export shows errors
- SCP download fails

**Diagnosis:**
```bash
# Check exports directory
ls -ld ~/Desktop/offline-setup-12Sep/exports/

# Check available CSV files
ls -lh ~/Desktop/offline-setup-12Sep/data/csv/

# Test SCP manually
scp ~/Desktop/offline-setup-12Sep/data/csv/readings_all.csv user@laptop:/tmp/
```

**Solution:**

1. **Create exports directory:**
   ```bash
   mkdir -p ~/Desktop/offline-setup-12Sep/exports
   chmod 755 ~/Desktop/offline-setup-12Sep/exports
   ```

2. **Check SSH keys (if using):**
   ```bash
   ls -l ~/.ssh/
   
   # Ensure proper permissions
   chmod 700 ~/.ssh
   chmod 600 ~/.ssh/id_rsa
   chmod 644 ~/.ssh/id_rsa.pub
   ```

3. **Test network connectivity:**
   ```bash
   # From laptop
   ping 192.168.137.100
   
   # Test SSH
   ssh pi@192.168.137.100 ls -l
   ```

---

## USB Auto-Copy Issues

### USB Drive Not Detected

**Symptoms:**
- Insert USB, no auto-copy occurs
- `/media/pi/` empty

**Diagnosis:**
```bash
# Check if drive recognized
lsblk

# Check mount points
mount | grep media

# Check udev service
systemctl status systemd-udevd
```

**Solution:**

1. **Manually mount:**
   ```bash
   # Create mount point
   sudo mkdir -p /media/pi/USB
   
   # Mount (replace sdX1 with actual device)
   sudo mount /dev/sda1 /media/pi/USB
   
   # Check if files copied
   ls /media/pi/USB/meter_data/
   ```

2. **Check auto-copy service:**
   ```bash
   systemctl status usb_csv_auto_copy.service
   
   # Restart if needed
   sudo systemctl restart usb_csv_auto_copy.service
   ```

3. **Test USB drive:**
   - Try different USB port
   - Test drive on another computer
   - Format as FAT32 or exFAT

---

## System Performance Issues

### High CPU Usage

**Symptoms:**
- System slow/laggy
- `top` shows python3 using >80% CPU

**Diagnosis:**
```bash
# Check process
top -u pi

# Check reading interval
grep reading_interval config/config.json
```

**Solution:**

1. **Increase reading interval:**
   ```bash
   nano config/config.json
   
   # Change from 60 to 120+ seconds
   "reading_interval": 120
   ```

2. **Reduce number of parameters:**
   ```bash
   nano config/device_config.json
   
   # Monitor only essential parameters
   "parameters": ["Voltage", "Current", "Power"]
   ```

3. **Check for runaway processes:**
   ```bash
   # Kill if needed
   sudo pkill -f simple_rpi_dashboard.py
   
   # Restart service
   sudo systemctl restart meter-dashboard
   ```

---

### Low Memory Warning

**Symptoms:**
- System slow
- `free -h` shows low available memory

**Diagnosis:**
```bash
# Check memory usage
free -h

# Check swap
swapon -s
```

**Solution:**

1. **Increase swap size:**
   ```bash
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile
   
   # Change:
   CONF_SWAPSIZE=2048
   
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

2. **Disable unnecessary services:**
   ```bash
   sudo systemctl disable bluetooth
   sudo systemctl disable avahi-daemon
   ```

3. **Use lighter desktop (if applicable):**
   - Switch to LXDE or console only

---

## Factory Reset / Clean Slate

### Complete Reinstallation

If all else fails, perform clean installation:

```bash
# Backup important data
cp -r ~/Desktop/offline-setup-12Sep/data ~/backup/
cp -r ~/Desktop/offline-setup-12Sep/logs ~/backup/
cp ~/Desktop/offline-setup-12Sep/config/*.json ~/backup/

# Remove installation
rm -rf ~/Desktop/offline-setup-12Sep

# Reclone repository
cd ~/Desktop
git clone https://github.com/VinitSadhanapada/Offline_Deploy_12Sep.git offline-setup-12Sep
cd offline-setup-12Sep

# Run fresh setup
sudo bash scripts/setup/master_setup.sh

# Restore configuration
cp ~/backup/*.json config/

# Restore data (optional)
cp -r ~/backup/data .
```

---

## Getting Help

### Diagnostic Information to Collect

When reporting issues, include:

```bash
# System info
uname -a
cat /etc/os-release

# Python version
python3 --version

# Service status
systemctl status meter-dashboard
systemctl status usb_ap.service

# Network config
ip addr
ip route

# USB devices
lsusb
ls -l /dev/ttyUSB*

# Recent logs
tail -100 ~/Desktop/offline-setup-12Sep/logs/*.log

# Disk space
df -h

# Configuration
cat config/config.json
cat config/device_config.json
```

### Useful Commands Reference

```bash
# Restart everything
sudo systemctl restart meter-dashboard
sudo systemctl restart usb_ap.service
sudo systemctl restart ssh

# View live logs
journalctl -u meter-dashboard -f

# Test network
ping 192.168.137.100
ping 192.168.4.1

# Check services
systemctl --type=service --state=running

# Disk usage
du -sh ~/Desktop/offline-setup-12Sep/*

# Process list
ps aux | grep python

# Network connections
netstat -tuln
```

---

## Related Documentation

- [Quick Start Guide](QUICKSTART.md)
- [SSH Access Guide](SSH_ACCESS.md)
- [Terminal UI Guide](TERMINAL_UI.md)
- [Fresh Pi Setup](../deployment/FRESH_PI_SETUP.md)
- [Network Setup](../deployment/NETWORK_SETUP.md)

---

**Last Updated:** 31 December 2025  
**Version:** 2.0.0
