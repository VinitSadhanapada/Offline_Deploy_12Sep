<!-- Copilot instructions for Offline_Deploy_12Sep -->
# Copilot instructions — Offline_Deploy_12Sep

This file provides focused, actionable guidance for AI coding agents working in this repository. Keep changes small, preserve CSV semantics, and prefer configuration-aware edits.

- Project type: Python scripts (single-file apps + small modules). No tests present.
- Key runtime files: `simple_meter_ui.py`, `simple_rpi_dashboard.py`, `print_dashboard2.py`, `meter_manager.py`, `mqtt_client.py`, `cloud_sync.py`.
- Meter drivers: `elmeasure_*.py` implement device-specific read logic. They expose `read_data()` and attributes like `name`, `model`, `device_address`, `location`.

Important patterns and conventions
- CSV layout: CSV header is produced by `meter_manager.create_formatted_csv_header()` and the expected header order is `Device_ID, Meter_Name, Time, Model, ...`. Time is column index 2 and parsed with `'%Y-%m-%d %H:%M:%S'` in retention pruning. Do not reorder or rename the Time column.
- MeterManager expectations: `MeterManager` expects a single CSV file per location (the constructor enforces `len(csv_filenames) == 1`). Avoid changing this contract without updating callers across the repo.
- Retention behavior: CSV pruning runs at most once per hour and uses `MeterManager._maybe_prune_old_rows()`; be conservative with I/O changes.
- MQTT config loading: `mqtt_client._load_mqtt_config()` prefers `/home/pi/meter_config/config.json` and falls back to the local `config.json`. Keys may be under a top-level `MQTT` object or as `MQTT_*` top-level keys. Edits that touch MQTT behavior should preserve this precedence and environment-variable overrides.
- JSONC usage: Config files (e.g., `config.jsonc`) support `//` comments and the code often strips `//` before parsing. When programmatically modifying configs, preserve comments or write valid JSONC.

Developer workflows and commands
- Install runtime deps (online): `python3 -m pip install -r requirements.txt`.
- Offline/packaged installs: see `offline-setup-12Sep/packages_folder/` and `check_offline_wheels.py` for offline wheel handling. Prefer using those artifacts for reproducible offline deployments.
- Python versions: repo includes a `Python-3.11.2/` tree and docs mentioning upgrades to 3.13 (see `UPGRADE_PYTHON_3.13.md` and `one_click_system_py313.sh`). Confirm target Python version before changing language features.
- Auto-start: system startup and cron helpers are `enable_auto_start.sh` and `startup_cron_setup.sh` — edits to service installation should preserve these scripts' behavior.
- Running the dashboard locally: `python3 simple_meter_ui.py` or `python3 simple_rpi_dashboard.py` depending on UI variant.

Integration points and data flow
- Primary integrations: MQTT (via `paho-mqtt`), local CSV files under `data/`, optional cloud sync (`cloud_sync.py`, rclone/rsync hooks in `config.jsonc`).
- USB data flow: `usb_csv_auto_copy.py` polls removable media and copies CSVs into `data/csv` (see `config.jsonc.usb_copy`). Keep the `dest_root_name` and `subfolder` semantics when modifying the copy logic.

Code edits guidance (actionable rules)
- Keep CSV semantics stable: preserve header order and timestamp format.
- Respect config precedence: environment variables -> `/home/pi/meter_config/config.json` -> project `config.json`/`config.jsonc`.
- Avoid long-running blocking changes on the MQTT thread; `mqtt_client` uses a background thread with `loop_start()` and a reconnect loop.
- When changing device read logic in `elmeasure_*`, return lists where index 0 is the timestamp string (matching header `Time`).
- When adding new dependencies, update `requirements.txt` and, if required for offline deploys, add wheels to `offline-setup-12Sep/packages_folder/` and update `check_offline_wheels.py` if necessary.

Files to consult for examples
- `meter_manager.py` — CSV header, retention, multi-device coordination.
- `mqtt_client.py` — config merging, payload shaping, background thread.
- `config.jsonc` — canonical runtime config structure (SIMULATION_MODE, MQTT, usb_copy, cloud_sync).
- `venv_utils.py`, `one_click_system_py313.sh`, `enable_auto_start.sh` — environment and deployment helpers.
- `elmeasure_*.py` — device-specific read implementations.

When to ask the maintainer
- If a change modifies CSV header structure, timestamp format, or retention logic.
- If you need to change MQTT topic names, default QoS, or broker discovery logic.
- Before upgrading to a newer Python minor version that may change package wheels for offline deploy.

If anything here looks incorrect or you'd like more detail in any section, ask and I'll iterate.
