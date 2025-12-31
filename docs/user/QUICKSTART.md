# Quick Start Guide
## Raspberry Pi Meter Monitoring System

This guide will get you up and running quickly with the meter monitoring system.

---

## Prerequisites

- Raspberry Pi (any model with USB port)
- Raspberry Pi OS (Bullseye or Bookworm)
- RS485-to-USB converter
- Elmeasure energy meters (LG6400, LG5310, EN8410, etc.)
- Network access (for initial setup)

---

## Installation Methods

Choose the method that fits your situation:

### Method 1: Fresh Raspberry Pi Installation (Recommended)

**Best for:** New deployments, clean installations

1. **Clone the repository:**
   ```bash
   cd ~/Desktop
   git clone https://github.com/VinitSadhanapada/Offline_Deploy_12Sep.git offline-setup-12Sep
   cd offline-setup-12Sep
   ```

2. **Run automated setup:**
   ```bash
   sudo bash scripts/setup/master_setup.sh
   ```
   
   Or use the test framework (validates everything):
   ```bash
   sudo bash test_complete_setup.sh
   ```

3. **Follow the prompts** to configure:
   - Python 3.13 environment
   - Static Ethernet IP (192.168.137.100)
   - Dashboard auto-start service
   - WiFi Access Point (optional)
   - USB download server (optional)

**⏱ Time:** 15-20 minutes  
**See also:** [Fresh Pi Setup Guide](../deployment/FRESH_PI_SETUP.md)

---

### Method 2: Desktop GUI Setup

**Best for:** When you have monitor, keyboard, mouse connected

1. **Navigate to the project folder:**
   - Open File Manager → Desktop → `offline-setup-12Sep`

2. **Run setup (first time):**
   - Double-click **`SimpleMeterUI_Admin.desktop`** in `setup_launchers/`
   - This automatically sets up Python environment and dependencies

3. **Launch the application:**
   - Double-click **`SimpleMeterUI_Admin.desktop`** again
   - Configure your meters in the GUI
   - Start data logging

**⏱ Time:** 5-10 minutes  
**See also:** [Desktop UI Guide](DESKTOP_UI.md)

---

### Method 3: SSH/Terminal Access

**Best for:** Remote access, headless operation, field deployment

1. **Connect via SSH:**
   ```bash
   # Via Ethernet (if static IP configured)
   ssh pi@192.168.137.100
   
   # Or via WiFi AP mode
   ssh pi@192.168.4.1
   ```

2. **Launch interactive menu:**
   ```bash
   cd ~/Desktop/offline-setup-12Sep
   ./scripts/setup/quick_setup.sh
   ```
   
   Select options:
   - **1** - Complete system setup
   - **2** - Terminal UI (view live data)
   - **4** - System status
   - **9** - WiFi AP control

3. **Or launch Terminal UI directly:**
   ```bash
   sudo bash terminal_ui.sh
   ```

**⏱ Time:** 5 minutes  
**See also:** [SSH Access Guide](SSH_ACCESS.md) | [Terminal UI Guide](TERMINAL_UI.md)

---

## First Run

### Desktop UI (Graphical)

1. **Launch application:**
   - Double-click `SimpleMeterUI_Admin.desktop`

2. **Configure meters:**
   - Click "Configure Devices"
   - Add each meter (Name, Model, Modbus Address)
   - Select parameters to monitor

3. **Start monitoring:**
   - Click "Start Dashboard"
   - Data logs to `data/csv/readings_all.csv`

4. **View data:**
   - Real-time display in GUI
   - Export CSV files
   - USB auto-copy (if configured)

---

### Terminal UI (SSH/Headless)

1. **Launch Terminal UI:**
   ```bash
   sudo bash terminal_ui.sh
   ```

2. **Navigate menu:**
   - Use arrow keys ↑/↓ to navigate
   - Press ENTER to select
   - Press Q to quit

3. **Key features:**
   - **1** - Live meter readings
   - **2** - Export CSV data
   - **3** - View latest readings
   - **4** - System status
   - **8** - SSH download instructions
   - **9** - WiFi AP control

4. **Download data via SSH:**
   ```bash
   # From your laptop
   scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./
   ```

---

## Verification

### Check Installation Success

**Desktop Method:**
- GUI opens without errors
- "Configure Devices" button works
- Dashboard shows reading cycles

**Terminal Method:**
```bash
# Check service status
systemctl status meter-dashboard

# View recent logs
tail -f ~/Desktop/offline-setup-12Sep/logs/*.log

# Check data files
ls -lh ~/Desktop/offline-setup-12Sep/data/csv/
```

### Expected Behavior

✅ **Dashboard service running** (if auto-start enabled)  
✅ **CSV files** created in `data/csv/`  
✅ **Logs** appearing in `logs/`  
✅ **Network access** via static IP (192.168.137.100)  
✅ **WiFi AP** broadcasting (if enabled)  

---

## Network Access

### Ethernet Static IP

**Default configuration:**
- IP Address: `192.168.137.100`
- Netmask: `255.255.255.0`
- Gateway: `192.168.137.1`

**Configure during setup** or run manually:
```bash
sudo ./scripts/setup/setup_static_ethernet.sh
```

**Connect from laptop:**
1. Set laptop Ethernet to `192.168.137.1/24`
2. SSH: `ssh pi@192.168.137.100`
3. Web access (if server enabled): `http://192.168.137.100:8080`

---

### WiFi Access Point

**Default configuration:**
- SSID: `SimpleMeter-Data`
- Password: `meter12345`
- IP Address: `192.168.4.1`

**Connect from phone/laptop:**
1. Join WiFi network `SimpleMeter-Data`
2. SSH: `ssh pi@192.168.4.1`
3. Download files via web interface

**Control AP from Terminal UI:**
- Option **9** - WiFi AP Control
- Start/stop AP service
- Enable/disable auto-start

---

## Meter Configuration

### Supported Models

- **LG6400** - Full-featured power meter
- **LG5310** - Standard energy meter
- **LG5220** - Basic energy meter
- **EN8410** - Industrial meter
- **EN8100** - Entry-level meter
- **iELR300** - Relay meter

### Configuration Files

**Main config:** `config/config.json`
```json
{
  "simulation_mode": false,
  "auto_start": true,
  "reading_interval": 60,
  "csv_dir": "data/csv",
  "log_dir": "logs"
}
```

**Device config:** `config/device_config.json`
```json
{
  "devices": [
    {
      "name": "Main Meter",
      "model": "LG6400",
      "address": 1,
      "parameters": ["Voltage", "Current", "Power", "Energy"]
    }
  ]
}
```

**Edit via GUI:** Use Desktop UI's "Configure Devices" button  
**Edit manually:** Use text editor or `nano config/device_config.json`

---

## Data Management

### CSV File Location

**Primary file:** `data/csv/readings_all.csv`  
**Site-specific:** `data/csv/SiteName_YYYY-MM-DD.csv`

### File Format

```csv
Timestamp,Device,Voltage,Current,Power,Energy
2025-12-31 14:30:00,Main Meter,230.5,5.2,1198.6,1234.5
```

### Export Methods

1. **Terminal UI Export:**
   - Option **2** - Export CSV Data
   - Copies to `exports/` folder
   - Shows SSH download commands

2. **SSH Download:**
   ```bash
   # All CSV files
   scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./
   
   # Specific date
   scp pi@192.168.137.100:~/Desktop/offline-setup-12Sep/data/csv/*2025-12-31*.csv ./
   ```

3. **USB Auto-Copy:**
   - Insert USB drive
   - Files auto-copy to `/media/pi/USB_NAME/meter_data/`

**See also:** [Data Export Guide](DATA_EXPORT.md)

---

## Troubleshooting

### Common Issues

**Problem:** Dashboard doesn't start  
**Solution:** 
```bash
# Check service status
systemctl status meter-dashboard

# View logs
tail -100 ~/Desktop/offline-setup-12Sep/logs/*.log

# Restart service
sudo systemctl restart meter-dashboard
```

**Problem:** No meter readings  
**Solution:**
- Check USB-RS485 connection: `ls /dev/ttyUSB*`
- Verify meter addresses in `config/device_config.json`
- Check Modbus communication in logs
- Try simulation mode first

**Problem:** Cannot SSH connect  
**Solution:**
- Check Ethernet cable connected
- Verify laptop IP: `192.168.137.1/24`
- Ping Pi: `ping 192.168.137.100`
- Check SSH enabled: `sudo systemctl status ssh`

**Problem:** WiFi AP not broadcasting  
**Solution:**
```bash
# Check AP service
systemctl status usb_ap.service

# Restart AP
sudo systemctl restart usb_ap.service

# Check network interface
ip addr show wlan0
```

**For more issues:** See [Troubleshooting Guide](TROUBLESHOOTING.md)

---

## Next Steps

### After Installation

1. **Configure meters** - Add all devices in config
2. **Test readings** - Verify data logging works
3. **Set up auto-start** - Enable systemd service
4. **Configure network** - Static IP and/or WiFi AP
5. **Test remote access** - SSH and file download
6. **Schedule backups** - USB or cloud sync

### Learn More

- **[SSH Access Guide](SSH_ACCESS.md)** - Remote access details
- **[Terminal UI Guide](TERMINAL_UI.md)** - Full Terminal UI reference
- **[Desktop UI Guide](DESKTOP_UI.md)** - GUI application guide
- **[Data Export Guide](DATA_EXPORT.md)** - CSV download methods
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common problems

### For Developers

- **[Architecture](../developer/ARCHITECTURE.md)** - System design
- **[Code Structure](../developer/CODE_STRUCTURE.md)** - Module organization
- **[Meter Drivers](../developer/METER_DRIVERS.md)** - Driver development

---

## Support

**Documentation:** `docs/` directory  
**Testing:** `sudo bash test_complete_setup.sh`  
**Logs:** `logs/` directory  
**Configuration:** `config/` directory

**Repository:** https://github.com/VinitSadhanapada/Offline_Deploy_12Sep

---

**Last Updated:** 31 December 2025  
**Version:** 2.0.0
