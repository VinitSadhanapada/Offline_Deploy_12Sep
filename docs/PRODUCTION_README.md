**Overview**

This document summarizes the recommended, prioritized steps to take the `offline-setup-12Sep` project to a production-ready state on Raspberry Pi devices (offline-capable, robust, and future-proof against differing Python versions). It is written to be actionable within a 2–3 day effort and includes concrete commands, files to add, and verification practices.

**Goals**
- **Stability:** Ensure the service runs reliably and recovers from errors without manual intervention.
- **Offline-first install:** Installer works without internet using the included `packages_folder`.
- **Future-proofing:** Works across Raspberry Pi systems with different default Python versions.
- **Maintainability:** Clear developer and deployment docs, tests, and CI for ongoing safety.

**Quick Prioritized Plan (2–3 day schedule)**
- **Day 1 — Critical (must do before deploy):**
  - **Pin dependencies:** Produce a pinned `requirements.txt` compatible with the wheels in `packages_folder`.
  - **Bootstrap installer:** Add `bootstrap.sh` (idempotent) to detect available Python >= 3.8, create a `.venv`, and install packages offline.
  - **Systemd integration:** Add `systemd/usb_download.service` and make `bootstrap.sh` enable and start it.
  - **Graceful shutdown:** Ensure main scripts handle `SIGTERM`/`SIGINT` and flush/close resources.
- **Day 2 — Stability & verification:**
  - **Static checks:** Run `ruff` and `mypy` (fix critical issues).
  - **Tests:** Add `pytest` tests (unit and integration mocks) for file I/O, config parsing, and device interfaces.
  - **Logging & rotation:** Ensure logs are rotated and informative.
- **Day 3 — Polish & release:**
  - **Packaging:** Build wheel/sdist; collect wheels into `release/wheels/` and copy those to `packages_folder`.
  - **Docs:** Add `DEPLOY.md` and `DEVELOPER.md` (or use this `PRODUCTION_README.md` for deploy steps).
  - **Smoke tests and tag:** Run a final smoke test on a Raspberry Pi and tag a release with rollback steps.

**Concrete Files to Add (start immediately)**
- `requirements.txt` — pinned package versions matching `packages_folder`.
- `bootstrap.sh` — robust installer that uses `--no-index --find-links`.
- `systemd/usb_download.service` — example systemd unit.
- `tests/` — minimal `pytest` suite for critical flows.
- `DEPLOY.md` / `DEVELOPER.md` — short how-tos and troubleshooting.

**Bootstrap installer (behavior & example snippets)**
- Purpose: make installing the app on an offline Pi trivial and idempotent.
- High-level behavior:
  - Detect a suitable Python: check candidates `python3.13 python3.12 python3.11 python3.10 python3.9 python3`.
  - Require Python >= 3.8 (adjustable).
  - Create a virtual environment under the project: `./.venv`.
  - Install dependencies offline: `pip install --no-index --find-links "$APP_DIR/packages_folder" -r "$APP_DIR/requirements.txt"`.
  - Create a service user (optional), copy the `systemd` unit, `systemctl daemon-reload`, `systemctl enable --now`.

Example command sequence (to be placed in `bootstrap.sh`):
```
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGES_DIR="$APP_DIR/packages_folder"
PY_CANDIDATES=(python3.13 python3.12 python3.11 python3.10 python3.9 python3)
for PY in "${PY_CANDIDATES[@]}"; do
  if command -v "$PY" >/dev/null 2>&1; then
    VER=$($PY -c 'import sys;print(".".join(map(str,sys.version_info[:2])))')
    MAJOR=${VER%%.*}; MINOR=${VER#*.}
    if [ "$MAJOR" -gt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 8 ]; }; then
      SELECTED_PY="$PY"
      break
    fi
  fi
done
if [ -z "${SELECTED_PY:-}" ]; then
  echo "No suitable Python found (>=3.8). Please install or choose another Pi image." >&2
  exit 1
fi
"$SELECTED_PY" -m venv "$APP_DIR/.venv"
. "$APP_DIR/.venv/bin/activate"
pip install --upgrade pip
pip install --no-index --find-links "$PACKAGES_DIR" -r "$APP_DIR/requirements.txt"
```

Make the script idempotent (skip venv creation if `.venv` exists, validate installed packages match `requirements.txt`). Log output to `logs/bootstrap.log` with timestamps.

**Systemd unit (example)**
Place a file at `systemd/usb_download.service` and have `bootstrap.sh` copy it to `/etc/systemd/system/`.
```
[Unit]
Description=USB Download Service
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/Desktop/offline-setup-12Sep
ExecStart=/home/pi/Desktop/offline-setup-12Sep/.venv/bin/python /home/pi/Desktop/offline-setup-12Sep/cloud_sync.py
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
KillMode=control-group

[Install]
WantedBy=multi-user.target
```

Notes:
- Avoid hard-coding `/home/pi` where possible; allow `APP_DIR` and `APP_USER` environment variables to be supplied to the unit or managed by the installer.

**Logging & rotation**
- Prefer `logging.handlers.RotatingFileHandler` for file logs stored under the project `logs/` directory, or rely on `systemd` journal but supplement with file logs for offline debugging.
- Ensure log lines include ISO timestamps, log-level, module context, and exception stack traces.

**Graceful shutdown & resource cleanup**
- Add `signal.signal(signal.SIGTERM, handler)` and `SIGINT` handling in long-running scripts such as `cloud_sync.py` and `usb_csv_auto_copy.py`.
- Use a `threading.Event()` or a global shutdown flag checked by worker loops.
- Close file and device handles in `finally` blocks. Flush CSV writes and use `os.replace()` for atomic file swaps.

**File & concurrency safety**
- If multiple processes or threads may write the same files (e.g. `data/csv/readings_all.csv`), use file locking (e.g., `fcntl` or `portalocker`) or centralize writing through a single writer thread/process.
- For CSV appends: open with `with open(..., 'a', newline='')` and call `file.flush(); os.fsync(file.fileno())` after writes when durability is needed.

**Testing & CI**
- Add `tests/` using `pytest`. Start with these tests:
  - Config validation: `config.json` schema validation (use `jsonschema`).
  - CSV append and atomic replace behavior.
  - Device driver mocks for `meter_device.py` to verify failure handling and retries.
  - Graceful shutdown test for `cloud_sync.py` (simulate `SIGTERM`).
- Add GitHub Actions workflow to run `ruff`, `mypy`, and `pytest` on push and PR.

**Packaging & offline release**
- Build release artifacts (`python -m build`) and collect wheels in `release/wheels/` and copy those to `packages_folder/` for offline installs.
- Provide checksums for the release artifacts.

**Backups & rollback**
- `bootstrap.sh` should make a time-stamped backup of `data/` and `config.json` to `backups/` before upgrade.
- Add `rollback.sh` to restore the most recent backup and restart the service.

**Developer & deployment documentation (what to include in `DEPLOY.md` or `DEVELOPER.md`)**
- Prerequisites: available Python or instructions to install a compatible Python on Pi.
- Offline install steps (exact `bootstrap.sh` usage and manual fallback commands).
- How to enable/disable the service: `systemctl enable --now usb_download.service` / `systemctl stop usb_download.service`.
- Troubleshooting checklist: how to read logs, check journal (`journalctl -u usb_download.service --no-pager`), common fixes.
- How to create a new release and vendor wheels into `packages_folder`.

**Quick commands**
Use these after placing the project on a Pi (examples):
```
cd /home/pi/Desktop/offline-setup-12Sep
sudo ./bootstrap.sh
sudo systemctl status usb_download.service
sudo journalctl -u usb_download.service --follow
```

**Compatibility & future-proofing notes**
- Support multiple Python versions by:
  - Choosing a reasonable minimum (recommend >= 3.8) and documenting it.
  - Installing into an isolated `.venv` (so system Python changes don't break the app).
  - Vendorizing wheels in `packages_folder` so the installer does not need internet.
- Consider a container option (Docker/Podman) for environments where containers are supported — this provides even stronger runtime reproducibility, but is optional for offline Pi deployments.

**Acceptance checklist before tagging a release**
- [ ] `requirements.txt` pinned and matches `packages_folder`.
- [ ] `bootstrap.sh` tested on a Pi image and is idempotent.
- [ ] Systemd unit in place and service starts/stops cleanly.
- [ ] Critical tests pass (`pytest`).
- [ ] Static checks run (ruff/mypy) and no critical errors.
- [ ] Logging and rotation verified and logs are readable.
- [ ] Backups and rollback verified.
- [ ] `DEPLOY.md` and `DEVELOPER.md` exist and are clear.

**Next steps I can implement for you now (pick any)**
- Create `bootstrap.sh` and `systemd/usb_download.service` and test them locally (Day 1 items).
- Generate `requirements.txt` by scanning `packages_folder` and the repo.
- Add a minimal `tests/` suite and a basic GitHub Actions workflow.

If you'd like, I will start by creating `bootstrap.sh`, `systemd/usb_download.service`, and a `DEPLOY.md` with exact commands and move the todo item to completed after creation and a quick smoke check. Otherwise tell me which of the three deliverables above to create first.

---
Generated on: 2025-12-17
