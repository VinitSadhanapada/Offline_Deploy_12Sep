#!/usr/bin/env python3
"""
Simple RPi Auto-Startup Dashboard - All-in-One Solution

This single script handles:
- Automatic venv setup and dependency installation
- Auto-startup configuration (systemd service)
- Headless operation with CSV logging
- Status monitoring and control

Usage:
    python3 simple_rpi_dashboard.py --setup      # Initial setup
    python3 simple_rpi_dashboard.py --install    # Install auto-startup
    python3 simple_rpi_dashboard.py --run        # Run dashboard
    python3 simple_rpi_dashboard.py --status     # Check status
    python3 simple_rpi_dashboard.py --stop       # Stop dashboard

Author: Simplified approach
Date: 24/07/25
"""

import os
import sys
import subprocess
import argparse
import json
import time
import signal
import logging
from pathlib import Path
from datetime import datetime

# Import shared venv utilities
from venv_utils import (
    setup_complete_venv_environment,
    setup_venv_with_pip,
    install_packages_in_venv,
)


def auto_use_venv_if_needed():
    """
    Automatically restart with venv Python if:
    1. We're not already running in venv
    2. venv exists
    3. We're trying to run the dashboard (--run)
    """
    script_dir = Path(__file__).parent.absolute()
    venv_python = script_dir / "venv" / "bin" / "python"

    # Check if we're already in venv by checking sys.executable
    if venv_python.exists() and str(venv_python) != sys.executable:
        # Check if this is a run command
        if len(sys.argv) > 1 and any(arg in ['--run', '--run-service'] for arg in sys.argv):
            print("🔄 Auto-switching to virtual environment...")
            print(f"   Using: {venv_python}")
            # Re-execute with venv python
            os.execv(str(venv_python), [str(venv_python)] + sys.argv)

    return False  # Not using venv or venv doesn't exist


def check_sudo_available():
    """Check if sudo is available and user has sudo access."""
    # If we're already running as root, we don't need sudo
    if os.geteuid() == 0:
        return True

    try:
        result = subprocess.run(["sudo", "-n", "true"],
                                capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def require_sudo_for_command(command_name):
    """Check if running with appropriate permissions for systemd operations."""
    if os.geteuid() != 0 and not check_sudo_available():
        print(
            f"❌ Error: '{command_name}' requires sudo access for systemd operations.")
        print("")
        print("💡 Solutions:")
        print("1. Run with sudo:")
        print(f"   sudo python3 {os.path.basename(__file__)} {command_name}")
        print("")
        print("2. Add user to sudo group:")
        print("   sudo usermod -aG sudo $USER")
        print("   # Then logout and login again")
        print("")
        print("3. For passwordless sudo (optional):")
        print("   sudo visudo")
        print("   # Add line: pi ALL=(ALL) NOPASSWD: /bin/systemctl")
        print("")
        return False
    return True


def check_user_permissions():
    """Check and display current user permissions."""
    user = os.getenv('USER', 'unknown')
    uid = os.getuid()

    print(f"👤 Current user: {user} (UID: {uid})")

    # Check if user is in dialout group (needed for serial ports)
    try:
        import grp
        dialout_group = grp.getgrnam('dialout')
        if user in dialout_group.gr_mem:
            print("✅ User is in 'dialout' group (serial port access)")
        else:
            print("⚠️ User NOT in 'dialout' group - serial ports may not work")
            print("   Fix: sudo usermod -aG dialout $USER")
    except KeyError:
        print("⚠️ 'dialout' group not found on this system")

    # Check sudo access
    if check_sudo_available():
        print("✅ Sudo access available")
    else:
        print("⚠️ No sudo access - service management will require manual sudo")

    print("")


# Minimal local utilities (we removed the old src/offline_dashboard package)
from typing import Any, Dict, List
import re as _re

def _strip_jsonc_comments(text: str) -> str:
    text = _re.sub(r"//.*", "", text)
    text = _re.sub(r"/\*.*?\*/", "", text, flags=_re.DOTALL)
    return text

def load_jsonc_config(path: Path) -> Any:
    with open(path, "r") as f:
        import json as _json
        return _json.loads(_strip_jsonc_comments(f.read()))

def _normalize_device_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(d, dict):
        return {}
    name = d.get("name") or d.get("meter_name") or d.get("device_name") or ""
    addr_raw = (
        d.get("address") if "address" in d else d.get("meter_address") if "meter_address" in d else d.get("device_id")
    )
    try:
        address = int(addr_raw) if addr_raw is not None else None
    except Exception:
        address = None
    model = d.get("model") or d.get("meter_model") or d.get("type") or ""
    location = d.get("location") or d.get("site") or d.get("plant") or "Unknown"
    merged = dict(d)
    if name:
        merged["name"] = name
    if address is not None:
        merged["address"] = address
    merged.setdefault("model", model)
    merged.setdefault("location", location)
    return merged

def _load_device_config(config_path: Path) -> List[Dict[str, Any]]:
    data = load_jsonc_config(config_path)
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = None
        for key in ("devices", "meters", "items"):
            v = data.get(key)
            if isinstance(v, list):
                items = v
                break
        if items is None:
            return []
    else:
        return []
    result: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            result.append(_normalize_device_keys(item))
    return result

# Defaults (used if no config files are found)
_DEFAULT_CONFIG = {
    "SIMULATION_MODE": False,
    "READING_INTERVAL": 10,
    "INTER_DEVICE_DELAY": 0.1,
    "PORT": "/dev/ttyUSB0",
    "ENABLE_MQTT": False,
    "ENABLE_RTC": True,
    "LOG_LEVEL": "INFO",
}
_DEFAULT_DEVICES = [
    {"name": "SP3 UPS", "address": 1, "model": "LG6400"},
    {"name": "Suryakund UPS", "address": 2, "model": "LG+5220"},
]

# Prefer configuration files at /home/pi/meter_config, then local copies
_CONFIG_DIR = Path("/home/pi/meter_config")
_SCRIPT_DIR = Path(__file__).parent.absolute()
_config_candidates = [
    _CONFIG_DIR / "config.json",
    _SCRIPT_DIR / "config.json",
]
_device_candidates = [
    _CONFIG_DIR / "device_config.json",
    _SCRIPT_DIR / "device_config.json",
]

def _first_existing(paths):
    for p in paths:
        if Path(p).exists():
            return Path(p)
    return None

_cfg_path = _first_existing(_config_candidates)
_dev_path = _first_existing(_device_candidates)

try:
    CONFIG = load_jsonc_config(_cfg_path) if _cfg_path else dict(_DEFAULT_CONFIG)
except Exception:
    CONFIG = dict(_DEFAULT_CONFIG)
try:
    DEVICE_CONFIG = _load_device_config(_dev_path) if _dev_path else list(_DEFAULT_DEVICES)
    if not DEVICE_CONFIG:
        DEVICE_CONFIG = list(_DEFAULT_DEVICES)
except Exception:
    DEVICE_CONFIG = list(_DEFAULT_DEVICES)

def _build_required_packages_for_version(major: int, minor: int):
    """Select package pins compatible with a specific Python version.
    - For Python < 3.13: use numpy==1.26.4, pandas==2.0.3
    - For Python >= 3.13: use numpy>=2.1,<3, pandas>=2.2,<3
    """
    base = [
        "pymodbus==2.5.3",
        "pyserial==3.5",
        "paho-mqtt==2.1.0",
        "termcolor==3.1.0",
    ]
    if (major, minor) >= (3, 13):
        base += [
            "numpy>=2.1,<3",
            "pandas>=2.2,<3",
        ]
    else:
        base += [
            "numpy==1.26.4",
            "pandas==2.0.3",
        ]
    return base


class SimpleDashboard:
    """All-in-one dashboard manager."""

    def __init__(self):
        self.script_dir = Path(__file__).resolve().parent
        # Determine project root: if running from scripts/, use parent; else current
        if (self.script_dir / "config.json").exists():
            self.project_root = self.script_dir
        elif (self.script_dir.parent / "config.json").exists():
            self.project_root = self.script_dir.parent
        else:
            # Fallback to script dir
            self.project_root = self.script_dir
        self.venv_dir = self.project_root / "venv"
        self.log_dir = self.project_root / "logs"
        self.csv_dir = self.project_root / "data" / "csv"
        self.service_name = "meter-dashboard"

    def setup_logging(self):
        """Setup logging."""
        from logging import FileHandler, StreamHandler
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.log_dir / f"dashboard_{datetime.now().strftime('%Y%m%d')}.log"

        handlers = []
        # Always at least log to console/journal
        handlers.append(StreamHandler())

        # Try to add a file handler; fall back gracefully on permission errors
        file_handler_added = False
        try:
            fh = FileHandler(log_file)
            handlers.insert(0, fh)  # file first, then stream
            file_handler_added = True
        except Exception as e:
            # Attempt to fall back to /tmp if primary log directory is not writable
            try:
                tmp_fallback = Path("/tmp") / log_file.name
                fh = FileHandler(tmp_fallback)
                handlers.insert(0, fh)
                print(f"⚠️ Cannot write to {log_file}: {e}. Using fallback log: {tmp_fallback}")
                file_handler_added = True
            except Exception as e2:
                print(f"⚠️ File logging disabled (permission error). Streaming logs only. Error: {e2}")

        logging.basicConfig(
            level=getattr(logging, CONFIG["LOG_LEVEL"]),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=handlers,
        )
        self.logger = logging.getLogger(__name__)
        if not file_handler_added:
            try:
                self.logger.warning("File logging is disabled due to permission issues; logs available in journal only.")
            except Exception:
                pass

    def run_command(self, cmd, check=True, shell=False):
        """Run a system command."""
        try:
            if isinstance(cmd, str) and not shell:
                cmd = cmd.split()
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=check, shell=shell)
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.CalledProcessError as e:
            return False, e.stdout, e.stderr

    def check_prerequisites(self):
        """Check system prerequisites and provide guidance."""
        print("🔍 Checking System Prerequisites...")
        print("=" * 50)

        issues_found = False

        # Check if running on Linux
        if os.name != 'posix':
            print("⚠️  This script is designed for Linux/Raspberry Pi systems")
            print("   Current OS detected:", os.name)
            issues_found = True
        else:
            print("✅ Running on Linux/Unix system")

        # Check Python version
        python_version = sys.version_info
        if python_version.major >= 3 and python_version.minor >= 7:
            print(
                f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
        else:
            print(
                f"⚠️  Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
            print("   Recommended: Python 3.7 or higher")
            issues_found = True

        # Check if user is in dialout group
        current_user = os.getenv('USER', 'unknown')
        print(f"👤 Current user: {current_user}")

        try:
            # grp module is only available on Unix-like systems
            if os.name == 'posix':
                import grp
                dialout_group = grp.getgrnam('dialout')
                if current_user in dialout_group.gr_mem:
                    print("✅ User is in 'dialout' group (serial port access)")
                else:
                    print("❌ User NOT in 'dialout' group")
                    print("   Fix: sudo usermod -a -G dialout $USER")
                    print("   Then: sudo reboot")
                    issues_found = True
            else:
                print("ℹ️  Group checking not available on this platform")
        except (KeyError, ImportError):
            print("⚠️  'dialout' group not found or grp module unavailable")

        # Check for required system packages
        required_packages = ['python3-venv', 'python3-pip']
        print("\n🔍 Checking system packages...")

        for package in required_packages:
            success, stdout, stderr = self.run_command(
                ['dpkg', '-l', package], check=False)
            if success and package in stdout:
                print(f"✅ {package} is installed")
            else:
                print(f"❌ {package} is NOT installed")
                print(f"   Fix: sudo apt install {package} -y")
                issues_found = True

        # Check systemd
        if Path('/etc/systemd/system').exists():
            print("✅ systemd is available")
        else:
            print("⚠️  systemd not found - will use crontab fallback")

        # Check venv module
        success, stdout, stderr = self.run_command(
            [sys.executable, '-m', 'venv', '--help'], check=False)
        if success:
            print("✅ venv module is available")
        else:
            print("❌ venv module not available")
            print("   Fix: sudo apt install python3-venv")
            issues_found = True

        # Check pip availability
        success, stdout, stderr = self.run_command(
            [sys.executable, '-m', 'pip', '--version'], check=False)
        if success:
            print("✅ pip is available")
        else:
            print("❌ pip not available")
            print("   Fix: sudo apt install python3-pip")
            issues_found = True

        print("\n" + "=" * 50)

        if issues_found:
            print("❌ Issues found! Please fix the above problems before proceeding.")
            print("\n📋 Quick fix commands:")
            print("sudo apt update")
            print("sudo apt install python3-venv python3-pip -y")
            print("sudo usermod -a -G dialout $USER")
            print("sudo reboot")
            return False
        else:
            print("✅ All prerequisites met! You can proceed with setup.")
            print("\n🚀 Next steps:")
            print("1. python3 simple_rpi_dashboard.py --setup")
            print("2. python3 simple_rpi_dashboard.py --create-service")
            return True

    def create_service_only(self):
        """Create systemd service file only (requires sudo)."""
        print("🔧 Creating systemd service file...")

        if not self.venv_dir.exists():
            print("❌ Virtual environment not found.")
            print("   Run: python3 simple_rpi_dashboard.py --setup")
            return False

        # Check if running with appropriate permissions
        if os.geteuid() != 0 and not check_sudo_available():
            print("❌ This operation requires sudo access.")
            print("💡 Run with sudo or ensure user has sudo privileges:")
            print(
                f"   sudo python3 {os.path.basename(__file__)} --create-service")
            return False

        return self.create_systemd_service()

    def setup_environment(self):
        """Setup virtual environment and install dependencies using shared utilities."""
        print("🔧 Setting up environment...")

        # Check if offline packages are available (support multiple common locations)
        # Resolve relative to the project root to be robust regardless of CWD
        offline_dir = None
        candidate_dirs = [
        self.project_root / "offline_packages",
        self.project_root / "vendor" / "packages",
        self.project_root / "packages_folder",
        ]
        for offline_path in candidate_dirs:
            if offline_path.exists() and (list(offline_path.glob("*.whl")) or list(offline_path.glob("*.tar.gz"))):
                print(f"🔍 Found offline packages at: {offline_path}")
                offline_dir = str(offline_path)
                break

        # Prefer the current interpreter (3.13+ on modern RPi) and do NOT downgrade to 3.11.
        # We ship cp313 wheels and pin modern versions for >=3.13 in _build_required_packages_for_version.
        preferred_python = None  # let setup_venv_with_pip use the invoking interpreter

        # Do not force-recreate a working venv just because it's on 3.13+.
        # Recreate only if explicitly requested by caller.
        force_recreate = False

        # (Preflight removed) We'll do wheel tag checks after venv creation using the venv interpreter.

        # 1) Create the venv first using the preferred interpreter
        success, python_exe = setup_venv_with_pip(self.venv_dir, force_recreate, preferred_python)
        if not success:
            return False

        # Determine the venv interpreter version to choose correct pins
        ver_ok, ver_out, _ = self.run_command([str(python_exe), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], check=False)
        venv_ver = ver_out.strip() if ver_ok else f"{sys.version_info.major}.{sys.version_info.minor}"
        try:
            maj, minr = map(int, venv_ver.split(".")[:2])
        except Exception:
            maj, minr = sys.version_info.major, sys.version_info.minor
        required_packages = _build_required_packages_for_version(maj, minr)

        # Optional: After venv exists, re-check numpy wheel tag compatibility against venv python
        try:
            if offline_dir:
                from pathlib import Path as _P
                import re as _re
                vtag_ok, vtag_out, _ = self.run_command([str(python_exe), "-c", "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}')"], check=False)
                target_py = vtag_out.strip() if vtag_ok else f"cp{maj}{minr}"
                offline_path = _P(offline_dir)
                numpy_wheels = list(offline_path.glob('numpy-*.whl'))
                if numpy_wheels:
                    def _wheel_py_tags(name: str):
                        return [p for p in name.split('-') if _re.fullmatch(r"cp\d{2,3}", p)]
                    available_tags = sorted({t for f in numpy_wheels for t in _wheel_py_tags(f.name)})
                    if available_tags and target_py not in available_tags:
                        import platform as _platform
                        arch = _platform.machine()
                        print("⚠️ Offline numpy wheels found but none match the target interpreter.")
                        print(f"   Available numpy wheel python tags: {', '.join(available_tags)}")
                        print(f"   Current/target interpreter tag: {target_py}")
                        plat_hint = "manylinux_2_17_aarch64.manylinux2014_aarch64" if arch == 'aarch64' else ("linux_armv7l" if arch.startswith('arm') else "manylinux")
                        print(f"💡 Add: numpy wheel built for {target_py}, e.g.: numpy-<ver>-{target_py}-{target_py}-{plat_hint}.whl")
        except Exception:
            pass

        # 2) Install packages into the created venv (offline aware)
        if not install_packages_in_venv(python_exe, required_packages, offline_dir):
            print("❌ Environment setup failed")
            return False

        # Create additional directories
        self.log_dir.mkdir(exist_ok=True)
        self.csv_dir.mkdir(exist_ok=True)

        print("✅ Environment setup complete")
        return True

    def create_systemd_service(self):
        """Create systemd service for auto-startup."""
        # Determine appropriate service user: prefer the invoking sudo user, then current user
        svc_user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "pi"
        # Final sanity: basic username characters only
        import re as _re_user
        if not _re_user.fullmatch(r"[A-Za-z0-9._-]+", svc_user or ""):
            svc_user = "pi"

        service_content = f"""[Unit]
Description=Meter Reading Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={svc_user}
WorkingDirectory={self.project_root}
ExecStart={self.venv_dir}/bin/python {Path(__file__).resolve()} --run
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

        service_file = f"/etc/systemd/system/{self.service_name}.service"

        try:
            # Write service file directly if running as root, otherwise use sudo
            if os.geteuid() == 0:
                # Running as root - write directly
                with open(service_file, "w") as f:
                    f.write(service_content)
                success = True
                stderr = ""
            else:
                # Not root - use sudo
                with open("/tmp/dashboard.service", "w") as f:
                    f.write(service_content)

                success, stdout, stderr = self.run_command([
                    "sudo", "cp", "/tmp/dashboard.service", service_file
                ])

            if not success:
                print(f"❌ Failed to create service file: {stderr}")
                return False

            # Enable and start service (use sudo if not root)
            if os.geteuid() == 0:
                self.run_command(["systemctl", "daemon-reload"])
                self.run_command(["systemctl", "enable", self.service_name])
            else:
                self.run_command(["sudo", "systemctl", "daemon-reload"])
                self.run_command(
                    ["sudo", "systemctl", "enable", self.service_name])

            print(
                f"✅ Systemd service '{self.service_name}' created and enabled")
            print("   The dashboard will start automatically on boot")
            return True

        except Exception as e:
            print(f"❌ Error creating systemd service: {e}")
            return False

    def install_auto_startup(self):
        """Install auto-startup service."""
        if not self.venv_dir.exists():
            print("❌ Virtual environment not found. Run --setup first.")
            return False

        print("🚀 Installing auto-startup service...")

        # Check if we're on a systemd system
        if Path("/etc/systemd/system").exists():
            return self.create_systemd_service()
        else:
            # Fallback to crontab
            return self.install_crontab()

    def install_crontab(self):
        """Fallback: Install crontab entry."""
        cron_entry = f"@reboot sleep 60 && cd {self.script_dir} && {self.venv_dir}/bin/python {__file__} --run"

        # Get current crontab
        success, current_cron, _ = self.run_command(
            ["crontab", "-l"], check=False)

        if not success or cron_entry not in current_cron:
            # Add new entry
            new_cron = current_cron + "\n" + cron_entry if success else cron_entry

            # Write to temp file and install
            with open("/tmp/new_crontab", "w") as f:
                f.write(new_cron)

            success, stdout, stderr = self.run_command(
                ["crontab", "/tmp/new_crontab"])
            os.unlink("/tmp/new_crontab")

            if success:
                print("✅ Crontab entry added")
                return True
            else:
                print(f"❌ Failed to add crontab entry: {stderr}")
                return False
        else:
            print("✅ Crontab entry already exists")
            return True

    def run_dashboard(self):
        """Run the main dashboard."""
        if not self.venv_dir.exists():
            print("❌ Virtual environment not found. Run --setup first.")
            return False

        self.setup_logging()
        self.logger.info("Starting dashboard in headless mode...")

        # Setup signal handlers
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}. Shutting down...")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Import modules (support both new package layout and legacy flat files)
            # Ensure project root is on path
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))

            # Import helpers from legacy_core if available, otherwise use flat-root modules
            def setup_modbus_client(config, logger=None):
                """
                Build a Modbus client and determine simulation mode.
                IMPORTANT: Do NOT force simulation mode on failures when the config explicitly disables it.
                If SIMULATION_MODE is False and hardware is unavailable, return (client=None, sim_mode=False) and let reads fail gracefully (no random data).
                """
                desired_sim = bool(config.get("SIMULATION_MODE", False))
                try:
                    from pymodbus.client.sync import ModbusSerialClient as ModbusClient
                except Exception as e:
                    if logger:
                        logger.error(f"Failed to import pymodbus: {e}")
                    # Honor user preference: only simulate if explicitly requested
                    return None, desired_sim, False
                port = config.get("PORT", "")
                import os
                if not port or not os.path.exists(port):
                    if logger:
                        logger.warning(f"Port {port} not found; simulation_mode={'ON' if desired_sim else 'OFF'} (honoring config)")
                    return None, desired_sim, False
                try:
                    client = ModbusClient(method="rtu", port=port, stopbits=1, bytesize=8, parity='E', baudrate=9600, timeout=0.5)
                    if client.connect():
                        # Connected: use configured simulation flag (usually False)
                        return client, desired_sim, False
                    if logger:
                        logger.warning("Modbus client connect() failed; not simulating unless configured")
                    return None, desired_sim, False
                except Exception as e:
                    if logger:
                        logger.warning(f"Error creating Modbus client: {e}; not simulating unless configured")
                    return None, desired_sim, False

            try:
                # Prefer grouped legacy modules
                from legacy_core.macros import PARAMETERS  # type: ignore

                def init_mqtt_if_enabled(config):
                    if not config.get("ENABLE_MQTT"):
                        return None
                    from legacy_core import mqtt_client as _mqtt  # type: ignore
                    _mqtt.mqtt_main()
                    return _mqtt

                def build_meters(parameters, devices, client, simulation_mode):
                    from legacy_core.meter_device import MeterDevice  # type: ignore
                    meters = []
                    for i, dev in enumerate(devices):
                        name = dev.get("name", f"Meter_{i+1}")
                        addr = dev.get("address", i+1)
                        model = dev.get("model", "")
                        m = MeterDevice(name=name, model=model, parameters=parameters, client=client, error_file=None, simulation_mode=simulation_mode, device_address=addr)
                        meters.append(m)
                    return meters

                def create_manager(meters, parameters, csv_path, mqtt_module, publish):
                    from legacy_core.meter_manager import MeterManager  # type: ignore
                    return MeterManager(meters, parameters, [str(csv_path)], mqtt_client=mqtt_module if publish else None, publish_mqtt=bool(publish))
            except Exception:
                # Final fallback to flat root modules
                from macros import PARAMETERS  # type: ignore

                def init_mqtt_if_enabled(config):
                    if not config.get("ENABLE_MQTT"):
                        return None
                    import mqtt_client as _mqtt
                    _mqtt.mqtt_main()
                    return _mqtt

                def build_meters(parameters, devices, client, simulation_mode):
                    from meter_device import MeterDevice
                    meters = []
                    for i, dev in enumerate(devices):
                        name = dev.get("name", f"Meter_{i+1}")
                        addr = dev.get("address", i+1)
                        model = dev.get("model", "")
                        m = MeterDevice(name=name, model=model, parameters=parameters, client=client, error_file=None, simulation_mode=simulation_mode, device_address=addr)
                        meters.append(m)
                    return meters

                def create_manager(meters, parameters, csv_path, mqtt_module, publish):
                    from meter_manager import MeterManager
                    return MeterManager(meters, parameters, [str(csv_path)], mqtt_client=mqtt_module if publish else None, publish_mqtt=bool(publish))

            self.logger.info("Modules imported successfully")

            # Initialize RTC for offline time keeping
            if CONFIG["ENABLE_RTC"]:
                self.logger.info(
                    "Initializing RTC system for offline time keeping...")
                try:
                    from rtc_manager import RTCManager
                    rtc_manager = RTCManager(logger=self.logger)

                    if rtc_manager.initialize_for_offline_operation():
                        self.logger.info(
                            "✅ RTC system ready for offline operation")
                    else:
                        self.logger.warning(
                            "⚠️ RTC initialization failed - using system time only")
                except Exception as e:
                    self.logger.warning(
                        f"⚠️ RTC initialization error: {e} - using system time only")
            else:
                self.logger.info("RTC disabled - using system time only")

            # Initialize hardware via shared helper
            client, sim_mode, _use_default = setup_modbus_client(CONFIG, logger=self.logger)
            # Preserve user's simulation preference; setup_modbus_client already honored it
            CONFIG["SIMULATION_MODE"] = sim_mode

            # Initialize MQTT
            mqtt = init_mqtt_if_enabled(CONFIG)

            # Create devices and manager
            # Use a single consolidated CSV file for the entire deployment (no daily rotation)
            self.csv_dir.mkdir(parents=True, exist_ok=True)
            csv_file = self.csv_dir / "readings_all.csv"
            csv_files = [str(csv_file)]
            meters = build_meters(PARAMETERS, DEVICE_CONFIG, client, CONFIG.get("SIMULATION_MODE", False))
            manager = create_manager(meters, PARAMETERS, csv_file, mqtt, CONFIG.get("ENABLE_MQTT", False))

            self.logger.info(f"Dashboard started with {len(meters)} devices")

            # Main loop: never exit on read errors; log and retry
            while True:
                try:
                    manager.read_all(
                        inter_device_delay=CONFIG["INTER_DEVICE_DELAY"])

                    if manager.TotalReadings % 10 == 0:
                        self.logger.info(
                            f"Completed {manager.TotalReadings} reading cycles")
                except Exception as e:
                    import traceback as _tb
                    self.logger.error(f"Read cycle error: {e}")
                    self.logger.debug(_tb.format_exc())
                    # Backoff briefly before retrying to avoid busy-loop
                    time.sleep(5)
                else:
                    time.sleep(CONFIG["READING_INTERVAL"])

        except Exception as e:
            import traceback
            self.logger.error(f"Dashboard error: {e}")
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    def check_status(self):
        """Check dashboard status."""
        print("📊 Dashboard Status")
        print("=" * 40)

        # Check if service is running
        success, stdout, stderr = self.run_command(["systemctl", "is-active", self.service_name], check=False)
        if success and "active" in stdout:
            print("✅ Service: Running")
        else:
            print("❌ Service: Not running")

        # Check for manually running processes
        success, stdout, stderr = self.run_command(["pgrep", "-f", "simple_rpi_dashboard.py --run"], check=False)
        if success and stdout.strip():
            pids = stdout.strip().split('\n')
            print(f"🔄 Manual processes: {len(pids)} running")
            for pid in pids:
                if pid.strip():
                    print(f"   PID: {pid.strip()}")
        else:
            print("⭕ Manual processes: None running")

        # Check venv
        if self.venv_dir.exists():
            print("✅ Virtual environment: Ready")
        else:
            print("❌ Virtual environment: Not found")

        # Check logs
        if self.log_dir.exists():
            log_files = list(self.log_dir.glob("*.log"))
            print(f"📁 Log files: {len(log_files)} found")
            if log_files:
                latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
                print(f"   Latest: {latest_log.name}")

        # Check CSV data
        if self.csv_dir.exists():
            csv_files = list(self.csv_dir.glob("*.csv"))
            print(f"📈 CSV files: {len(csv_files)} found")

        print("=" * 40)

    def stop_dashboard(self):
        """Stop the dashboard service and any running processes."""
        print("🛑 Stopping dashboard...")

        # First, try to stop the systemd service
        success, stdout, stderr = self.run_command(
            ["sudo", "systemctl", "stop", self.service_name], check=False)
        if success:
            print("✅ Dashboard service stopped")
        else:
            print(f"⚠️ Service stop result: {stderr}")

        # Also kill any manually running dashboard processes
        print("🔍 Checking for running dashboard processes...")
        success, stdout, stderr = self.run_command(
            ["pgrep", "-f", "simple_rpi_dashboard.py --run"], check=False)

        if success and stdout.strip():
            print("🔄 Found running dashboard processes, stopping them...")
            pids = stdout.strip().split('\n')
            for pid in pids:
                if pid.strip():
                    print(f"   Stopping process {pid.strip()}")
                    self.run_command(
                        ["kill", "-TERM", pid.strip()], check=False)

            # Wait a moment, then force kill if still running
            time.sleep(2)
            success2, stdout2, stderr2 = self.run_command(
                ["pgrep", "-f", "simple_rpi_dashboard.py --run"], check=False)
            if success2 and stdout2.strip():
                print("🔨 Force stopping remaining processes...")
                pids2 = stdout2.strip().split('\n')
                for pid in pids2:
                    if pid.strip():
                        self.run_command(
                            ["kill", "-KILL", pid.strip()], check=False)

            print("✅ All dashboard processes stopped")
        else:
            print("ℹ️ No running dashboard processes found")

    def view_logs(self):
        """View recent dashboard logs."""
        print("📋 Recent Dashboard Logs")
        print("=" * 40)

        if not self.log_dir.exists():
            print("❌ No log directory found")
            return

        log_files = list(self.log_dir.glob("*.log"))
        if not log_files:
            print("❌ No log files found")
            return

        # Get the most recent log file
        latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
        print(f"📁 Showing last 50 lines from: {latest_log.name}")
        print("-" * 40)

        try:
            with open(latest_log, 'r') as f:
                lines = f.readlines()
                for line in lines[-50:]:  # Show last 50 lines
                    print(line.rstrip())
        except Exception as e:
            print(f"❌ Error reading log file: {e}")

    def start_service(self):
        """Start the dashboard service."""
        print("🚀 Starting dashboard service...")

        success, stdout, stderr = self.run_command(
            ["sudo", "systemctl", "start", self.service_name], check=False)
        if success:
            print("✅ Dashboard service started")
            time.sleep(2)  # Wait a moment
            self.check_status()
        else:
            print(f"❌ Failed to start service: {stderr}")

    def restart_service(self):
        """Restart the dashboard service."""
        print("🔄 Restarting dashboard service...")

        success, stdout, stderr = self.run_command(
            ["sudo", "systemctl", "restart", self.service_name], check=False)
        if success:
            print("✅ Dashboard service restarted")
            time.sleep(2)  # Wait a moment
            self.check_status()
        else:
            print(f"❌ Failed to restart service: {stderr}")

    def uninstall_service(self):
        """Uninstall the dashboard service."""
        print("🗑️ Uninstalling dashboard service...")

        # Stop and disable service
        self.run_command(["sudo", "systemctl", "stop",
                         self.service_name], check=False)
        self.run_command(["sudo", "systemctl", "disable",
                         self.service_name], check=False)

        # Remove service file
        service_file = f"/etc/systemd/system/{self.service_name}.service"
        success, stdout, stderr = self.run_command(
            ["sudo", "rm", "-f", service_file], check=False)

        if success:
            self.run_command(
                ["sudo", "systemctl", "daemon-reload"], check=False)
            print("✅ Dashboard service uninstalled")
        else:
            print(f"❌ Failed to remove service file: {stderr}")


def main():
    """Main entry point."""
    # Auto-switch to venv if needed for --run commands
    auto_use_venv_if_needed()

    parser = argparse.ArgumentParser(
        description="Simple RPi Dashboard Manager")
    parser.add_argument("--check-prereq", action="store_true",
                        help="Check prerequisites and permissions")
    parser.add_argument("--setup", action="store_true",
                        help="Setup environment (venv + packages + directories)")
    parser.add_argument("--create-service", action="store_true",
                        help="Create systemd service file (requires sudo)")
    parser.add_argument("--install", action="store_true",
                        help="Full install: setup + create service (requires sudo)")
    parser.add_argument("--run", action="store_true", help="Run dashboard")
    parser.add_argument("--force-mqtt", action="store_true", help="Force-enable MQTT publishing during run (overrides config)")
    parser.add_argument("--run-service", action="store_true",
                        help="Run dashboard as service (used by systemd)")
    parser.add_argument("--status", action="store_true", help="Check status")
    parser.add_argument("--stop", action="store_true", help="Stop dashboard")
    parser.add_argument("--logs", action="store_true", help="View logs")
    parser.add_argument("--start", action="store_true", help="Start service")
    parser.add_argument("--restart", action="store_true",
                        help="Restart service")
    parser.add_argument("--uninstall", action="store_true",
                        help="Uninstall service")

    args = parser.parse_args()
    dashboard = SimpleDashboard()

    if args.check_prereq:
        dashboard.check_prerequisites()
    elif args.setup:
        dashboard.setup_environment()
    elif args.create_service:
        dashboard.create_service_only()
    elif args.install:
        # Full installation: setup + service creation
        print("🚀 Full installation starting...")
        if dashboard.setup_environment():
            dashboard.create_service_only()
    elif args.run or args.run_service:
        # Both --run and --run-service do the same thing
        script_dir = Path(__file__).parent.absolute()
        venv_dir = script_dir / "venv"

        if not venv_dir.exists():
            print("❌ Virtual environment not found!")
            print("🔧 Please run setup first:")
            print("   python3 simple_rpi_dashboard.py --setup")
            print("   python3 simple_rpi_dashboard.py --create-service")
            print("")
            print("💡 Or use the quick install:")
            print("   python3 simple_rpi_dashboard.py --install")
            sys.exit(1)

        # Optional: force-enable MQTT regardless of config when requested
        if getattr(args, "force_mqtt", False):
            try:
                CONFIG["ENABLE_MQTT"] = True
                print("🔔 MQTT publish forced ON via --force-mqtt flag")
            except Exception:
                pass

        dashboard.run_dashboard()
    elif args.status:
        dashboard.check_status()
    elif args.stop:
        dashboard.stop_dashboard()
    elif args.logs:
        dashboard.view_logs()
    elif args.start:
        dashboard.start_service()
    elif args.restart:
        dashboard.restart_service()
    elif args.uninstall:
        dashboard.uninstall_service()
    else:
        print("🔌 Simple RPi Dashboard Manager")
        print("\n📋 Prerequisites Check:")
        print("  python3 simple_rpi_dashboard.py --check-prereq   # Check system prerequisites")
        print("\n🔧 Setup Commands:")
        print("  python3 simple_rpi_dashboard.py --setup          # Setup environment only (no sudo)")
        print("  python3 simple_rpi_dashboard.py --create-service # Create service file (requires sudo)")
        print("  python3 simple_rpi_dashboard.py --install        # Full setup + service (requires sudo)")
        print("\n▶️  Running:")
        print("  python3 simple_rpi_dashboard.py --run            # Run dashboard manually (auto-uses venv)")
        print("  python3 simple_rpi_dashboard.py --status         # Check service status")
        print("")
        print("💡 Note: --run automatically uses virtual environment if available")
        print("\n🔧 Service Management:")
        print("  python3 simple_rpi_dashboard.py --start          # Start service")
        print("  python3 simple_rpi_dashboard.py --stop           # Stop service")
        print("  python3 simple_rpi_dashboard.py --restart        # Restart service")
        print("  python3 simple_rpi_dashboard.py --logs           # View logs")
        print("  python3 simple_rpi_dashboard.py --uninstall      # Remove service")
        print("\n📖 For manual setup without sudo prompts, see: docs/MANUAL_SETUP.md")


if __name__ == "__main__":
    main()
