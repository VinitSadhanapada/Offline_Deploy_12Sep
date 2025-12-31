# FRESH RASPBERRY PI - COMPLETE TESTING INSTRUCTIONS

## 🎯 Objective
Test the complete setup on a fresh Raspberry Pi to ensure 100% automated deployment.

---

## 📦 What You Need

### Hardware
- Fresh Raspberry Pi (any model with Raspberry Pi OS)
- MicroSD card with fresh OS install
- Ethernet cable (for SSH testing)
- Laptop (for SSH access testing)
- USB-RS485 adapter + meter (optional, for full functionality test)

### Software Requirements (on Pi)
- Raspberry Pi OS (Bullseye or Bookworm)
- Python 3.11+ (usually pre-installed)
- Git (usually pre-installed)

---

## 🚀 STEP-BY-STEP TESTING PROCEDURE

### STEP 1: Prepare Fresh Pi

**On fresh Raspberry Pi:**

```bash
# Boot up the Pi and open terminal

# 1. Check Python version (should be 3.11+)
python3 --version

# 2. Ensure git is installed
git --version

# If git is missing:
sudo apt update && sudo apt install -y git
```

---

### STEP 2: Clone Repository

```bash
# 1. Navigate to Desktop
cd ~/Desktop

# 2. Clone your repository
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git offline-setup-12Sep

# Or if you pushed to different remote:
# git clone YOUR_GIT_URL offline-setup-12Sep

# 3. Enter directory
cd offline-setup-12Sep

# 4. Verify files are present
ls -la
# Should see: setup_launchers/, docs/, README.md, etc.
```

---

### STEP 3: Pre-Flight Check

```bash
# Run pre-flight validation
chmod +x preflight_check.sh
bash preflight_check.sh
```

**Expected Output:**
```
✓ In correct directory
✓ Python version: 3.11
✓ No venv found (fresh system)
✓ No service installed (fresh system)
✓ Test script exists
```

**If any errors:** Fix them before continuing

---

### STEP 4: Quick Test (Optional but Recommended)

```bash
# Run quick validation of critical files
bash quick_test.sh
```

**Expected Output:**
```
Passed: 13  Failed: 0
Ready for full test!
```

**If any failures:** The repo may be incomplete. Check git status.

---

### STEP 5: Run Comprehensive Test

```bash
# Run the full test suite (will prompt for confirmation)
sudo bash test_complete_setup.sh
```

**What happens:**
1. Tests 1-8: Validates workspace structure (2-3 minutes)
2. **Test 9: Asks permission to run master_setup.sh**
   - Type `y` and press Enter to continue
   - master_setup.sh will run (5-10 minutes)
3. Tests 10-20: Validates setup results (2-3 minutes)

**Total Time:** ~10-15 minutes

**Watch for:**
- Green `✓ PASS` messages (good)
- Yellow `⚠ WARN` messages (usually acceptable)
- Red `✗ FAIL` messages (need investigation)

---

### STEP 6: Review Test Results

After test completes:

```bash
# Check summary at end of output
# Look for:
# Passed:   XX
# Warnings: XX
# Failed:   0    <- This should be ZERO

# View full test log
ls -lt /tmp/setup_test_*.log | head -1
cat $(ls -lt /tmp/setup_test_*.log | head -1 | awk '{print $9}')
```

**SUCCESS Criteria:**
- ✓ `FAILED: 0` (no critical failures)
- ✓ `PASSED: 50+` (most tests passed)
- ⚠ Warnings are OK for:
  - Empty CSV files (no data yet)
  - Services not running (will start after reboot)
  - No Ethernet IP (cable not connected)

**FAILURE Criteria:**
- ✗ Any `FAILED` tests related to:
  - Python modules not installed
  - Scripts not executable
  - Config files invalid
  - Core files missing

---

### STEP 7: Post-Setup Validation

If test passed, verify the setup:

```bash
# 1. Check Python virtual environment
ls -la venv/
source venv/bin/activate
python3 -c "import pymodbus, paho.mqtt.client, pandas; print('All modules OK')"
deactivate

# 2. Check systemd service
sudo systemctl status meter-dashboard

# 3. Check network config
cat /etc/dhcpcd.conf | grep "192.168.137.2"

# 4. Check user groups
groups $USER | grep dialout
groups $USER | grep gpio

# 5. View setup log
cat logs/master_setup_*.log | tail -50
```

---

### STEP 8: Functional Tests

#### Test A: Terminal UI

```bash
# Launch terminal UI
python3 terminal_meter_ui.py

# Or using wrapper:
bash terminal_ui.sh
```

**Expected:**
- Color menu with 9 options
- Can navigate with arrow keys
- Press '9' or 'Q' to exit

**Common Issues:**
- Terminal too small: Resize to 80x24+
- Permission denied: Reboot needed (dialout group)

#### Test B: Desktop UI

```bash
# From terminal:
python3 simple_meter_ui.py

# Or double-click:
# ~/Desktop/SimpleMeterUI_Admin.desktop
```

**Expected:**
- GUI window opens
- Shows system info
- No crash on startup

#### Test C: SSH Access (Requires Ethernet Cable)

**On Laptop:**
1. Connect Ethernet cable: Laptop ↔ Pi
2. Configure laptop static IP: `192.168.137.1`
3. Test connection:
```bash
ping 192.168.137.2
ssh pi@192.168.137.2
```

**On Pi (via SSH):**
```bash
cd ~/Desktop/offline-setup-12Sep
python3 terminal_meter_ui.py
```

#### Test D: Auto-Start After Reboot

```bash
# Reboot the Pi
sudo reboot

# After reboot, SSH back in
ssh pi@192.168.137.2

# Check service started automatically
sudo systemctl status meter-dashboard

# Should show "active (running)"
```

---

### STEP 9: Document Results

**Create test report:**

```bash
# Save test results
mkdir -p ~/Desktop/offline-setup-12Sep/test_results
cp /tmp/setup_test_*.log ~/Desktop/offline-setup-12Sep/test_results/test_fresh_pi_$(date +%Y%m%d_%H%M%S).log

# Create summary file
cat > ~/Desktop/offline-setup-12Sep/test_results/TEST_SUMMARY.txt << 'EOF'
Test Date: $(date)
Raspberry Pi Model: [Fill in - e.g., Pi 4 Model B]
OS Version: [Check with: cat /etc/os-release]
Python Version: [Check with: python3 --version]

RESULTS:
[ ] All tests passed (0 failures)
[ ] Terminal UI works
[ ] Desktop UI works
[ ] SSH access works
[ ] Auto-start works

ISSUES FOUND:
[List any issues]

PRODUCTION READY: [ YES / NO ]
EOF
```

---

## 🔄 IF TESTS FAIL - TROUBLESHOOTING

### Scenario 1: Setup Script Fails

```bash
# Check setup log
cat ~/Desktop/offline-setup-12Sep/logs/master_setup_*.log

# Look for errors
grep -i "error\|fail" ~/Desktop/offline-setup-12Sep/logs/master_setup_*.log

# Common fixes:
# - Missing sudo: Run with sudo
# - Permission issues: Check file ownership
# - Missing packages: Re-run master_setup.sh
```

### Scenario 2: Python Modules Missing

```bash
# Verify packages_folder has wheels
ls ~/Desktop/offline-setup-12Sep/packages_folder/*.whl

# Re-run Python setup
cd ~/Desktop/offline-setup-12Sep
bash one_click_system_py313.sh
```

### Scenario 3: Service Won't Start

```bash
# Check service logs
sudo journalctl -u meter-dashboard -n 100

# Verify service file
sudo systemctl cat meter-dashboard

# Check paths are correct
# Re-run enable_auto_start.sh
cd ~/Desktop/offline-setup-12Sep
sudo bash setup_launchers/enable_auto_start.sh
```

---

## ✅ CHECKLIST FOR PRODUCTION SIGN-OFF

Before deploying to field:

- [ ] Fresh Pi test completed with 0 failures
- [ ] Terminal UI accessible via SSH
- [ ] Desktop UI launches correctly
- [ ] Auto-start works after reboot
- [ ] Static Ethernet IP configured (192.168.137.2)
- [ ] Data collection tested (if meter available)
- [ ] All documentation accurate
- [ ] Test logs archived
- [ ] Known issues documented
- [ ] Recovery procedure documented

---

## 📝 WHAT TO REPORT BACK

After testing, report:

1. **Test Results:**
   - Passed: X
   - Warnings: X
   - Failed: X

2. **Failed Tests (if any):**
   - List each failure
   - Include error messages
   - Attach test log

3. **Issues Found:**
   - Description
   - Steps to reproduce
   - Severity (Critical / Major / Minor)

4. **System Info:**
   - Pi model
   - OS version
   - Python version

5. **Final Status:**
   - READY FOR PRODUCTION: YES/NO

---

## 🔁 ITERATIVE TESTING

If issues found:

1. **Document the issue** in GitHub/notes
2. **Fix the code** in your development environment
3. **Commit and push** changes
4. **Get a FRESH Pi** (or re-flash SD card)
5. **Re-run complete test** from STEP 1
6. **Repeat** until 0 failures

**Goal:** Test must pass on completely fresh Pi with zero manual intervention!

---

## 📞 QUICK REFERENCE

```bash
# Complete test sequence on fresh Pi:
cd ~/Desktop
git clone YOUR_REPO offline-setup-12Sep
cd offline-setup-12Sep
bash preflight_check.sh
bash quick_test.sh
sudo bash test_complete_setup.sh  # Answer 'y' when prompted
```

**Expected total time:** 15-20 minutes

**Success:** All tests pass, services running, UI accessible

---

## 🆘 GET HELP

If stuck:

1. Check test log: `/tmp/setup_test_*.log`
2. Check setup log: `logs/master_setup_*.log`
3. Check service log: `sudo journalctl -u meter-dashboard`
4. Review: `TESTING_GUIDE.md` for detailed troubleshooting
5. Create GitHub issue with:
   - Test log
   - Setup log
   - Error messages
   - System info

---

**Remember:** The goal is bulletproof deployment. If it doesn't work on fresh Pi, it won't work in production!
