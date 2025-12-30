# End-to-End Testing Guide

Complete testing protocol for validating the setup on a fresh Raspberry Pi.

## 🎯 Testing Objective

Validate that a fresh Raspberry Pi can:
1. Clone/pull this workspace from Git
2. Run complete automated setup
3. Have all services working
4. Access terminal UI via SSH
5. Access desktop UI locally
6. Collect and store meter data

---

## 📋 Pre-Test Requirements

### Fresh Raspberry Pi Checklist
- [ ] Fresh Raspberry Pi OS installation (Bullseye or Bookworm)
- [ ] Python 3.11+ installed (`python3 --version`)
- [ ] Git installed (`git --version`)
- [ ] Internet connection (for initial git clone)
- [ ] sudo access

### Optional Hardware
- [ ] USB-to-RS485 adapter (for meter testing)
- [ ] Elmeasure meter (for full functionality test)
- [ ] Ethernet cable + laptop (for SSH testing)

---

## 🚀 Testing Protocol

### Phase 1: Fresh Install & Clone

**On fresh Raspberry Pi:**

```bash
# 1. Update system (optional but recommended)
sudo apt update

# 2. Ensure git is installed
sudo apt install -y git

# 3. Clone the repository
cd ~/Desktop
git clone <YOUR_GIT_REPO_URL> offline-setup-12Sep
# Or if already exists: cd offline-setup-12Sep && git pull

# 4. Navigate to workspace
cd ~/Desktop/offline-setup-12Sep

# 5. Make test script executable
chmod +x test_complete_setup.sh

# 6. Run comprehensive test
sudo bash test_complete_setup.sh
```

**Expected Outcome:**
- Test script runs all 20 test suites
- Prompts to run `master_setup.sh`
- Reports PASS/WARN/FAIL for each test

---

### Phase 2: Test Results Analysis

The test script will create a detailed log at `/tmp/setup_test_YYYYMMDD_HHMMSS.log`

**Review the log:**
```bash
# View the latest test log
ls -lt /tmp/setup_test_*.log | head -1 | awk '{print $9}' | xargs cat

# Or search for failures
grep "FAIL" /tmp/setup_test_*.log | tail -1
```

**Expected Results:**
- ✓ **0 FAILED** tests (critical)
- ⚠ **Some WARNINGS** acceptable (e.g., no meter connected, services not started yet)
- ✓ **High PASSED** count (50+ tests)

**Common Acceptable Warnings:**
- `readings_all.csv is empty` - normal on fresh install
- `Ethernet has no IP` - normal if cable not connected
- `Service not running` - normal before reboot
- `config.json not found` - created by setup

**Critical Failures (Must Fix):**
- Python modules not installed
- Scripts not executable
- Systemd service files incorrect
- Config files invalid JSON
- Missing core Python files

---

### Phase 3: Post-Setup Validation

After `master_setup.sh` completes successfully:

```bash
# 1. Check service status
sudo systemctl status meter-dashboard
sudo systemctl status usb-download-server

# 2. Check Python venv
source ~/Desktop/offline-setup-12Sep/venv/bin/activate
python3 -c "import pymodbus, paho.mqtt.client, pandas; print('All modules OK')"
deactivate

# 3. Check log files
cat ~/Desktop/offline-setup-12Sep/logs/master_setup_*.log | tail -50

# 4. Verify network config
ip addr show eth0
cat /etc/dhcpcd.conf | grep "192.168.137.2"

# 5. Test terminal UI (without starting)
python3 ~/Desktop/offline-setup-12Sep/terminal_meter_ui.py --help 2>&1 | head -5
# Should show usage or not crash immediately

# 6. Verify symlinks
ls -lh ~/Desktop/offline-setup-12Sep/quick_start
ls -lh ~/Desktop/offline-setup-12Sep/complete_setup
```

---

### Phase 4: Functional Testing

#### Test 1: Terminal UI (SSH Access)

**On Raspberry Pi:**
```bash
# Option A: Direct launch
python3 ~/Desktop/offline-setup-12Sep/terminal_meter_ui.py

# Option B: Via wrapper
bash ~/Desktop/offline-setup-12Sep/terminal_ui.sh
```

**Expected:**
- Curses-based color menu appears
- 9 options displayed (Live Readings, Export Data, etc.)
- Can navigate with arrow keys
- Can exit with 'Q' or '9'

**Common Issues:**
- `Terminal too small` → Resize terminal to 80x24+
- `No readings` → Normal if meter not connected
- `Permission denied` on serial → User not in dialout group, reboot needed

#### Test 2: Desktop UI

**On Raspberry Pi (with desktop):**
```bash
# Option A: Double-click desktop shortcut
# ~/Desktop/SimpleMeterUI_Admin.desktop

# Option B: From terminal
cd ~/Desktop/offline-setup-12Sep
python3 simple_meter_ui.py
```

**Expected:**
- GUI window opens
- Shows system status
- Can view logs/configs
- Can trigger manual reads (if meter connected)

#### Test 3: SSH Access from Laptop

**Connect Ethernet cable: Laptop ↔ Raspberry Pi**

**On Laptop:**
```bash
# 1. Configure laptop Ethernet to static IP
# Windows: Network adapter settings → Manual IP: 192.168.137.1
# Linux: nmcli con mod "Wired connection 1" ipv4.addresses 192.168.137.1/24
# Mac: System Preferences → Network → Ethernet → Manual: 192.168.137.1

# 2. Test connectivity
ping 192.168.137.2

# 3. SSH into Pi
ssh pi@192.168.137.2

# 4. Launch terminal UI
cd ~/Desktop/offline-setup-12Sep
python3 terminal_meter_ui.py
```

**Expected:**
- Can ping Pi at 192.168.137.2
- Can SSH successfully
- Terminal UI works over SSH
- Can download data with download_meter_data.sh

#### Test 4: Auto-Start Service

**On Raspberry Pi:**
```bash
# 1. Enable auto-start
sudo systemctl start meter-dashboard

# 2. Check status
sudo systemctl status meter-dashboard

# 3. Check logs
sudo journalctl -u meter-dashboard -f

# 4. Reboot test
sudo reboot
# Wait for reboot...
# SSH back in
ssh pi@192.168.137.2
sudo systemctl status meter-dashboard
# Should show "active (running)"
```

#### Test 5: Data Collection (If Meter Connected)

**Prerequisites:** USB-RS485 adapter + Elmeasure meter

**On Raspberry Pi:**
```bash
# 1. Check USB adapter
ls -l /dev/ttyUSB* 2>/dev/null || ls -l /dev/ttyACM* 2>/dev/null

# 2. Verify device_config.json has correct port
cat ~/Desktop/offline-setup-12Sep/device_config.json | grep -A5 '"port"'

# 3. Test manual read
cd ~/Desktop/offline-setup-12Sep
source venv/bin/activate
python3 meter_manager.py

# 4. Check CSV output
ls -lh ~/Desktop/offline-setup-12Sep/data/csv/
cat ~/Desktop/offline-setup-12Sep/data/csv/readings_all.csv | tail -5
```

**Expected:**
- Detects serial port (/dev/ttyUSB0 or similar)
- Reads data from meter
- Writes to readings_all.csv
- Creates site-specific CSV files

---

## 🔍 Automated Re-Test After Fixes

If issues are found and fixed, re-run the complete test:

```bash
cd ~/Desktop/offline-setup-12Sep

# 1. Pull latest changes
git pull

# 2. Re-run test suite
sudo bash test_complete_setup.sh

# 3. Compare results
diff /tmp/setup_test_*.log | grep "FAIL"
```

---

## 📊 Test Results Template

Use this template to document test results:

```
==============================================
TEST RUN: [Date/Time]
Raspberry Pi Model: [Pi 4 / Pi 3 / Pi Zero]
OS Version: [Bullseye / Bookworm]
Python Version: [3.11 / 3.13]
==============================================

PHASE 1: Fresh Install
[ ] Git clone successful
[ ] test_complete_setup.sh ran
[ ] master_setup.sh completed

PHASE 2: Test Results
Passed:   [X] / 50+
Warnings: [X]
Failed:   [X]

Critical Failures (if any):
- [List any FAIL results]

PHASE 3: Post-Setup
[ ] Services enabled
[ ] Python venv working
[ ] Network configured
[ ] Symlinks correct

PHASE 4: Functional Tests
[ ] Terminal UI launches
[ ] Desktop UI launches
[ ] SSH access working
[ ] Auto-start service works
[ ] Data collection works (if meter present)

ISSUES FOUND:
1. [Description]
   - Error: [Error message]
   - Fix: [What was changed]
   - Status: [Fixed / Open]

FINAL STATUS: [ PASS / FAIL ]
READY FOR PRODUCTION: [ YES / NO ]

Notes:
[Any additional observations]
```

---

## 🐛 Common Issues & Solutions

### Issue: "Permission denied" on serial port
**Fix:**
```bash
sudo usermod -a -G dialout $USER
sudo reboot
```

### Issue: Python module not found
**Fix:**
```bash
cd ~/Desktop/offline-setup-12Sep
source venv/bin/activate
pip list  # Check what's installed
# Re-run Python setup
bash one_click_system_py313.sh
```

### Issue: Service fails to start
**Fix:**
```bash
sudo journalctl -u meter-dashboard -n 50  # Check logs
sudo systemctl edit meter-dashboard  # Check service file
# Verify paths in service file match actual locations
```

### Issue: Static IP not working
**Fix:**
```bash
# Check dhcpcd.conf
sudo cat /etc/dhcpcd.conf | grep -A5 "interface eth0"

# Re-run static IP setup
sudo bash ~/Desktop/offline-setup-12Sep/setup_launchers/setup_static_ethernet.sh

# Restart networking
sudo systemctl restart dhcpcd
```

### Issue: Desktop shortcuts don't work
**Fix:**
```bash
# Check desktop file paths
cat ~/Desktop/MasterSetup_Admin.desktop | grep "Exec="

# Verify script locations
ls -l ~/Desktop/offline-setup-12Sep/setup_launchers/master_setup.sh

# Re-copy desktop files
cp ~/Desktop/offline-setup-12Sep/setup_launchers/*.desktop ~/Desktop/
chmod +x ~/Desktop/*.desktop
```

---

## ✅ Sign-Off Checklist

Before declaring the setup ready for production:

- [ ] Test passed on fresh Pi (0 critical failures)
- [ ] All services start successfully
- [ ] Terminal UI accessible via SSH
- [ ] Desktop UI launches correctly
- [ ] Data collection verified (with test meter)
- [ ] Auto-start works after reboot
- [ ] Documentation is accurate
- [ ] Known issues documented
- [ ] Recovery procedures documented

---

## 📝 Test Log Archive

Keep test logs for each test run:

```bash
# Create test results directory
mkdir -p ~/Desktop/offline-setup-12Sep/test_results

# Copy test log after each run
cp /tmp/setup_test_*.log ~/Desktop/offline-setup-12Sep/test_results/

# Name with description
mv ~/Desktop/offline-setup-12Sep/test_results/setup_test_*.log \
   ~/Desktop/offline-setup-12Sep/test_results/test_run_1_fresh_pi4_$(date +%Y%m%d).log
```

---

## 🔄 Continuous Testing

For ongoing development:

1. **After every code change:** Run `test_complete_setup.sh`
2. **Before git push:** Ensure all tests pass
3. **After git pull on Pi:** Re-run tests
4. **Weekly:** Full end-to-end test with fresh Pi image
5. **Before production deployment:** Complete Phase 1-4 testing

---

## 🆘 Escalation Path

If persistent failures occur:

1. **Document the failure:** Capture full test log
2. **Check setup log:** Review `logs/master_setup_*.log`
3. **Check service logs:** `sudo journalctl -xe`
4. **Minimal test:** Try running just one component
5. **Clean slate:** Test on completely fresh SD card
6. **Report issue:** Include all logs and exact steps to reproduce

---

**Remember:** The goal is 100% automated setup with zero manual intervention!
