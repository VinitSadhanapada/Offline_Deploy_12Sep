#!/usr/bin/env python3
"""
TEST_05_HARDWARE: Dual-Rate Architecture Test with REAL METERS

This test connects to actual meters via RS485 to verify:
1. Fast polling (0.5s) captures blackout events
2. Slow CSV writes (60s) for main data logging
3. EVENTS.csv gets immediate fsync on blackout detection

PREREQUISITES:
  - Meter connected via RS485/USB adapter
  - device_config.json configured with meter details
  - Run as: python3 TEST_05_HARDWARE_dual_rate.py

WHAT THIS TEST DOES:
  1. Loads real meter config from device_config.json
  2. Connects to meter via Modbus RTU
  3. Polls for 2 minutes at 0.5s intervals
  4. Shows live readings on screen
  5. Detects any blackout events (Int count changes)
  6. Writes EVENTS.csv immediately on detection
  7. Writes DATA_ALL.csv every 60s

TO SIMULATE A BLACKOUT DURING TEST:
  - Briefly disconnect meter power (not RS485)
  - Or flip the breaker feeding the meter's CT/PT inputs
  - Watch for "BLACKOUT DETECTED" in output
"""
import sys
import os
import json
import time
import signal
from pathlib import Path
from datetime import datetime

# Add project to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    prefix = {
        "INFO": f"{Colors.CYAN}[INFO]{Colors.ENDC}",
        "INPUT": f"{Colors.YELLOW}[INPUT]{Colors.ENDC}",
        "PROCESS": f"{Colors.BLUE}[PROCESS]{Colors.ENDC}",
        "OUTPUT": f"{Colors.GREEN}[OUTPUT]{Colors.ENDC}",
        "CHECK": f"{Colors.BOLD}[CHECK]{Colors.ENDC}",
        "PASS": f"{Colors.GREEN}{Colors.BOLD}[PASS]{Colors.ENDC}",
        "FAIL": f"{Colors.RED}{Colors.BOLD}[FAIL]{Colors.ENDC}",
        "HEADER": f"{Colors.HEADER}{Colors.BOLD}",
        "DETAIL": f"{Colors.DIM}[DETAIL]{Colors.ENDC}",
        "WARN": f"{Colors.YELLOW}{Colors.BOLD}[WARN]{Colors.ENDC}",
        "BLACKOUT": f"{Colors.BG_RED}{Colors.BOLD}[BLACKOUT]{Colors.ENDC}",
        "METER": f"{Colors.BG_GREEN}[METER]{Colors.ENDC}",
    }
    print(f"{timestamp} {prefix.get(level, '[???]')} {msg}")

# Global for clean shutdown
running = True

def signal_handler(sig, frame):
    global running
    print("\n")
    log("Received interrupt signal, shutting down gracefully...", "WARN")
    running = False

def load_device_config():
    """Load meter configuration from device_config.json"""
    config_paths = [
        Path("/home/pi/meter_config/device_config.json"),
        PROJECT_ROOT / "config" / "device_config.json",
        Path.home() / "meter_config" / "device_config.json",
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            log(f"Found config at: {config_path}", "INFO")
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                if config:  # Non-empty list
                    return config, config_path
                else:
                    log(f"Config file is empty: {config_path}", "WARN")
            except json.JSONDecodeError as e:
                log(f"Invalid JSON in {config_path}: {e}", "WARN")
    
    return None, None

def create_modbus_client(port="/dev/ttyUSB0", baudrate=9600):
    """Create Modbus RTU client connection"""
    try:
        from pymodbus.client import ModbusSerialClient
        
        client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity='N',
            stopbits=1,
            bytesize=8,
            timeout=1
        )
        
        if client.connect():
            log(f"Modbus connected on {port} @ {baudrate} baud", "OUTPUT")
            return client
        else:
            log(f"Failed to connect to {port}", "FAIL")
            return None
            
    except ImportError:
        log("pymodbus not installed. Install with: pip install pymodbus", "FAIL")
        return None
    except Exception as e:
        log(f"Modbus connection error: {e}", "FAIL")
        return None

def run_hardware_test():
    global running
    
    print("\n" + "="*80)
    log("TEST_05_HARDWARE: DUAL-RATE ARCHITECTURE WITH REAL METERS", "HEADER")
    print("="*80 + Colors.ENDC)
    
    print("""
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  This test will connect to your actual meter via RS485 and monitor     │
    │  for blackout events. It runs for 2 minutes (or until Ctrl+C).         │
    │                                                                         │
    │  TO TEST BLACKOUT DETECTION:                                           │
    │    • Briefly disconnect meter power input (NOT the RS485 cable)        │
    │    • Or flip the breaker on the line being monitored                   │
    │    • Watch for "BLACKOUT DETECTED" messages                            │
    │                                                                         │
    │  FILES CREATED:                                                        │
    │    • data/csv/DATA_ALL.csv - Main readings (every 60s)                 │
    │    • data/csv/EVENTS.csv   - Blackout events (immediate)               │
    └─────────────────────────────────────────────────────────────────────────┘
    """)
    
    # Setup signal handler for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # ===== PHASE 1: LOAD CONFIGURATION =====
    print("\n" + "-"*40)
    log("PHASE 1: LOADING CONFIGURATION", "HEADER")
    print("-"*40 + Colors.ENDC)
    
    device_config, config_path = load_device_config()
    
    if not device_config:
        log("No valid device configuration found!", "FAIL")
        log("Please configure at least one meter in:", "INFO")
        log("  /home/pi/meter_config/device_config.json", "INFO")
        log("  OR config/device_config.json", "INFO")
        print("""
    Example device_config.json:
    [
      {
        "name": "MainMeter",
        "address": 1,
        "model": "LG6400",
        "location": "Panel Room"
      }
    ]
        """)
        return False
    
    log(f"Loaded {len(device_config)} meter(s) from config:", "OUTPUT")
    for i, meter_cfg in enumerate(device_config):
        log(f"  [{i+1}] {meter_cfg.get('name', 'Unknown')}", "INPUT")
        log(f"      Address: {meter_cfg.get('address', 1)}", "INPUT")
        log(f"      Model: {meter_cfg.get('model', 'Unknown')}", "INPUT")
        log(f"      Location: {meter_cfg.get('location', 'N/A')}", "INPUT")
    
    # ===== PHASE 2: CONNECT TO HARDWARE =====
    print("\n" + "-"*40)
    log("PHASE 2: CONNECTING TO HARDWARE", "HEADER")
    print("-"*40 + Colors.ENDC)
    
    # Check for USB serial adapter
    usb_ports = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyAMA0"]
    available_port = None
    
    for port in usb_ports:
        if os.path.exists(port):
            log(f"Found serial port: {port}", "OUTPUT")
            available_port = port
            break
    
    if not available_port:
        log("No USB serial adapter found!", "FAIL")
        log("Please connect RS485-USB adapter and try again", "INFO")
        log("Expected at: /dev/ttyUSB0 or /dev/ttyUSB1", "INFO")
        return False
    
    client = create_modbus_client(port=available_port)
    if not client:
        return False
    
    # ===== PHASE 3: CREATE METER DEVICES =====
    print("\n" + "-"*40)
    log("PHASE 3: INITIALIZING METER DEVICES", "HEADER")
    print("-"*40 + Colors.ENDC)
    
    from src.devices.meter_device import MeterDevice
    from src.devices.meter_manager import MeterManager
    from src.utils.macros import PARAMETERS
    
    meters = []
    for meter_cfg in device_config:
        name = meter_cfg.get('name', 'Meter')
        model = meter_cfg.get('model', 'LG6400')
        address = meter_cfg.get('address', 1)
        
        log(f"Creating MeterDevice: {name} (addr={address}, model={model})", "PROCESS")
        
        meter = MeterDevice(
            name=name,
            model=model,
            parameters=PARAMETERS,
            client=client,
            error_file=None,
            simulation_mode=False,
            device_address=address
        )
        meters.append(meter)
        log(f"  ✓ MeterDevice created", "OUTPUT")
    
    # ===== PHASE 4: CREATE METER MANAGER =====
    print("\n" + "-"*40)
    log("PHASE 4: CREATING DUAL-RATE METER MANAGER", "HEADER")
    print("-"*40 + Colors.ENDC)
    
    fast_poll = 0.5
    slow_csv = 60
    
    log(f"Timing configuration:", "INPUT")
    log(f"  - fast_poll_interval: {fast_poll}s (blackout detection)", "INPUT")
    log(f"  - slow_csv_interval: {slow_csv}s (main CSV writes)", "INPUT")
    
    try:
        manager = MeterManager(
            meters=meters,
            parameters=PARAMETERS,
            fast_poll_interval=fast_poll,
            slow_csv_interval=slow_csv
        )
        log(f"MeterManager created successfully", "OUTPUT")
        log(f"  - Main CSV: {manager.csv_path}", "OUTPUT")
        log(f"  - Events CSV: {manager.events_path}", "OUTPUT")
        
    except Exception as e:
        log(f"Failed to create MeterManager: {e}", "FAIL")
        import traceback
        traceback.print_exc()
        client.close()
        return False
    
    # ===== PHASE 5: LIVE MONITORING =====
    print("\n" + "-"*40)
    log("PHASE 5: LIVE MONITORING (2 minutes or Ctrl+C to stop)", "HEADER")
    print("-"*40 + Colors.ENDC)
    
    print("""
    ┌──────────────────────────────────────────────────────────────┐
    │  MONITORING ACTIVE - Press Ctrl+C to stop                    │
    │                                                              │
    │  Legend:                                                     │
    │    [METER] = Successful read from meter                      │
    │    [BLACKOUT] = Interruption count increased (blackout!)     │
    │    [WARN] = Communication error or timeout                   │
    └──────────────────────────────────────────────────────────────┘
    """)
    
    start_time = time.time()
    test_duration = 120  # 2 minutes
    poll_count = 0
    blackout_count = 0
    error_count = 0
    last_status_time = 0
    
    # Find interruption index for display
    intr_idx = None
    freq_idx = None
    for i, p in enumerate(PARAMETERS):
        p_lower = p.lower().replace(" ", "").replace("_", "")
        if 'interruption' in p_lower or 'intr' in p_lower:
            intr_idx = i
        if 'frequency' in p_lower or 'freq' in p_lower:
            freq_idx = i
    
    log(f"Interruption parameter at index: {intr_idx}", "DETAIL")
    log(f"Frequency parameter at index: {freq_idx}", "DETAIL")
    
    prev_int_counts = {}
    
    try:
        while running and (time.time() - start_time) < test_duration:
            elapsed = time.time() - start_time
            
            # Call read_all (handles its own throttling)
            manager.read_all()
            poll_count += 1
            
            # Display meter values
            for meter_name, state in manager._meter_state.items():
                values = state.get('latest_values')
                if values:
                    # Get key values
                    freq = values[freq_idx] if freq_idx and len(values) > freq_idx else "N/A"
                    intr = values[intr_idx] if intr_idx and len(values) > intr_idx else "N/A"
                    
                    # Check for blackout (int count increase)
                    if intr_idx and intr != -1:
                        try:
                            current_int = int(float(intr))
                            prev_int = prev_int_counts.get(meter_name)
                            
                            if prev_int is not None and current_int > prev_int:
                                blackout_count += 1
                                log(f"█ {meter_name}: INT COUNT JUMPED {prev_int} → {current_int} █", "BLACKOUT")
                                log(f"  Blackouts detected this session: {blackout_count}", "BLACKOUT")
                            
                            prev_int_counts[meter_name] = current_int
                        except (ValueError, TypeError):
                            pass
                    
                    # Periodic status (every 5 seconds)
                    if time.time() - last_status_time >= 5:
                        if freq == -1 or intr == -1:
                            error_count += 1
                            log(f"{meter_name}: COMM_ERROR (values=-1)", "WARN")
                        else:
                            log(f"{meter_name}: Freq={freq}Hz, Int={intr}, Time={values[0]}", "METER")
                        last_status_time = time.time()
                
                else:
                    if time.time() - last_status_time >= 5:
                        log(f"{meter_name}: No data received", "WARN")
                        error_count += 1
            
            # Show progress
            remaining = test_duration - elapsed
            if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                log(f"Progress: {int(elapsed)}s elapsed, {int(remaining)}s remaining", "INFO")
            
            # Small sleep to prevent CPU spinning (throttle handles actual timing)
            time.sleep(0.1)
            
    except Exception as e:
        log(f"Error during monitoring: {e}", "FAIL")
        import traceback
        traceback.print_exc()
    
    # ===== PHASE 6: RESULTS =====
    print("\n" + "-"*40)
    log("PHASE 6: TEST RESULTS", "HEADER")
    print("-"*40 + Colors.ENDC)
    
    total_time = time.time() - start_time
    
    log(f"Test Duration: {total_time:.1f} seconds", "OUTPUT")
    log(f"Total Polls: {poll_count}", "OUTPUT")
    log(f"Blackouts Detected: {blackout_count}", "OUTPUT")
    log(f"Communication Errors: {error_count}", "OUTPUT")
    
    # Check files created
    print()
    log("Files created:", "OUTPUT")
    
    if os.path.exists(manager.csv_path):
        size = os.path.getsize(manager.csv_path)
        with open(manager.csv_path, 'r') as f:
            lines = len(f.readlines())
        log(f"  ✓ {manager.csv_path}", "PASS")
        log(f"    Size: {size} bytes, Lines: {lines}", "DETAIL")
    else:
        log(f"  ✗ {manager.csv_path} NOT CREATED", "FAIL")
    
    if os.path.exists(manager.events_path):
        size = os.path.getsize(manager.events_path)
        with open(manager.events_path, 'r') as f:
            lines = len(f.readlines())
        log(f"  ✓ {manager.events_path}", "PASS")
        log(f"    Size: {size} bytes, Lines: {lines} (including header)", "DETAIL")
        
        if lines > 1:
            log(f"  Events logged:", "OUTPUT")
            with open(manager.events_path, 'r') as f:
                for i, line in enumerate(f.readlines()):
                    if i == 0:
                        continue  # Skip header
                    log(f"    {line.strip()}", "BLACKOUT")
    else:
        log(f"  ✗ {manager.events_path} NOT CREATED", "FAIL")
    
    # Cleanup
    print("\n" + "-"*40)
    log("CLEANUP", "HEADER")
    print("-"*40 + Colors.ENDC)
    
    try:
        manager.close()
        log("MeterManager closed", "OUTPUT")
    except:
        pass
    
    try:
        client.close()
        log("Modbus client closed", "OUTPUT")
    except:
        pass
    
    # ===== FINAL VERDICT =====
    print("\n" + "="*80)
    if blackout_count > 0:
        log(f"TEST COMPLETE: {blackout_count} BLACKOUT(S) DETECTED AND LOGGED", "PASS")
    elif error_count > poll_count * 0.5:
        log(f"TEST COMPLETE: Too many communication errors ({error_count})", "WARN")
    else:
        log(f"TEST COMPLETE: No blackouts during test period", "INFO")
        log(f"  (To test blackout detection, briefly interrupt power to the monitored line)", "INFO")
    print("="*80 + "\n")
    
    return True

if __name__ == "__main__":
    success = run_hardware_test()
    sys.exit(0 if success else 1)
