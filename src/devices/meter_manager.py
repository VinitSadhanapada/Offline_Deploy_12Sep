#!/usr/bin/env python3
import csv
import time
import os
import re
import tempfile
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# Time sanitizer for RTC-based time integrity
try:
    from src.utils.time_sanitizer import RTCTimeSanitizer
    TIME_SANITIZER_AVAILABLE = True
except ImportError:
    TIME_SANITIZER_AVAILABLE = False


def format_csv_value(value, param_name):
    """
    Format a value for CSV output with simple, consistent formatting.

    Args:
        value: The raw value from meter reading
        param_name: The parameter name to determine formatting

    Returns:
        str: Formatted value string
    """
    if value in [0, "0", "0.0", 0.0]:
        return "0"

    try:
        # Convert to float for formatting
        float_val = float(value)

        # Round to 2 decimal places for most values
        if float_val == int(float_val):
            return str(int(float_val))  # No decimals for whole numbers
        else:
            return f"{float_val:.2f}"  # 2 decimal places for others

    except (ValueError, TypeError):
        # If conversion fails, return as string
        return str(value)


def create_formatted_csv_header(parameters):
    """
    Create a simple, readable CSV header by cleaning up parameter names.

    Returns:
        list: Formatted header row
    """
    formatted_headers = ["Device_ID", "Meter_Name"]
    # Insert 'Time' and 'Model' in the correct order
    for i, param in enumerate(parameters):
        clean_name = param.replace(" ", "_").replace(
            ".", "").replace("(", "").replace(")", "")
        if i == 0:
            # After 'Time', insert 'Model'
            formatted_headers.append(clean_name)
            formatted_headers.append("Model")
        else:
            formatted_headers.append(clean_name)
    return formatted_headers


"""
MeterManager Module for Multi-Device Coordination.

This module provides the MeterManager class which orchestrates reading data from
multiple meter devices, manages CSV logging, MQTT publishing, and UI callbacks.
Designed to handle complex meter reading scenarios with centralized management.
"""


class MeterManager:
    DEFAULT_RETENTION_DAYS = 14  # 2 weeks

    def _ensure_csv_file(self):
        """
        Ensure the CSV file exists and is open for appending. If deleted, recreate and write header.
        """
        import os
        file_path = self.csv_file.name if hasattr(self, 'csv_file') else None
        need_header = False
        if file_path is not None:
            if self.csv_file.closed or not os.path.exists(file_path):
                try:
                    self.csv_file = open(file_path, "a", newline='')
                    self.csv_writer = csv.writer(self.csv_file)
                    # If file is empty, write header
                    self.csv_file.seek(0, 2)
                    if self.csv_file.tell() == 0:
                        need_header = True
                except Exception as e:
                    print(f"Error reopening CSV file {file_path}: {e}")
                    return
        if need_header:
            try:
                formatted_headers = create_formatted_csv_header(
                    self.parameters)
                self.csv_writer.writerow(formatted_headers)
                self.csv_file.flush()
            except Exception as e:
                print(f"Error writing header to CSV: {e}")

    def get_all_meter_readings(self):
        """
        Returns a list of dicts with device info and latest readings for all meters.
        Each dict contains: 'device_id', 'device_name', 'model', 'readings' (list of parameter values)
        """
        result = []
        for i, meter in enumerate(self.meters):
            info = {
                'device_id': getattr(meter, 'device_address', i+1),
                'device_name': getattr(meter, 'name', f"Meter_{i+1}"),
                'model': getattr(meter, 'model', 'Unknown'),
                'readings': self.allRegValues[i] if i < len(self.allRegValues) else []
            }
            result.append(info)
        return result
    """
    Manages multiple meter devices with coordinated data collection and publishing.
    
    The MeterManager class serves as the central coordinator for a meter reading system,
    handling multiple MeterDevice instances and providing integrated logging, MQTT
    publishing, and UI update capabilities.
    
    Args:
        meters (List[MeterDevice]): List of MeterDevice instances to manage.
    parameters (List[str]): Parameter names that match across all devices.
        csv_filenames (List[str]): CSV file paths for logging each device's data.
                                 Must have same length as meters list.
        ui_callback (callable, optional): Function to call for UI updates.
                                        Signature: callback(total_readings, stdscr, reg_values)
        mqtt_client (object, optional): MQTT client instance for data publishing.
        publish_mqtt (bool): Enable MQTT publishing. Default: False.
    
    Attributes:
        meters (List[MeterDevice]): Managed meter devices.
        TotalReadings (int): Total number of reading cycles completed.
        allRegValues (List[List]): Latest readings from all devices.
                                 Structure: [[device0_readings], [device1_readings], ...]
        published_msg (int): Count of MQTT messages successfully published.
        
    Raises:
        ValueError: If meters and csv_filenames lists have different lengths.
        FileNotFoundError: If CSV file paths cannot be created.
        
    Example:
        >>> meters = [MeterDevice("Meter1", "LG6400", params, simulation_mode=True)]
        >>> manager = MeterManager(
        ...     meters=meters,
        ...     parameters=["Time", "Voltage", "Current"],
        ...     csv_filenames=["meter1_log.csv"],
        ...     publish_mqtt=True
        ... )
        >>> manager.read_all()  # Read from all meters and update logs
        >>> print(f"Completed {manager.TotalReadings} reading cycles")
    """

    def __init__(self, meters, parameters, csv_filenames=None, ui_callback=None, mqtt_client=None, publish_mqtt=False,
                 fast_poll_interval=0.5, slow_csv_interval=60):
        """
        Initialize MeterManager with devices and configuration.

        Dual-rate architecture:
        - fast_poll_interval: Seconds between blackout checks (default 0.5)
        - slow_csv_interval: Seconds between main CSV writes (default 60)

        Args:
            meters (List[MeterDevice]): Meter devices to manage
            parameters (List[str]): Parameter names for all devices
            csv_filenames (ignored): CSV log file paths (ignored; always uses DATA_ALL.csv)
            ui_callback (callable, optional): UI update function
            mqtt_client (object, optional): MQTT client for publishing
            publish_mqtt (bool): Enable MQTT message publishing
            fast_poll_interval (float): Seconds between fast polls for blackout detection (default 0.5)
            slow_csv_interval (float): Seconds between main CSV writes (default 60)
        """
        self.meters = meters
        self.parameters = parameters
        
        # Setup error logger
        self.error_logger = logging.getLogger(__name__)
        if not self.error_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.error_logger.addHandler(handler)
            self.error_logger.setLevel(logging.INFO)
        
        # Dual-rate timing configuration
        self.fast_poll_interval = fast_poll_interval
        self.slow_csv_interval = slow_csv_interval
        
        # Timing trackers
        self._last_poll_time = 0
        self._last_csv_write_time = 0
        self._last_drift_check_time = 0
        self._drift_check_interval = 60  # Check RTC vs system every 60 seconds
        
        # Per-meter state for fast polling (blackout detection)
        self._meter_state = {}
        for idx, m in enumerate(meters):
            name = getattr(m, 'name', f"Meter_{idx+1}")
            self._meter_state[name] = {
                'latest_values': None,
                'last_int_count': None,
                'last_poll_success': None
            }
        
        # Per-meter state tracking for refined detection (Feature 5/6)
        self._meter_comm_state = {}  # meter_name -> True/False (healthy/error)
        self._meter_last_valid_int = {}  # Last known good Int count (not -1)
        self._meter_suspect_state = {}  # For Option C deferred confirmation
        
        for idx, m in enumerate(meters):
            name = getattr(m, 'name', f"Meter_{idx+1}")
            self._meter_comm_state[name] = 'OK'  # 'OK' | 'RPI_USB_ERROR' | 'METER_COMM_ERROR'
            self._meter_last_valid_int[name] = None
            self._meter_suspect_state[name] = {
                'active': False,          # Is blackout currently in progress?
                'start_time': None,       # When blackout started
                'start_int': None         # Int counter at blackout start
            }
        
        # Find key parameter indices once for detection logic
        self._intr_idx = self._find_param_index(parameters, ['interruption', 'intr', 'no of interruption', 'noofintr'])
        self._freq_idx = self._find_param_index(parameters, ['frequency', 'freq'])
        self._wh_idx = self._find_param_index(parameters, ['whreceived', 'whrcvd', 'wh'])
        self._onhrs_idx = self._find_param_index(parameters, ['onhours', 'onhrs'])
        
        # Always use DATA_ALL.csv in data/csv/
        from pathlib import Path
        data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "csv"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = str(data_dir / "DATA_ALL.csv")
        self.data_dir = data_dir

        # Setup backup directory for rotated archives
        self.backup_dir = data_dir / "backup"
        self.backup_dir.mkdir(exist_ok=True)
        
        # Retention settings
        self.retention_days = self.DEFAULT_RETENTION_DAYS
        self.prune_check_interval = 3600  # 1 hour
        self._last_prune_check = time.time()
        self.rotation_size_threshold = 1 * 1024 * 1024  # 1MB triggers rotation
        
        # Track CSV start time for naming archives
        self._current_csv_start_time = None  # Set after file is opened
        
        try:
            self.csv_file = open(self.csv_path, "a", newline='')
        except Exception as e:
            print(f"Error opening CSV file {self.csv_path}: {e}")
            raise
        self.csv_writer = csv.writer(self.csv_file)
        # Write header if file is empty
        try:
            self.csv_file.seek(0, 2)  # Seek to end
            if self.csv_file.tell() == 0:
                formatted_headers = create_formatted_csv_header(parameters)
                self.csv_writer.writerow(formatted_headers)
            self.csv_file.seek(0, 2)
        except Exception as e:
            print(f"Error writing header to CSV: {e}")
        
        # Get CSV start time for archive naming
        self._current_csv_start_time = self._get_csv_start_time()

        # Detect and repair any CSV corruption on startup
        self._detect_and_repair_corruption()

        # Setup events CSV (fast, immediate flush for blackout detection)
        self.events_path = data_dir / "EVENTS.csv"
        self._init_events_csv()
        
        # Initialize time sanitizer for RTC-based time integrity
        self._last_csv_timestamp = None  # For time jump detection
        if TIME_SANITIZER_AVAILABLE:
            try:
                state_file = data_dir.parent / "rtc_state.json"
                self.time_sanitizer = RTCTimeSanitizer(state_file_path=str(state_file))
                
                # Validate time on startup
                is_valid, time_events = self.time_sanitizer.validate_and_correct()
                for event in time_events:
                    self._log_system_event(event)
                
                if is_valid:
                    self.error_logger.info("Time sanitizer: RTC validation passed")
                else:
                    self.error_logger.warning("Time sanitizer: RTC validation failed, check EVENTS.csv")
            except Exception as e:
                self.error_logger.error(f"Failed to initialize time sanitizer: {e}")
                self.time_sanitizer = None
        else:
            self.time_sanitizer = None
            self.error_logger.debug("Time sanitizer not available (import failed)")
        
        self.ui_callback = ui_callback
        self.allRegValues = [[0] * len(parameters) for _ in meters]
        self.published_msg = 0
        self.TotalReadings = 0
        self.mqtt_client = mqtt_client
        self.publish_mqtt = publish_mqtt
        # Month-change tracking for CSV rotation (disabled)
        self.current_month = None
        self.month_change_callback = None

    def set_month_change_callback(self, callback):
        # No-op: month change/rotation is disabled in single-file mode
        pass

    def rotate_csv_file(self, new_csv_path):
        # No-op: rotation is disabled in single-file mode
        pass

    def _check_month_change(self):
        # No-op: month change/rotation is disabled in single-file mode
        pass

    def _find_param_index(self, parameters, keywords):
        """Find parameter index by keyword matching (case insensitive)."""
        for i, param in enumerate(parameters):
            p_clean = param.lower().replace(" ", "").replace("_", "").replace(".", "")
            for kw in keywords:
                if kw in p_clean:
                    return i
        return None

    def _init_events_csv(self):
        """Initialize events log (blackouts, time jumps, etc.) - immediate flush."""
        try:
            if not self.events_path.exists():
                with open(self.events_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp_detected',
                        'event_type',           # BLACKOUT, TIME_JUMP, COMM_ERROR, etc.
                        'meter_name',
                        'details',              # JSON-style details
                        'count_before',
                        'count_after',
                        'estimated_start'
                    ])
                    f.flush()
                    os.fsync(f.fileno())
            # Append mode for events
            self.events_file = open(self.events_path, 'a', newline='', buffering=1)
            self.events_writer = csv.writer(self.events_file)
            
        except Exception as e:
            self.error_logger.error(f"Failed to init events CSV: {e}")
            # Don't raise - events logging is non-critical
            self.events_file = None
            self.events_writer = None

    def read_all(self, stdscr=None, inter_device_delay=0.1):
        """
        Dual-rate acquisition loop:
        - Runs every fast_poll_interval (0.5s) for blackout detection
        - Writes to main CSV only every slow_csv_interval (60s)

        Coordinates a complete reading cycle across all managed meters, including:
        - Data collection from each MeterDevice
        - Blackout detection via interruption count monitoring
        - CSV logging of readings (at slow interval)
        - MQTT publishing (if enabled)
        - UI callback execution (if provided)

        Args:
            stdscr (curses.window, optional): Curses screen object for UI updates.
            inter_device_delay (float): Delay in seconds between reading each device.
                                      Default: 0.1 seconds (100ms)

        Returns:
            None
        """
        current_time = time.time()
        
        # Throttle: Respect fast polling interval
        if current_time - self._last_poll_time < self.fast_poll_interval:
            return
        
        self._last_poll_time = current_time
        poll_timestamp = datetime.now()
        self.TotalReadings += 1
        
        # Check if month has changed and rotate CSV if needed
        self._check_month_change()
        
        # --- FAST POLL PHASE (Every 0.5s) ---
        for i, meter in enumerate(self.meters):
            meter_name = getattr(meter, 'name', f"Meter_{i+1}")
            state = self._meter_state.get(meter_name, {})
            
            try:
                # Fast read from meter
                regValue = meter.read_data()
                
                # --- REFINED BLACKOUT DETECTION (Feature 5/6 with Option C) ---
                # Process with refined logic (comm state machine, deferred confirmation)
                should_log, processed_values = self._process_meter_reading(meter_name, regValue)
                
                # Store latest values for slow CSV
                state['latest_values'] = processed_values
                state['last_poll_success'] = poll_timestamp
                self._meter_state[meter_name] = state
                
                # Update allRegValues for compatibility
                self.allRegValues[i] = processed_values.copy() if processed_values else regValue.copy()
                
            except Exception as e:
                self.error_logger.debug(f"Fast poll failed for {meter_name}: {e}")
                # Mark as comm error on exception
                self._meter_comm_state[meter_name] = False
            
            # MQTT publishing (every poll for real-time)
            if self.publish_mqtt and self.mqtt_client and state.get('latest_values'):
                meta = {
                    'device_id': getattr(meter, 'device_address', i + 1),
                    'model': getattr(meter, 'model', None),
                    'location': getattr(meter, 'location', None),
                }
                self.published_msg = self.mqtt_client.publish_message(
                    self.parameters, state['latest_values'], meter.name, meta=meta)
            
            # Inter-device delay
            if i < len(self.meters) - 1 and inter_device_delay > 0:
                time.sleep(inter_device_delay)
        
        # --- RTC DRIFT CHECK (Every 60s, independent of CSV writes) ---
        if self.time_sanitizer and (current_time - self._last_drift_check_time >= self._drift_check_interval):
            self._last_drift_check_time = current_time
            drift_event = self.time_sanitizer.check_drift()
            if drift_event:
                self._log_system_event(drift_event)

        # --- SLOW CSV WRITE PHASE (Every 60s) ---
        if current_time - self._last_csv_write_time >= self.slow_csv_interval:
            # Time sanity checks before writing
            if self.time_sanitizer:
                # Check for time jump between CSV writes
                for meter_name, state in self._meter_state.items():
                    values = state.get('latest_values')
                    if values and len(values) > 0:
                        current_ts = values[0]  # Timestamp is first element
                        if current_ts and self._last_csv_timestamp:
                            jump_event = self.time_sanitizer.check_discontinuity(
                                current_ts, self._last_csv_timestamp
                            )
                            if jump_event:
                                self._log_system_event(jump_event)
                        self._last_csv_timestamp = current_ts
                        break  # Only need to check once
            
            self._write_slow_csv()
            self._last_csv_write_time = current_time
            # Periodically prune old rows to enforce rolling retention
            self._maybe_prune_old_rows()
        
        # Update UI with latest values
        if self.ui_callback:
            self.ui_callback(self.TotalReadings, stdscr, self.allRegValues)

    def _write_row_safe(self, row):
        """
        Write row with power-loss durability and external rotation handling.
        Returns True if written successfully.
        """
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Check 1: Has file been deleted/rotated externally?
                if not os.path.exists(self.csv_path):
                    self._reopen_csv_recreate()
                
                # Check 2: Is handle still valid?
                if self.csv_file.closed:
                    self._reopen_csv_append()
                
                # Write and flush to OS buffer
                self.csv_writer.writerow(row)
                self.csv_file.flush()
                
                # Critical: Force physical write to disk (survives power loss)
                os.fsync(self.csv_file.fileno())
                return True
                
            except (IOError, OSError) as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                self.error_logger.error(f"CSV write failed after retries: {e}")
                return False
    
    def _reopen_csv_recreate(self):
        """File was deleted/rotated. Create new file with headers."""
        try:
            if hasattr(self, 'csv_file') and self.csv_file:
                self.csv_file.close()
        except:
            pass
            
        self.csv_file = open(self.csv_path, 'a', newline='', buffering=1)
        self.csv_writer = csv.writer(self.csv_file)
        
        # Write header if empty
        if os.path.getsize(self.csv_path) == 0:
            self.csv_writer.writerow(create_formatted_csv_header(self.parameters))
            self.csv_file.flush()
            os.fsync(self.csv_file.fileno())
    
    def _reopen_csv_append(self):
        """Simple reopen for append mode."""
        self.csv_file = open(self.csv_path, 'a', newline='', buffering=1)
        self.csv_writer = csv.writer(self.csv_file)

    def _log_blackout_event(self, detected_time, meter_name, count_before, count_after, frequency):
        """Write blackout to EVENTS.csv with immediate disk sync (survives power loss)."""
        if not self.events_writer:
            return
            
        try:
            # Estimate start time (polling interval ago, roughly)
            est_start = detected_time - timedelta(seconds=self.fast_poll_interval)
            
            row = [
                detected_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],  # Millis precision
                'BLACKOUT',
                meter_name,
                f'Int count jump {count_before}->{count_after}',
                count_before,
                count_after,
                est_start.strftime('%H:%M:%S.%f')[:-3]
            ]
            
            self.events_writer.writerow(row)
            self.events_file.flush()
            os.fsync(self.events_file.fileno())  # Critical: immediate disk write
            
            self.error_logger.info(
                f"BLACKOUT: {meter_name} {count_before}->{count_after} "
                f"at {detected_time.strftime('%H:%M:%S')}"
            )
            
        except Exception as e:
            self.error_logger.error(f"Failed to log blackout: {e}")

    def _log_system_event(self, event_dict):
        """
        Write system events (time corrections, battery fails, boot gaps, etc.) to EVENTS.csv.
        
        Args:
            event_dict: Dictionary containing event details with at minimum 'type' key
        """
        if not self.events_writer:
            return
            
        try:
            import json
            
            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],  # Millis precision
                event_dict.get('type', 'UNKNOWN'),
                'SYSTEM',  # meter_name column - system events use 'SYSTEM'
                json.dumps(event_dict),  # Full details as JSON string
                '',  # count_before - empty for system events
                '',  # count_after - empty for system events
                ''   # estimated_start - empty for system events
            ]
            
            self.events_writer.writerow(row)
            self.events_file.flush()
            os.fsync(self.events_file.fileno())  # Critical: immediate disk write
            
            self.error_logger.info(f"SYSTEM EVENT: {event_dict.get('type', 'UNKNOWN')}")
            
        except Exception as e:
            self.error_logger.error(f"Failed to log system event: {e}")

    def _log_event(self, timestamp, event_type, meter_name, details, count_before, count_after):
        """Universal event logger with immediate fsync for all event types."""
        try:
            # Ensure file handle is valid
            if not hasattr(self, 'events_file') or self.events_file is None or self.events_file.closed:
                self._init_events_csv()
            
            if not self.events_writer:
                return
            
            row = [
                timestamp,
                event_type,
                meter_name,
                details,
                str(count_before) if count_before != '' else '',
                str(count_after) if count_after != '' else '',
                ''  # estimated_start column (optional for some events)
            ]
            
            self.events_writer.writerow(row)
            self.events_file.flush()
            os.fsync(self.events_file.fileno())
            
            # Also log to error_logger for console visibility
            self.error_logger.info(f"[{event_type}] {meter_name}: {details}")
            
        except Exception as e:
            self.error_logger.error(f"Failed to log event: {e}")

    def _process_meter_reading(self, meter_name, reg_values):
        """
        Three-way detection for each meter reading:

        1. RPI↔USB COMM ERROR:  any value is -1
           → USB adapter unreachable (serial port lost, driver issue)
        2. USB↔METER COMM ERROR: all values are 0 (including cumulative counters)
           → Adapter connected but meter not responding on RS-485 bus
        3. TRUE BLACKOUT: Freq=0, V=0 BUT cumulative counters (Wh, OnHours) > 0
           → Line power lost, meter still alive and responding

        Key insight: cumulative counters (Wh Received, On Hours) never reset to 0
        as long as the meter is powered.  All-zeros means no real data came back.

        Returns: (should_log_to_csv, processed_values)
        """
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # --- Helper: safe value extraction ---
        def _val(idx):
            if idx is not None and len(reg_values) > idx:
                return reg_values[idx]
            return None

        freq_val  = _val(self._freq_idx)
        intr_val  = _val(self._intr_idx)
        wh_val    = _val(self._wh_idx)
        onhrs_val = _val(self._onhrs_idx)

        # ── CASE 1: RPI ↔ USB comm failure (any value is -1) ──────────────
        has_minus_one = any(v == -1 for v in reg_values if v is not None)
        was_healthy = self._meter_comm_state.get(meter_name, 'OK')

        if has_minus_one:
            if was_healthy != 'RPI_USB_ERROR':
                self._log_event(
                    timestamp=current_time,
                    event_type='RPI_USB_COMM_ERROR',
                    meter_name=meter_name,
                    details='Values contain -1: RPi cannot communicate with USB adapter',
                    count_before='', count_after=''
                )
                self._meter_comm_state[meter_name] = 'RPI_USB_ERROR'
            return True, reg_values  # Write -1s to CSV for audit trail

        # ── CASE 2: USB ↔ Meter comm failure (all values zero) ────────────
        # Check numeric data values only (skip index 0 which is the timestamp)
        numeric_values = reg_values[1:]  # everything after timestamp
        all_zero = all(
            (v == 0 or v == 0.0 or v == '0' or v == '0.0')
            for v in numeric_values if v is not None
        )

        if all_zero and len(numeric_values) > 0:
            if was_healthy != 'METER_COMM_ERROR':
                self._log_event(
                    timestamp=current_time,
                    event_type='METER_COMM_ERROR',
                    meter_name=meter_name,
                    details='All parameter values are 0: USB adapter cannot reach meter on RS-485 bus',
                    count_before='', count_after=''
                )
                self._meter_comm_state[meter_name] = 'METER_COMM_ERROR'
            return True, reg_values  # Write zeros to CSV for audit trail

        # ── If we reach here, we have real data from the meter ────────────
        # Transition logging: recover from any previous error state
        if was_healthy != 'OK':
            self._log_event(
                timestamp=current_time,
                event_type='COMM_RESTORED',
                meter_name=meter_name,
                details=f'Communication restored (was {was_healthy})',
                count_before='', count_after=''
            )
            self._meter_comm_state[meter_name] = 'OK'

        # Convert to numeric for blackout checks
        try:
            freq  = float(freq_val) if freq_val is not None else -1
            intr  = int(float(intr_val)) if intr_val is not None else -1
            wh    = float(wh_val) if wh_val is not None else -1
            onhrs = float(onhrs_val) if onhrs_val is not None else -1
        except (ValueError, TypeError):
            return True, reg_values  # Parse error, just write raw data

        # ── CASE 3: True blackout detection (Freq=0, cumulative counters > 0) ─
        last_intr = self._meter_last_valid_int.get(meter_name)
        blackout_state = self._meter_suspect_state.get(meter_name, {
            'active': False,
            'start_time': None,
            'start_int': None
        })

        if freq == 0 and (wh > 0 or onhrs > 0):
            # Meter is responding with real cumulative data but line frequency is 0
            # → TRUE BLACKOUT (AC line is dead)
            if not blackout_state.get('active', False):
                # Blackout just started
                blackout_state['active'] = True
                blackout_state['start_time'] = current_time
                blackout_state['start_int'] = intr
                self._meter_suspect_state[meter_name] = blackout_state
                self._log_event(
                    timestamp=current_time,
                    event_type='BLACKOUT_START',
                    meter_name=meter_name,
                    details=f'Freq=0 with cumulative counters intact (Wh={wh}, OnHrs={onhrs})',
                    count_before=str(last_intr) if last_intr is not None else '',
                    count_after=str(intr)
                )
        else:
            # Freq > 0 → line is alive
            if blackout_state.get('active', False):
                # Blackout just ended
                duration_note = f'Started: {blackout_state.get("start_time", "?")}'
                int_before = blackout_state.get('start_int', '?')
                blackout_state['active'] = False
                blackout_state['start_time'] = None
                self._meter_suspect_state[meter_name] = blackout_state
                self._log_event(
                    timestamp=current_time,
                    event_type='BLACKOUT_END',
                    meter_name=meter_name,
                    details=f'Power restored. {duration_note}',
                    count_before=str(int_before),
                    count_after=str(intr)
                )

        # Update last valid interruption count
        if intr >= 0:
            self._meter_last_valid_int[meter_name] = intr

        return True, reg_values

    def _write_slow_csv(self):
        """Write latest values to main CSV (60s intervals)."""
        try:
            # Ensure CSV file exists and is open before writing
            self._ensure_csv_file()
            # ...existing code...
            for i, meter in enumerate(self.meters):
                meter_name = getattr(meter, 'name', f"Meter_{i+1}")
                state = self._meter_state.get(meter_name, {})
                values = state.get('latest_values')
                if not values:
                    continue
                # Build row with same format as before
                formatted_row = [
                    getattr(meter, 'device_address', i + 1),
                    meter_name
                ]
                for j, value in enumerate(values):
                    if j == 0:  # Timestamp - keep as-is
                        formatted_row.append(value)
                        # Insert model after time
                        formatted_row.append(getattr(meter, 'model', 'Unknown'))
                    else:
                        param_name = self.parameters[j] if j < len(self.parameters) else "Unknown"
                        formatted_value = format_csv_value(value, param_name)
                        formatted_row.append(formatted_value)
                self._write_row_safe(formatted_row)
            # ...existing code...
        except Exception as e:
            self.error_logger.error(f"Slow CSV write failed: {e}")

    def _detect_and_repair_corruption(self):
        """
        Check existing CSV for concatenated lines on startup.
        Repairs if found (e.g., '2026-01-18 11:33:35...,DG_Changeover,2026-01-18 11:32:17').
        """
        if not os.path.exists(self.csv_path):
            return
            
        # Read first 100 lines to detect corruption pattern
        try:
            with open(self.csv_path, 'r', newline='') as f:
                lines = f.readlines()[:100]
        except:
            return
            
        # Pattern: Two ISO timestamps in one line = concatenation
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        
        # Check each line for multiple timestamps
        corruption_detected = False
        for line in lines:
            matches = re.findall(timestamp_pattern, line)
            if len(matches) > 1:  # More than one timestamp in a single line
                corruption_detected = True
                break
        
        if corruption_detected:
            self.error_logger.warning("CSV corruption detected (concatenated timestamps). Repairing...")
            self._repair_concatenated_lines()
    
    def _repair_concatenated_lines(self):
        """
        Split concatenated records and rewrite clean file atomically.
        """
        csv_path = Path(self.csv_path)
        temp_path = csv_path.with_suffix('.repair.tmp')
        
        try:
            # Read entire file
            with open(csv_path, 'r', newline='') as src:
                content = src.read()
            
            # Find all timestamps with surrounding context
            timestamp_pattern = r'(\d+,\w+,\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\w+(?:,[\d.]+)*)'
            
            # Split by timestamp pattern to extract individual records
            header = create_formatted_csv_header(self.parameters)
            expected_cols = len(header)
            
            with open(temp_path, 'w', newline='') as dst:
                writer = csv.writer(dst)
                writer.writerow(header)
                
                # Read original file again as CSV
                with open(csv_path, 'r', newline='') as src:
                    reader = csv.reader(src)
                    next(reader, None)  # Skip header
                    
                    for row in reader:
                        if not row or len(row) < 3:
                            continue
                        
                        # If row is too long, it's concatenated
                        if len(row) > expected_cols:
                            # Try to split it into multiple records
                            # Find timestamp indices (column index 2)
                            timestamp_indices = []
                            for i, cell in enumerate(row):
                                if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', cell):
                                    timestamp_indices.append(i)
                            
                            if len(timestamp_indices) > 1:
                                # Split at each timestamp
                                for idx, ts_pos in enumerate(timestamp_indices):
                                    # Extract record: go back 2 columns for Device_ID and Meter_Name
                                    start_pos = ts_pos - 2
                                    if start_pos < 0:
                                        start_pos = 0
                                    
                                    # End position is before next timestamp or end of row
                                    if idx + 1 < len(timestamp_indices):
                                        end_pos = timestamp_indices[idx + 1] - 2
                                    else:
                                        end_pos = len(row)
                                    
                                    record = row[start_pos:end_pos]
                                    if len(record) >= 3:  # At least ID, Name, Time
                                        writer.writerow(record[:expected_cols])
                            else:
                                # Just truncate to expected columns
                                writer.writerow(row[:expected_cols])
                        else:
                            # Normal row
                            writer.writerow(row[:expected_cols])
            
            # Atomic replace
            os.replace(temp_path, csv_path)
            self.error_logger.info("CSV corruption repaired successfully")
            
        except Exception as e:
            self.error_logger.error(f"Repair failed: {e}")
            if temp_path.exists():
                temp_path.unlink()

    def close(self):
        """Closes all CSV files safely."""
        # Close main CSV
        if hasattr(self, 'csv_file') and self.csv_file is not None and not self.csv_file.closed:
            try:
                self.csv_file.flush()
                self.csv_file.close()
            except Exception as e:
                print(f"Error closing CSV file: {e}")
        
        # Close events CSV with final sync
        if hasattr(self, 'events_file') and self.events_file is not None and not self.events_file.closed:
            try:
                self.events_file.flush()
                os.fsync(self.events_file.fileno())
                self.events_file.close()
            except Exception as e:
                print(f"Error closing events file: {e}")

    # --- Safe Retention with Timestamped Archives ---
    
    def _get_csv_start_time(self):
        """Get earliest timestamp in current CSV, or now if empty."""
        try:
            if os.path.exists(self.csv_path) and os.path.getsize(self.csv_path) > 100:
                with open(self.csv_path, 'r', newline='') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if not header:
                        return datetime.now()
                    
                    # Time column is index 2: Device_ID, Meter_Name, Time...
                    time_idx = 2 if len(header) > 2 else 0
                    
                    first_row = next(reader, None)
                    if first_row and len(first_row) > time_idx:
                        time_str = first_row[time_idx]
                        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            self.error_logger.debug(f"Could not read CSV start time: {e}")
        
        return datetime.now()
    
    def _maybe_prune_old_rows(self):
        """Check hourly if retention rotation is needed (file size > threshold)."""
        current_time = time.time()
        
        if current_time - self._last_prune_check < self.prune_check_interval:
            return
        
        self._last_prune_check = current_time
        
        # Sanity check: Don't rotate if time is suspicious (year < 2024)
        if datetime.now().year < 2024:
            self.error_logger.warning("Suspicious system time (year<2024), skipping retention rotation")
            return
        
        try:
            if not os.path.exists(self.csv_path):
                return
                
            file_size = os.path.getsize(self.csv_path)
            # Only rotate if file exceeds threshold (default 1MB)
            if file_size < self.rotation_size_threshold:
                return
            
            self._perform_safe_rotation()
            
        except Exception as e:
            self.error_logger.error(f"Retention check failed: {e}")

    def _perform_safe_rotation(self):
        """
        Rotate CSV to backup with timestamp naming [START]_TO_[END].
        Atomic operation: copy -> verify -> fsync -> truncate original.
        """
        try:
            # Get time range of current file
            start_time = self._current_csv_start_time or self._get_csv_start_time()
            end_time = datetime.now()
            
            # Format: 2026-01-18_103000_TO_2026-01-25_143000.csv
            start_str = start_time.strftime('%Y-%m-%d_%H%M%S')
            end_str = end_time.strftime('%Y-%m-%d_%H%M%S')
            archive_name = f"{start_str}_TO_{end_str}.csv"
            archive_path = self.backup_dir / archive_name
            
            # Step 1: Copy current file to backup (with verification)
            self.error_logger.info(f"Rotating CSV to backup: {archive_name}")
            
            # Copy with shutil (preserves metadata)
            shutil.copy2(self.csv_path, archive_path)
            
            # Verify copy succeeded (size match)
            if not archive_path.exists():
                raise IOError("Archive file not created after copy")
            
            original_size = os.path.getsize(self.csv_path)
            archive_size = archive_path.stat().st_size
            
            if archive_size < original_size * 0.9:  # Allow 10% tolerance
                raise IOError(f"Archive size mismatch: {archive_size} vs {original_size}")
            
            # Step 2: Sync archive to disk (ensure it's safe before truncating)
            with open(archive_path, 'a') as f:
                f.flush()
                os.fsync(f.fileno())
            
            # Step 3: Now safe to truncate original file
            # Close current handle
            try:
                if self.csv_file and not self.csv_file.closed:
                    self.csv_file.flush()
                    self.csv_file.close()
            except:
                pass
            
            # Truncate file and write fresh headers
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                headers = create_formatted_csv_header(self.parameters)
                writer.writerow(headers)
                f.flush()
                os.fsync(f.fileno())
            
            # Reopen for append
            self.csv_file = open(self.csv_path, 'a', newline='', buffering=1)
            self.csv_writer = csv.writer(self.csv_file)
            
            # Update start time for next archive
            self._current_csv_start_time = datetime.now()
            
            # Log rotation event
            self._log_system_event({
                'type': 'CSV_ROTATION',
                'archive_file': archive_name,
                'rows_moved': 'retained_full_file',
                'size_mb': round(archive_size / (1024*1024), 2)
            })
            
            self.error_logger.info(f"CSV rotation complete: {archive_name} ({archive_size} bytes)")
            
            # Step 4: Cleanup old archives (>14 days)
            self._cleanup_old_archives()
            
        except Exception as e:
            self.error_logger.error(f"Rotation failed: {e}")
            # Ensure file handle is valid after failure
            self._ensure_csv_handle()

    def _cleanup_old_archives(self):
        """Remove archives older than retention_days."""
        try:
            cutoff = datetime.now() - timedelta(days=self.retention_days)
            removed_count = 0
            
            for archive_file in self.backup_dir.glob("*.csv"):
                try:
                    # Parse filename for end timestamp
                    # Format: 2026-01-18_103000_TO_2026-01-25_143000.csv
                    name = archive_file.name
                    if '_TO_' in name:
                        end_part = name.split('_TO_')[1]
                        end_timestamp = end_part.replace('.csv', '')
                        end_dt = datetime.strptime(end_timestamp, '%Y-%m-%d_%H%M%S')
                        
                        if end_dt < cutoff:
                            archive_file.unlink()
                            removed_count += 1
                            self.error_logger.debug(f"Removed old archive: {archive_file.name}")
                            
                except Exception as e:
                    self.error_logger.warning(f"Could not parse archive date {archive_file}: {e}")
            
            if removed_count > 0:
                self.error_logger.info(f"Cleaned up {removed_count} old archives")
                
        except Exception as e:
            self.error_logger.error(f"Archive cleanup failed: {e}")

    def _ensure_csv_handle(self):
        """Reopen CSV file handles if closed or invalid."""
        try:
            if not hasattr(self, 'csv_file') or self.csv_file.closed:
                self.csv_file = open(self.csv_path, 'a', newline='', buffering=1)
                self.csv_writer = csv.writer(self.csv_file)
        except Exception as e:
            self.error_logger.error(f"Failed to reopen CSV: {e}")
