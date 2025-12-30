# Upgrading from Python 3.11.2 Tarball to Python 3.13.x (Raspberry Pi)

This guide explains safe, reproducible approaches to move the offline deployment from the existing Python **3.11.2 tarball** to **Python 3.13.x**. It includes why *not* to simply ship a pre-built virtual environment, and offers several packaging alternatives.

---
## 1. Summary of Recommended Strategy

1. Build Python 3.13.x from source on a donor Pi of the **same architecture** (aarch64 vs armv7l).
2. Produce a minimal runtime tarball (similar layout to 3.11.2) and checksum.
3. Maintain/update the offline wheelhouse (`packages_folder/`) with `cp313` wheels.
4. On each target Pi: verify architecture, extract runtime tarball, run `ldconfig`, create a *fresh* venv, offline install wheels, smoke test.

This mirrors the proven 3.11.2 workflow and avoids the fragility of distributing a pre-made venv.

---
## 2. Why Not Ship a Pre-Built Virtual Environment?

| Concern | Explanation |
|---------|-------------|
| Absolute paths | Scripts in `venv/bin/` have shebang `#!/usr/local/bin/python3.13` or donor-specific paths; if target differs, they break. |
| Compiled artifacts | Wheels (e.g. `numpy`) embed architecture-specific optimizations; mixing architectures silently fails or produces illegal instructions. |
| `pyvenv.cfg` references | The `home = ...` path may differ; moving the venv can cause pip / distutils confusion. |
| Dynamic linker deps | Shared libs relied on by the interpreter must exist; a venv tarball doesn’t guarantee system lib compatibility. |
| SSL / _sqlite modules | If system libraries differ, the interpreter inside the venv can lack working SSL or database support. |
| Upgrades & maintenance | Rebuilding venv for security fixes is less transparent than rebuilding a clean runtime tarball + fresh venv creation. |

A shipped venv *can* work only if: identical architecture, identical base OS version (glibc, OpenSSL), identical path target (e.g. `/opt/dashboard_venv`), and careful post-extraction fixups. This is brittle compared to installing a Python runtime + rebuilding venv.

---
## 3. Building Python 3.13.x Runtime Tarball

```bash
# Pre-req system packages (adjust for Debian/RPi OS):
sudo apt update
sudo apt install -y build-essential libssl-dev zlib1g-dev libbz2-dev \
  libreadline-dev libsqlite3-dev libffi-dev libncurses5-dev libncursesw5-dev \
  xz-utils tk-dev uuid-dev libgdbm-dev liblzma-dev

PY_VER=3.13.5   # adjust to desired patch release
wget https://www.python.org/ftp/python/${PY_VER}/Python-${PY_VER}.tgz
sha256sum Python-${PY_VER}.tgz  # record for integrity log

# Extract & build
 tar xf Python-${PY_VER}.tgz
 cd Python-${PY_VER}
 ./configure --prefix=/usr/local --enable-optimizations --with-lto \
   --enable-shared CFLAGS='-O3 -pipe'
 make -j$(nproc)
 sudo make install
 sudo ldconfig

/usr/local/bin/python3.13 -V
/usr/local/bin/python3.13 -m ensurepip --upgrade
```

### Package the Runtime
Produce a lean tarball (exclude test suite and ensure only needed directories):
```bash
cd /usr/local
sudo tar -czf ~/python3.13-dist.tar.gz \
  bin/python3.13 \
  lib/libpython3.13.so* \
  lib/python3.13 \
  include/python3.13
sha256sum ~/python3.13-dist.tar.gz > ~/python3.13-dist.tar.gz.sha256
```
Distribute `python3.13-dist.tar.gz` + its checksum.

---
## 4. Refresh Wheelhouse for cp313

On the donor Pi:
```bash
source /usr/local/bin/python3.13 -m venv buildwheel
source buildwheel/bin/activate
python -m pip install --upgrade pip wheel
python -m pip download --only-binary=:all: --dest packages_folder \
  numpy pandas pymodbus pyserial paho-mqtt termcolor python-dateutil tzdata six pytz

# Verify tags:
ls packages_folder | grep cp313
```
Remove any obsolete `cp311` wheels once migration is confirmed.

---
## 5. Target Pi Upgrade Steps

```bash
uname -m                                 # confirm architecture
sha256sum -c python3.13-dist.tar.gz.sha256
sudo tar -C /usr/local -xzf python3.13-dist.tar.gz
sudo ldconfig
/usr/local/bin/python3.13 -V

cd /path/to/offline-setup-12Sep
rm -rf venv
/usr/local/bin/python3.13 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --no-index --find-links=packages_folder \
  numpy pandas pymodbus pyserial paho-mqtt termcolor python-dateutil tzdata six pytz
python - <<'PY'
import sys, numpy, pandas
print(sys.version)
print(numpy.__version__, pandas.__version__)
PY
```

Update any service units or scripts that reference `python3.11` to `python3.13` if they refer to the interpreter directly.

---
## 6. Option B: Use System Python (If 3.13 Available via OS)
If Raspberry Pi OS ships Python 3.13 pre-packaged:

```bash
python3 -V            # ensure 3.13.x
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --no-index --find-links=packages_folder <packages>
```
Still recreate venv on each device; *do not* ship a pre-made venv.

---
## 7. Option C: Pre-Built Venv Tarball (Not Recommended)
If you must:
1. Create under a neutral path (e.g. `/opt/dashboard_venv`).
2. Use `--copies` to reduce symlink fragility (if using `virtualenv`).
3. After extraction on target, run a repair step:
   ```bash
   sed -i 's@home = .*@home = /usr/local/bin@' /opt/dashboard_venv/pyvenv.cfg || true
   /opt/dashboard_venv/bin/python -m pip install --upgrade pip  # refresh scripts
   ```
4. Run a full smoke test.

Expect higher breakage risk if OS differs. Keep this as a last resort.

---
## 8. Alternative Packaging (More Robust)
| Tool | Benefit | Notes |
|------|---------|-------|
| PEX | Single executable with all deps; hermetic | Still depends on system glibc & libffi; build on matching arch. |
| Shiv | Similar to PEX; zip + bootstrap | Simpler build; runtime unzip overhead. |
| zipapp + `--compressed` | Pure-Python only | Native extensions (numpy) disqualify. |
| Docker container | Fully pinned runtime | Bigger footprint; requires container runtime installed. |
| uv (Astral) | Faster env creation; lockfiles | Can generate lock + sync offline; still needs Python runtime. |

For heavy numeric packages, shipping wheels + runtime tarball remains simplest.

---
## 9. Post-Upgrade Validation
```bash
/usr/local/bin/python3.13 -c 'import ssl, sqlite3, _ctypes; print("core OK")'
./venv/bin/python -c 'import numpy as n; print(n.__version__)'
ldd /usr/local/bin/python3.13 | grep libpython3.13
```
Confirm services run and logs show correct Python version.

---
## 10. Rollback Plan
Keep previous `python3.11-dist.tar.gz` and wheels. To revert:
```bash
sudo rm -f /usr/local/bin/python3.13
sudo rm -rf /usr/local/lib/python3.13
sudo tar -C /usr/local -xzf python3.11-dist.tar.gz
sudo ldconfig
rm -rf venv
/usr/local/bin/python3.11 -m venv venv
# reinstall packages from cp311 wheelhouse
```

---
## 11. Quick Decision Matrix
| Scenario | Recommended Approach |
|----------|---------------------|
| Need fastest migration; control donor & targets | Build 3.13 tarball + recreate venv per Pi |
| OS already ships Python 3.13 | Use system Python + offline wheels |
| Need single-file distribution | Use PEX (built on matching arch) |
| Constrained bandwidth; minimal changes | Stay on 3.11 until next security fix, plan staged build |

---
## 12. Security & Maintenance
Track upstream CVEs; rebuild tarball for each security patch (3.13.x). Keep a changelog noting:
- Build date
- Source tarball checksum
- Compile flags
- Wheel versions

---
## 13. Automation Idea
Extend `one_click_py311_tarball.sh` into a version-agnostic script:
- Accept `--python-tarball python3.13-dist.tar.gz`
- Infer major.minor from extracted binary for venv recreation checks.

---
## 14. Checklist
- [ ] Donor architecture matches targets
- [ ] Python 3.13 built & installed
- [ ] Runtime tarball + sha256 created
- [ ] cp313 wheels downloaded
- [ ] Target extraction & venv recreation succeeded
- [ ] Smoke tests pass
- [ ] Services updated (if any) to new interpreter
- [ ] Changelog updated

---
**Conclusion:** Upgrading via a runtime tarball + per-device venv recreation remains the most reliable offline strategy. Shipping a pre-built venv is fragile and should be avoided unless all systems are strictly identical.
