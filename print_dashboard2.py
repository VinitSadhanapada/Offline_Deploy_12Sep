"""Continuous Meter Reading Dashboard with MQTT Integration.

This module provides a console dashboard that reads meter devices,
logs CSV, and can publish to MQTT. It prefers the grouped
`legacy_core` package and falls back to the legacy flat layout.
"""

import sys
import time
import os
import platform
from pathlib import Path
from datetime import datetime

# Prefer legacy_core imports; then legacy flat root imports
# Ensure project root on path for legacy layout
this_dir = Path(__file__).resolve().parent
project_root_guess = this_dir if (this_dir / "config.jsonc").exists() else this_dir.parent
if str(project_root_guess) not in sys.path:
    sys.path.insert(0, str(project_root_guess))
try:
    from legacy_core.meter_device import MeterDevice  # type: ignore
    from legacy_core.meter_manager import MeterManager  # type: ignore
    from legacy_core.macros import DEVICE_NAMES, PARAMETERS  # type: ignore
    from legacy_core import mqtt_client as mqtt  # type: ignore
except Exception:
    from meter_device import MeterDevice
    from meter_manager import MeterManager
    from macros import DEVICE_NAMES, PARAMETERS
    import mqtt_client as mqtt

# Optional venv utilities
try:
    from venv_utils import setup_complete_venv_environment
    VENV_UTILS_AVAILABLE = True
except Exception:
    VENV_UTILS_AVAILABLE = False

# Configuration
SIMULATION_MODE = False
READING_INTERVAL = 10
PUBLISH_MQTT = False
REFRESH_INTERVAL = 5

# Device Configuration - customize as needed
DEVICE_CONFIG = [
    {"name": "Main Panel", "address": 1, "model": "LG6400"}
]

# Derive device names and ensure macros stays consistent
DEVICE_NAMES = [d["name"] for d in DEVICE_CONFIG]
try:
    # try to update macros if available (prefer legacy_core)
    try:
        from legacy_core import macros as _macros  # type: ignore
    except Exception:
        import macros as _macros
    _macros.DEVICE_NAMES = DEVICE_NAMES
except Exception:
    pass

# Determine project root and prepare dirs early (MQTT and logs depend on this)
script_dir = Path(__file__).resolve().parent
project_root = script_dir if (script_dir / "config.jsonc").exists() else script_dir.parent
logs_dir = project_root / "logs"
csv_dir = project_root / "data" / "csv"
os.makedirs(csv_dir, exist_ok=True)
os.makedirs(logs_dir, exist_ok=True)

# Prepare CSV filenames for today's run
timestamp = datetime.now().strftime("%Y%m%d")
csv_filenames = []
for device in DEVICE_CONFIG:
    clean_name = "".join(c for c in device["name"] if c.isalnum() or c in ('-', '_'))
    filename = str(csv_dir / f"{clean_name}_{timestamp}.csv")
    csv_filenames.append(filename)

# Initialize MQTT (will read local config.jsonc)
mqtt.mqtt_main()

# Setup Modbus client
client = None
error_file = None
if not SIMULATION_MODE:
    try:
        from pymodbus.client.sync import ModbusSerialClient as ModbusClient
        PORT = "/dev/ttyUSB0" if platform.system() == 'Linux' else 'COM7'
        if platform.system() == 'Linux' and not os.path.exists(PORT):
            for alt in ("/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyAMA0"):
                if os.path.exists(alt):
                    PORT = alt
                    break

        client = ModbusClient(method="rtu", port=PORT, stopbits=1,
                              bytesize=8, parity='E', baudrate=9600, timeout=0.5)
        connected = client.connect()
        if connected:
            print(f"✓ Successfully connected to {PORT}")
        else:
            raise RuntimeError("Modbus connect returned False")

        # open error log in logs directory
        error_log_path = logs_dir / "error_log.txt"
        error_file = open(str(error_log_path), "a")
    except Exception as e:
        print(f"✗ Unable to connect to {PORT} or initialize Modbus: {e}")
        print("Falling back to simulation mode...")
        SIMULATION_MODE = True
        client = None

# Setup meters and manager
meters = []
for device in DEVICE_CONFIG:
    meter = MeterDevice(
        name=device["name"],
        model=device["model"],
        parameters=PARAMETERS,
        client=client,
        error_file=error_file,
        simulation_mode=SIMULATION_MODE,
        device_address=device["address"],
    )
    meters.append(meter)

manager = MeterManager(
    meters,
    PARAMETERS,
    csv_filenames,
    mqtt_client=mqtt,
    publish_mqtt=PUBLISH_MQTT,
)


def setup_venv_if_requested():
    """Optional venv setup helper (keeps original behaviour)."""
    import sys
    from pathlib import Path

    if '--setup-venv' in sys.argv:
        if not VENV_UTILS_AVAILABLE:
            print("❌ venv_utils not available. Make sure venv_utils.py is in the same directory.")
            return False
        offline_mode = '--offline' in sys.argv
        offline_dir = "offline_packages" if offline_mode else None
        script_dir = Path(__file__).parent.absolute()
        venv_dir = script_dir / "dashboard_venv"
        required_packages = [
            "pymodbus==2.5.3",
            "pyserial==3.5",
            "paho-mqtt==2.1.0",
            "termcolor==3.1.0",
            "numpy==1.24.3",
            "pandas==2.0.3"
        ]
        success, python_exe = setup_complete_venv_environment(
            venv_dir=venv_dir,
            packages=required_packages,
            force_recreate=False,
            offline_dir=offline_dir
        )
        if success:
            print("✅ Virtual environment setup complete!")
            print(f"📍 Virtual environment: {venv_dir}")
        else:
            print("❌ Virtual environment setup failed!")
        return success

    if '--check-venv' in sys.argv:
        script_dir = Path(__file__).parent.absolute()
        venv_dir = script_dir / "dashboard_venv"
        print("🔍 Checking virtual environment status...")
        if venv_dir.exists():
            print(f"✅ Virtual environment exists: {venv_dir}")
        else:
            print("❌ Virtual environment not found")
        return True

    return None


# Check for venv commands
venv_result = setup_venv_if_requested()
if venv_result is not None:
    exit(0 if venv_result else 1)

print("Starting Meter Reading Dashboard...")
print("Press Ctrl+C to stop")
print("=" * 80)

try:
    next_time = time.time()
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')

        # Read new data (this also publishes to MQTT if enabled)
        manager.read_all()

        # Print header with status
        print(f"Meter Reading Dashboard - Cycle: {getattr(manager, 'TotalReadings', '?')}")
        print(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"MQTT Publishing: {'Enabled' if PUBLISH_MQTT else 'Disabled'}")
        print(f"Simulation Mode: {'Enabled' if SIMULATION_MODE else 'Disabled'}")
        print("=" * 80)

        # Display table
        header = ["Device"] + PARAMETERS
        print("\t".join(header))
        print("-" * 120)
        for i, values in enumerate(getattr(manager, 'allRegValues', [])):
            name = DEVICE_NAMES[i] if i < len(DEVICE_NAMES) else f"Device{i}"
            row = [name] + [str(v) for v in values]
            print("\t".join(row))

        print("=" * 80)
        print(f"Next update in {REFRESH_INTERVAL} seconds... (Press Ctrl+C to exit)")

        next_time += REFRESH_INTERVAL
        sleep_time = max(0, next_time - time.time())
        time.sleep(sleep_time)

except KeyboardInterrupt:
    print("\nShutting down dashboard...")
    try:
        manager.close()
    except Exception:
        pass
    try:
        mqtt.mqtt_close()
    except Exception:
        pass

    # Close Modbus connection and error file
    if client and hasattr(client, 'close'):
        try:
            client.close()
            print("✓ Modbus connection closed")
        except Exception:
            pass

    if error_file:
        try:
            error_file.close()
            print("✓ Error log file closed")
        except Exception:
            pass

    print("Dashboard stopped.")
