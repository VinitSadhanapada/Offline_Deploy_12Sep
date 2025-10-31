# Simple Meter Dashboard – Technician UI Quick Start

**Version:** Electrical IoT UI 1.0.0  
**Prepared by:** Sudhir Rupapara  
**Department:** Electrical

---

## Quick Start

1. **Hardware Setup**
	- Connect all MFMs using RS485 daisy-chain wiring.
	- Plug RS485-to-USB converter into the Raspberry Pi.
	- Power the Raspberry Pi via UPS.

2. **Software Setup**
	- Copy the `simple-meter-dashboard` folder to the Raspberry Pi Desktop.
	- Double-click `simple_meter_ui.py` to launch the Technician UI.

3. **Configuration**
	- Device configuration lives at `/home/pi/meter_config/device_config.json`.
	- Click **Configure Devices** in the UI to open the editor pre-filled from that file.
	- You can also edit the file directly (JSON or JSON-with-comments). The UI supports:
		- Top-level list of devices OR an object with a `devices`/`meters`/`items` array.
		- Alternate key names like `meter_name`/`device_name`, `meter_address`/`device_id`, `meter_model`.
	- Fields used by the dashboard are normalized to: `name`, `address`, `model`, `location`.
	- Save in the UI to write back to the same file and shape.

4. **Environment Setup**
	- Click **Setup Environment** in the UI to install all required packages and create necessary folders.

5. **Operation**
	- Use **Manual Run** to test meter readings and log data to CSV.
	- Use **Live Readings** for real-time monitoring.
	- Click **Enable Auto-Start** to set up automatic dashboard startup after reboot.
	- Manual Run reads device definitions from `/home/pi/meter_config/device_config.json`.

6. **Data Management**
	- CSV files are saved in `data/csv/`.
	- USB auto-copy (optional but recommended for field collection):
		- Controlled by `config.jsonc` → `usb_copy.enabled` (default: true).
		- When a USB drive is plugged, files from `data/csv/` are copied to `<USB>/OfflineDashboard/data/csv`.
		- The service is installed/enabled by running `sudo bash enable_auto_start.sh`.
		- Logs: `logs/usb_copy.log` (state file: `logs/.usb_copy_state.json`).
			- Behavior: copies immediately on USB insertion, then throttles repeats to every `usb_copy.cooldown_seconds` (default 600s) while the same USB stays plugged in.
			- Tip: You can test once without USB by creating a folder and running:
		  `python3 usb_csv_auto_copy.py --once --test-mount /path/to/folder`.

7. **MQTT Publishing (optional)**
	- To publish readings to MQTT (for use with `simple-meter-dashboard/iot_scripts/mqtt_to_db_ingest.py`):
		- Edit `config.jsonc` and set `ENABLE_MQTT` to `true`.
		- Configure the `MQTT` section (broker, port, topic, username/password, TLS). The runtime reads the broker and other settings from the `config.jsonc` file located in this same folder.
		- Default topic is `meter/readings` which matches the ingest script.
		- Payload includes device metadata (pi_name, pi_ip, meter_name, time, device_id, model, location) and all parameters.
		- Tip: `config.jsonc` supports // comments, but JSON values still must be valid. Put quotes around strings (e.g., usernames and passwords).

8. **Cloud Sync (optional)**
	- Pushes `data/csv/` to a remote when Wi‑Fi is available.
	- Configure `config.jsonc` → `cloud_sync`: choose a method:
		- `rclone`: requires `rclone` installed and a remote configured (`rclone config`). Set `rclone_remote` and `dest_path`.
		- `rsync`: set `rsync_target` (e.g., `user@host:/path`) and optionally `ssh_key` and `ssh_port`.
		- `scp`: simple fallback; uses the same `rsync_target`.
	- Turn on with `cloud_sync.enabled: true`, then run `sudo bash enable_auto_start.sh` to (re)create/enable the timer.
	- Interval: prefer `cloud_sync.interval_seconds` (e.g., 10 for fast checks). If not set, falls back to `cloud_sync.interval_minutes` (default: 10).
	- Logs: `logs/cloud_sync.log`.
	- See `docs/cloud_sync_google_drive.md` for a step‑by‑step Google Drive setup (online and offline‑friendly).

9. **Troubleshooting**
	- Use **Force Stop Logging** to terminate stuck processes.
	- Use **System Status** to check permissions and system health.
	- For common issues, refer to the SOP.

---

**For detailed instructions, wiring diagrams, and troubleshooting, refer to the full SOP document.**

## Notes on code layout and cleanup

- Core modules are grouped under `legacy_core/` (macros, meter_device, meter_manager, mqtt_client, and meter drivers).
- The previous `src/offline_dashboard/` package and duplicate root modules were removed to avoid confusion.
- Entry points remain the same:
	- `simple_meter_ui.py` for the Technician UI
	- `simple_rpi_dashboard.py` for CLI setup/run/service
- The old offline debug scripts and USB auto-copy service have been removed.
 - USB auto-copy and Cloud Sync are provided as standalone services:
	- `usb_csv_auto_copy.service` watches for USB drives and copies CSVs.
	- `cloud_sync.timer` triggers `cloud_sync.service` to push data when online.
