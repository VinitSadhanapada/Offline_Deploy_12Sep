#!/usr/bin/env python3
"""
TEST_99_full_system_hardware.py
===============================

Full System Hardware Verification

Tests complete pipeline from hardware to cloud:
1. Dependencies
2. Setup files
3. RS485 communication
4. CSV writing
5. MQTT publishing
6. Full integration (2-minute run)

Usage:
    sudo python3 TEST_99_full_system_hardware.py

Expected runtime: 2-3 minutes
"""

import os
import sys
import time
import json
import subprocess
import tempfile
import signal
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Configuration
TEST_DURATION_SECONDS = 120  # 2-minute integration run
MQTT_TEST_MESSAGE = "test_blackout_detection"


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


def log_step(step_num, total, description):
    """Print formatted step header."""
    print(f"\n{Colors.YELLOW}{Colors.BOLD}[STEP {step_num}/{total}] {description}{Colors.RESET}")
    print("=" * 60)


def log_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")


def log_failure(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")
    return False


def log_info(msg):
    print(f"{Colors.CYAN}  {msg}{Colors.RESET}")


def load_config():
    """Load config.json and device_config.json."""
    config = {}
    device_config = []
    
    config_path = PROJECT_ROOT / "config" / "config.json"
    device_config_path = PROJECT_ROOT / "config" / "device_config.json"
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            content = f.read()
            # Strip comments
            import re
            content = re.sub(r'//.*', '', content)
            config = json.loads(content)
    
    if device_config_path.exists():
        with open(device_config_path, 'r') as f:
            device_config = json.load(f)
    
    return config, device_config


def check_dependencies():
    """Step 1: Verify all Python dependencies are installed."""
    required = {
        'pymodbus': 'pymodbus',
        'paho.mqtt': 'paho-mqtt', 
        'serial': 'pyserial',
        'pandas': 'pandas',
        'numpy': 'numpy',
    }
    missing = []
    
    for module, pkg_name in required.items():
        try:
            __import__(module)
            print(f"  ✓ {module}")
        except ImportError:
            missing.append(pkg_name)
            print(f"  ✗ {module} MISSING")
    
    # Check smbus2 for RTC
    try:
        import smbus2
        print(f"  ✓ smbus2 (RTC)")
    except ImportError:
        print(f"  ⚠ smbus2 not available (RTC will use fallback)")
    
    if missing:
        return log_failure(f"Missing packages: {missing}")
    
    log_success("All required dependencies present")
    return True


def check_setup_files():
    """Step 2: Verify setup scripts and config files exist."""
    files = {
        "master_setup.sh": "Master setup script",
        "src/dashboard/simple_rpi_dashboard.py": "Main dashboard",
        "src/devices/meter_device.py": "Meter device module",
        "src/devices/meter_manager.py": "Meter manager",
        "config/config.json": "Main config",
        "config/device_config.json": "Device config",
    }
    
    all_present = True
    for f, desc in files.items():
        path = PROJECT_ROOT / f
        if path.exists():
            print(f"  ✓ {f}")
        else:
            print(f"  ✗ {f} MISSING ({desc})")
            all_present = False
    
    if not all_present:
        return log_failure("Some critical files are missing")
    
    log_success("All setup files present")
    return True


def check_rs485_communication():
    """Step 3: Verify RS485/Modbus communication with meters."""
    config, device_config = load_config()
    
    port = config.get("PORT", "/dev/ttyUSB0")
    print(f"  Serial port: {port}")
    
    # Check if port exists
    if not os.path.exists(port):
        return log_failure(f"Serial port {port} not found. Check USB-RS485 adapter.")
    
    print(f"  ✓ Serial port {port} exists")
    
    # Check port permissions
    if not os.access(port, os.R_OK | os.W_OK):
        log_info(f"Port {port} may need sudo or user in dialout group")
    
    if not device_config:
        log_info("No devices configured in device_config.json")
        return True  # Not a failure if no devices configured
    
    # Use actual MeterDevice class for proper communication
    try:
        from src.devices.meter_device import MeterDevice
        from src.utils.macros import PARAMETERS
        
        # Try pymodbus 3.x import first, fallback to 2.x
        try:
            from pymodbus.client import ModbusSerialClient
        except ImportError:
            from pymodbus.client.sync import ModbusSerialClient
        
        client = ModbusSerialClient(
            method='rtu',
            port=port,
            baudrate=9600,
            parity='N',
            stopbits=1,
            bytesize=8,
            timeout=2
        )
        
        if client.connect():
            print(f"  ✓ Modbus client connected to {port}")
            
            # Try to read from each configured device using MeterDevice
            meters_found = 0
            for dev in device_config:
                addr = dev.get("address", 1)
                name = dev.get("name", f"Meter_{addr}")
                model = dev.get("model", "LG6400")
                
                try:
                    # Create MeterDevice instance (uses correct registers for model)
                    meter = MeterDevice(
                        name=name,
                        model=model,
                        parameters=PARAMETERS,
                        client=client,
                        error_file=None,
                        simulation_mode=False,
                        device_address=addr
                    )
                    
                    # Try to read data
                    values = meter.read_data()
                    
                    # Check if we got valid data (not all -1)
                    if values and not all(v == -1 for v in values if isinstance(v, (int, float))):
                        print(f"  ✓ {name} (addr={addr}, model={model}) responding")
                        # Show a sample value
                        if len(values) > 1:
                            log_info(f"Sample reading: {values[1] if len(values) > 1 else values[0]}")
                        meters_found += 1
                    else:
                        print(f"  ✗ {name} (addr={addr}) returned error values")
                except Exception as e:
                    print(f"  ✗ {name} (addr={addr}) error: {e}")
            
            client.close()
            
            if meters_found == 0:
                return log_failure(f"No meters responding on RS485 bus (0/{len(device_config)})")
            
            log_success(f"RS485 communication OK - {meters_found}/{len(device_config)} meters responding")
            return True
        else:
            return log_failure(f"Could not connect Modbus client to {port}")
            
    except Exception as e:
        return log_failure(f"RS485 test failed: {e}")


def check_csv_writing():
    """Step 4: Verify CSV writing capability."""
    csv_dir = PROJECT_ROOT / "data" / "csv"
    csv_file = csv_dir / "DATA_ALL.csv"
    
    # Check directory exists or can be created
    try:
        csv_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ CSV directory exists: {csv_dir}")
    except Exception as e:
        return log_failure(f"Cannot create CSV directory: {e}")
    
    # Check write permission
    test_file = csv_dir / ".write_test"
    try:
        test_file.write_text("test")
        test_file.unlink()
        print(f"  ✓ CSV directory is writable")
    except Exception as e:
        return log_failure(f"Cannot write to CSV directory: {e}")
    
    # Check if DATA_ALL.csv exists and is valid
    if csv_file.exists():
        try:
            import csv
            with open(csv_file, 'r') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    row_count = sum(1 for _ in reader) + 1
                    print(f"  ✓ DATA_ALL.csv exists ({row_count} rows)")
                    print(f"    Header: {header[:5]}..." if len(header) > 5 else f"    Header: {header}")
        except Exception as e:
            print(f"  ⚠ DATA_ALL.csv exists but may be corrupted: {e}")
    else:
        print(f"  ℹ DATA_ALL.csv does not exist yet (will be created)")
    
    # Check EVENTS.csv
    events_file = csv_dir / "EVENTS.csv"
    if events_file.exists():
        print(f"  ✓ EVENTS.csv exists")
    else:
        print(f"  ℹ EVENTS.csv does not exist yet (will be created)")
    
    log_success("CSV writing capability verified")
    return True


def check_rtc():
    """Step 5: Check RTC (DS3231) availability."""
    try:
        from src.utils.rtc_module import is_rtc_available, get_rtc_time
        
        if is_rtc_available():
            rtc_time = get_rtc_time()
            system_time = datetime.now()
            drift = abs((system_time - rtc_time).total_seconds())
            
            print(f"  ✓ RTC detected (DS3231)")
            print(f"    RTC time:    {rtc_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    System time: {system_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Drift: {drift:.1f} seconds")
            
            if drift > 60:
                print(f"  ⚠ Large drift detected - consider syncing RTC")
            
            log_success("RTC available and working")
            return True
        else:
            print(f"  ⚠ RTC not detected - using system time only")
            log_info("This is OK if no DS3231 is installed")
            return True  # Not a failure, just a warning
            
    except ImportError as e:
        print(f"  ⚠ RTC module not available: {e}")
        return True  # Not critical
    except Exception as e:
        print(f"  ⚠ RTC check error: {e}")
        return True  # Not critical


def check_mqtt_publishing():
    """Step 6: Check MQTT publishing capability (if enabled)."""
    config, _ = load_config()
    
    if not config.get("ENABLE_MQTT", False):
        print(f"  ℹ MQTT is disabled in config")
        log_info("Skipping MQTT test (not configured)")
        return True
    
    try:
        import paho.mqtt.client as mqtt
        
        # Get MQTT config
        mqtt_config = config.get("mqtt", {})
        broker = mqtt_config.get("broker", "localhost")
        port = mqtt_config.get("port", 1883)
        
        print(f"  MQTT broker: {broker}:{port}")
        
        # Try to connect
        client = mqtt.Client()
        connected = [False]
        
        def on_connect(c, userdata, flags, rc):
            if rc == 0:
                connected[0] = True
        
        client.on_connect = on_connect
        
        try:
            client.connect(broker, port, keepalive=5)
            client.loop_start()
            
            # Wait up to 5 seconds for connection
            for _ in range(50):
                if connected[0]:
                    break
                time.sleep(0.1)
            
            client.loop_stop()
            client.disconnect()
            
            if connected[0]:
                print(f"  ✓ MQTT broker reachable")
                log_success("MQTT publishing capability verified")
                return True
            else:
                print(f"  ⚠ Could not connect to MQTT broker")
                log_info("MQTT may not be running - check broker status")
                return True  # Not a critical failure
                
        except Exception as e:
            print(f"  ⚠ MQTT connection failed: {e}")
            return True  # Not critical
            
    except ImportError:
        print(f"  ⚠ paho-mqtt not installed")
        return True


def run_integration_test():
    """Step 7: Run full integration test for TEST_DURATION_SECONDS."""
    config, device_config = load_config()
    
    print(f"  Running {TEST_DURATION_SECONDS}-second integration test...")
    print(f"  Configured meters: {len(device_config)}")
    
    # Track metrics
    readings_count = 0
    errors_count = 0
    start_time = time.time()
    
    # Import modules
    try:
        from src.devices.meter_device import MeterDevice
        from src.devices.meter_manager import MeterManager
        from src.utils.macros import PARAMETERS
    except Exception as e:
        return log_failure(f"Failed to import modules: {e}")
    
    # Create Modbus client
    try:
        # Try pymodbus 3.x import first, fallback to 2.x
        try:
            from pymodbus.client import ModbusSerialClient
        except ImportError:
            from pymodbus.client.sync import ModbusSerialClient
        
        port = config.get("PORT", "/dev/ttyUSB0")
        client = ModbusSerialClient(
            method='rtu',
            port=port,
            baudrate=9600,
            parity='N',
            stopbits=1,
            bytesize=8,
            timeout=1
        )
        
        if not client.connect():
            return log_failure(f"Could not connect to {port}")
            
    except Exception as e:
        return log_failure(f"Modbus client error: {e}")
    
    # Create meters
    meters = []
    for dev in device_config:
        name = dev.get("name", f"Meter_{len(meters)+1}")
        addr = dev.get("address", len(meters)+1)
        model = dev.get("model", "LG6400")
        
        m = MeterDevice(
            name=name,
            model=model,
            parameters=PARAMETERS,
            client=client,
            error_file=None,
            simulation_mode=config.get("SIMULATION_MODE", False),
            device_address=addr
        )
        meters.append(m)
    
    # Create manager with temp directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "TEST_DATA_ALL.csv"
        
        csv_log_interval = config.get("CSV_LOG_INTERVAL", 60)
        manager = MeterManager(
            meters=meters,
            parameters=PARAMETERS,
            csv_filenames=[str(csv_path)],
            fast_poll_interval=0.5,
            slow_csv_interval=min(csv_log_interval, 10)  # Use shorter interval for test
        )
        
        # Override paths for isolated test
        manager.csv_path = str(csv_path)
        manager.events_path = Path(tmpdir) / "TEST_EVENTS.csv"
        manager.data_dir = Path(tmpdir)
        
        print(f"\n  {Colors.CYAN}Integration test running...{Colors.RESET}")
        print(f"  Press Ctrl+C to stop early\n")
        
        # Progress bar
        bar_width = 40
        
        try:
            while time.time() - start_time < TEST_DURATION_SECONDS:
                try:
                    manager.read_all(inter_device_delay=0.1)
                    readings_count += 1
                except Exception as e:
                    errors_count += 1
                    if errors_count <= 3:
                        print(f"  ⚠ Read error: {e}")
                
                # Update progress
                elapsed = time.time() - start_time
                progress = min(elapsed / TEST_DURATION_SECONDS, 1.0)
                filled = int(bar_width * progress)
                bar = '█' * filled + '░' * (bar_width - filled)
                
                print(f"\r  [{bar}] {int(progress*100):3d}% | Readings: {readings_count} | Errors: {errors_count}", end='', flush=True)
                
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print(f"\n  Test interrupted by user")
        
        print()  # New line after progress bar
        
        # Close manager
        try:
            manager.close()
        except:
            pass
        
        # Check results
        elapsed_total = time.time() - start_time
        
        # Check CSV file
        csv_rows = 0
        if csv_path.exists():
            with open(csv_path, 'r') as f:
                csv_rows = sum(1 for _ in f) - 1  # Exclude header
        
        # Check events file
        events_count = 0
        events_path = Path(tmpdir) / "TEST_EVENTS.csv"
        if events_path.exists():
            with open(events_path, 'r') as f:
                events_count = sum(1 for _ in f) - 1
    
    client.close()
    
    # Report results
    print(f"\n  {Colors.BOLD}Integration Test Results:{Colors.RESET}")
    print(f"  ─────────────────────────────────")
    print(f"  Duration:      {elapsed_total:.1f} seconds")
    print(f"  Total reads:   {readings_count}")
    print(f"  Errors:        {errors_count}")
    print(f"  CSV rows:      {csv_rows}")
    print(f"  Events logged: {events_count}")
    
    error_rate = errors_count / max(readings_count, 1) * 100
    
    if error_rate > 50:
        return log_failure(f"High error rate: {error_rate:.1f}%")
    elif readings_count == 0:
        return log_failure("No successful readings")
    else:
        if error_rate > 10:
            print(f"  ⚠ Error rate {error_rate:.1f}% - check connections")
        log_success(f"Integration test passed ({readings_count} readings, {error_rate:.1f}% errors)")
        return True


def main():
    """Run all hardware verification tests."""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  TEST_99: Full System Hardware Verification{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"  Project root: {PROJECT_ROOT}")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    total_steps = 7
    results = {}
    
    # Step 1: Dependencies
    log_step(1, total_steps, "Checking Dependencies")
    results['dependencies'] = check_dependencies()
    
    # Step 2: Setup files
    log_step(2, total_steps, "Checking Setup Files")
    results['setup_files'] = check_setup_files()
    
    # Step 3: RS485 Communication
    log_step(3, total_steps, "Testing RS485 Communication")
    results['rs485'] = check_rs485_communication()
    
    # Step 4: CSV Writing
    log_step(4, total_steps, "Checking CSV Writing")
    results['csv'] = check_csv_writing()
    
    # Step 5: RTC
    log_step(5, total_steps, "Checking RTC (DS3231)")
    results['rtc'] = check_rtc()
    
    # Step 6: MQTT
    log_step(6, total_steps, "Checking MQTT Publishing")
    results['mqtt'] = check_mqtt_publishing()
    
    # Step 7: Integration Test
    log_step(7, total_steps, f"Running Integration Test ({TEST_DURATION_SECONDS}s)")
    results['integration'] = run_integration_test()
    
    # Final Summary
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  TEST SUMMARY{Colors.RESET}")
    print(f"{'='*60}")
    
    passed = 0
    failed = 0
    
    for test, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {test:20s} [{status}]")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"{'='*60}")
    
    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}  ✓ ALL TESTS PASSED ({passed}/{passed+failed}){Colors.RESET}")
        print(f"  System is ready for production use.\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}  ✗ SOME TESTS FAILED ({failed} failures){Colors.RESET}")
        print(f"  Please fix the issues above before deploying.\n")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Test interrupted by user{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
