# Fast Deploy Guide (Freshly Flashed Pi with System Python 3.13.5)

This guide assumes a newly flashed Raspberry Pi OS image that already includes **Python 3.13.5** as `python3`. Goal: copy the offline deployment folder and get the dashboard running with minimal steps, while keeping an option to install (or retain) Python 3.11.2 side‑by‑side if strict version pinning is needed.

---
## 1. Contents to Copy Onto Each Fresh Pi
Copy the entire `offline-setup-12Sep/` directory (or a slimmed subset) containing:
- `packages_folder/` (wheelhouse; update to include `cp313` wheels if using Python 3.13)
- Project scripts: `simple_rpi_dashboard.py`, `simple_meter_ui.py`, services scripts (`enable_auto_start.sh`, `usb_csv_auto_copy.py`, `cloud_sync.py`, etc.)
- Config files: `config.json`, `device_config.json`
- (Optional) Python runtime tarball(s): `python3.11-dist.tar.gz` + checksum if you need Python 3.11 side‑by‑side.
- Support docs: `README_PY311.md`, `UPGRADE_PYTHON_3.13.md`

---
## 2. Recommended Strategy Going Forward
Because 3.13.5 ships with the OS:
- Use **system Python 3.13** for new deployments and keep wheelhouse updated with `cp313` wheels.
- Retain a **Python 3.11 tarball** only if regression tests show differences or if you have native dependency constraints.
- Avoid downgrading or replacing the system's `python3`; install 3.11 into `/usr/local` side‑by‑side.

---
## 3. Immediate Setup (System Python 3.13)
```bash
cd ~/Desktop/offline-setup-12Sep
python3 -V          # Expect 3.13.5
uname -m            # Confirm architecture (aarch64 or armv7l)

# Create fresh venv under project directory
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip

# Offline install from wheelhouse (ensure cp313 wheels present)
python -m pip install --no-index --find-links=packages_folder \
  numpy pandas pymodbus pyserial paho-mqtt termcolor python-dateutil tzdata six pytz

# Smoke test
python - <<'PY'
import sys, numpy, pandas
print(sys.version)
print('numpy', numpy.__version__, 'pandas', pandas.__version__)
PY

# Dashboard environment setup (if script automates additional steps)
python simple_rpi_dashboard.py --setup
python simple_rpi_dashboard.py --run   # or launch UI
```
Deactivate when done:
```bash
deactivate
```

---
## 4. Optional: Install Python 3.11.2 Side‑By‑Side
If you require continuity with 3.11 for testing or conservative rollout:
```bash
# Copy python3.11-dist.tar.gz and checksum to a working folder
cd ~/Desktop/offline-setup-12Sep
sha256sum -c python3.11-dist.tar.gz.sha256
sudo tar -C /usr/local -xzf python3.11-dist.tar.gz
sudo ldconfig
/usr/local/bin/python3.11 -V

# Create a separate venv (keep naming clear)
/usr/local/bin/python3.11 -m venv venv311
source venv311/bin/activate
python -m pip install --upgrade pip
python -m pip install --no-index --find-links=packages_folder \
  numpy pandas pymodbus pyserial paho-mqtt termcolor python-dateutil tzdata six pytz
python - <<'PY'
import sys
print('Py311 venv:', sys.version)
PY
deactivate
```
You can run the dashboard with either interpreter:
```bash
./venv/bin/python simple_rpi_dashboard.py --run       # 3.13
./venv311/bin/python simple_rpi_dashboard.py --run    # 3.11
```

---
## 5. Keeping Wheelhouse Current
When system Python revs (e.g. 3.13.6 → still cp313 ABI):
- Existing `cp313` wheels remain valid.
- Re-download only if you need newer package versions or security patches.

If Python upgrades major ABI (3.13 → 3.14):
1. Recreate wheelhouse with `cp314` wheels.
2. Rebuild runtime tarball (if using side‑by‑side custom version).
3. Recreate venvs per device.

To update wheelhouse:
```bash
source venv/bin/activate
python -m pip download --only-binary=:all: --dest packages_folder \
  numpy pandas pymodbus pyserial paho-mqtt termcolor python-dateutil tzdata six pytz
deactivate
ls packages_folder | grep cp313   # verify tags
```

---
## 6. Why a 3.13 Runtime Tarball Is Usually Unnecessary Now
Pros of relying on system Python 3.13:
- Zero initial extraction time.
- Updates via OS security channels.
- Smaller deliverables; only wheelhouse + scripts.

Cons:
- Future OS image variations could change minor version unexpectedly.
- Harder to freeze interpreter state for reproducibility across time.

If strict reproducibility is needed, keep a tarball snapshot of a known‑good 3.13 build and optionally automate verification (`python -c "import ssl, sqlite3"`).

---
## 7. Ensuring Python 3.11 Is Present at Flash Time
Options:
1. **Custom Image Bake**: Mount the image (loop device), chroot, install /usr/local Python 3.11, unmount, flash. Result: Pi boots with both 3.13 (system) and 3.11 (custom).
2. **First-Boot Provision Script**: Place a script in `/boot/firstboot.sh` (using Raspberry Pi Imager advanced settings or a systemd unit) that extracts `python3.11-dist.tar.gz` on the first boot.
3. **pi-gen Stage**: Fork `pi-gen` and add a stage that builds or injects 3.11.2 into `/usr/local`.
4. **Ignore Downgrade**: Maintain only 3.13 and verify packages; simplest unless an app hard-requires 3.11 semantics.

Recommended: Option 2 (first-boot script) for minimal maintenance.

Example first-boot systemd unit drop-in (conceptual):
```bash
# /etc/systemd/system/py311-install.service
[Unit]
Description=Install Python 3.11 Tarball Once
ConditionPathExists=/boot/python3.11-dist.tar.gz
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/bash -c 'tar -C /usr/local -xzf /boot/python3.11-dist.tar.gz && ldconfig'
ExecStart=/usr/bin/bash -c 'mv /boot/python3.11-dist.tar.gz /boot/python3.11-dist.tar.gz.installed'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```
Enable it during image customization:
```bash
sudo systemctl enable py311-install.service
```

---
## 8. Service Units & Interpreter Selection
If you rely on a systemd service to auto-start the dashboard, choose interpreter explicitly:
- For system Python 3.13: `ExecStart=/home/pi/Desktop/offline-setup-12Sep/venv/bin/python simple_rpi_dashboard.py --run`
- For side‑by‑side 3.11: `ExecStart=/home/pi/Desktop/offline-setup-12Sep/venv311/bin/python simple_rpi_dashboard.py --run`

Avoid generic `python3` if you need version pinning.

---
## 9. Minimal Command Cheat Sheets
System Python path:
```bash
python3 -m venv venv && source venv/bin/activate && python -m pip install --upgrade pip
```
Install offline deps:
```bash
python -m pip install --no-index --find-links=packages_folder numpy pandas
```
Run dashboard:
```bash
./venv/bin/python simple_rpi_dashboard.py --run
```

---
## 10. Decision Matrix
| Need | Action |
|------|--------|
| Fastest new device bring-up | Use system Python 3.13 + recreate venv |
| Long-term reproducibility | Keep runtime tarball (3.13 or 3.11) in archive + versioned wheelhouse |
| Legacy compatibility tests | Maintain parallel 3.11 venv |
| Minimal artifacts | Drop 3.11; rely solely on system 3.13 |
| Future ABI changes | Regenerate wheelhouse & venvs when Python major/minor ABI changes |

---
## 11. Ongoing Maintenance Checklist
- [ ] Wheelhouse contains only current ABI wheels (cp313).
- [ ] First-boot script (if used) still valid after OS image updates.
- [ ] Service units point to correct venv interpreter.
- [ ] Smoke tests pass (numpy/pandas import).
- [ ] Security patches tracked (Python release notes).

---
**Conclusion:** For freshly flashed Pis with Python 3.13.5, the quickest path is to rely on system Python and recreate the venv using your offline wheelhouse. Keep 3.11 only if tests demand it; otherwise simplify deployment.
