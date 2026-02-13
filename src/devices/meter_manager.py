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
                 fast_poll_interval=0, slow_csv_interval=60):
        """
        Initialize MeterManager with devices and configuration.

        Dual-rate architecture:
        - fast_poll_interval: Seconds between blackout checks (default 0.5)
        - FSAT POLL INTERVAL REMVOED TO REDUCE LATENCY BETWEEN READINGS
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
            self._meter_comm_state[name] = True  # Assume healthy start
            self._meter_last_valid_int[name] = None
            self._meter_suspect_state[name] = {
                'suspect_timestamp': None,  # When we first saw Freq=0,Int=0
                'suspect_last_int': None,
                'pending_confirmation': False
            }
        
        # Find interruption and frequency parameter indices once
        self._intr_idx = self._find_param_index(parameters, ['interruption', 'intr', 'no of interruption', 'noofintr'])
        self._freq_idx = self._find_param_index(parameters, ['frequency', 'freq'])
        
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

        # Setup events CSV in backup folder (fast, immediate flush for blackout detection)
        self.events_path = self.backup_dir / "EVENTS.csv"
        # Migrate old EVENTS.csv from data/csv/ to backup/ if it exists
        old_events = data_dir / "EVENTS.csv"
        if old_events.exists() and not self.events_path.exists():
            try:
                shutil.move(str(old_events), str(self.events_path))
                self.error_logger.info(f"Migrated EVENTS.csv to backup folder")
            except Exception as e:
                self.error_logger.warning(f"Could not migrate old EVENTS.csv: {e}")
        elif old_events.exists() and self.events_path.exists():
            # Append old data to new, then remove old
            try:
                with open(old_events, 'r') as old_f:
                    lines = old_f.readlines()
                if len(lines) > 1:  # Has data beyond header
                    with open(self.events_path, 'a') as new_f:
                        new_f.writelines(lines[1:])  # Skip header
                old_events.unlink()
                self.error_logger.info("Merged old EVENTS.csv into backup/EVENTS.csv")
            except Exception as e:
                self.error_logger.warning(f"Could not merge old EVENTS.csv: {e}")
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
        
        # --- SLOW CSV WRITE PHASE (Every 60s) ---
        if current_time - self._last_csv_write_time >= self.slow_csv_interval:
            # Time sanity checks before writing
            if self.time_sanitizer:
                # Check for runtime drift (system vs RTC)
                drift_event = self.time_sanitizer.check_drift()
                if drift_event:
                    self._log_system_event(drift_event)
                
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
        Process single meter reading with refined detection logic (Option C deferred confirmation).
        
        Features:
        - Comm Error State Machine: Single START/END events (not every cycle)
        - Blackout Detection: Freq=0 AND Int increased proves line dead
        - Option C Deferred: Suspect state (Freq=0,Int=0) waits for next poll confirmation
        - False Positive Filter: Ignores Int increases if Freq>0 (meter glitch, not blackout)
        
        Returns: (should_log_to_csv, processed_values)
        """
        freq_idx = self._freq_idx
        intr_idx = self._intr_idx
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Extract values (handle index bounds)
        freq_val = reg_values[freq_idx] if freq_idx is not None and len(reg_values) > freq_idx else -1
        intr_val = reg_values[intr_idx] if intr_idx is not None and len(reg_values) > intr_idx else -1
        
        # --- FEATURE 5: Comm Error State Machine ---
        comm_healthy = (freq_val != -1 and intr_val != -1)
        was_healthy = self._meter_comm_state.get(meter_name, True)
        
        if comm_healthy != was_healthy:
            if comm_healthy:
                # Recovery from comm error
                self._log_event(
                    timestamp=current_time,
                    event_type='COMM_ERROR_END',
                    meter_name=meter_name,
                    details='Communication restored',
                    count_before='',
                    count_after=''
                )
                self._meter_comm_state[meter_name] = True
            else:
                # Entered comm error
                self._log_event(
                    timestamp=current_time,
                    event_type='COMM_ERROR_START',
                    meter_name=meter_name,
                    details=f'Values became -1 (Freq:{freq_val}, Int:{intr_val})',
                    count_before=str(self._meter_last_valid_int.get(meter_name, 'N/A')),
                    count_after='-1'
                )
                self._meter_comm_state[meter_name] = False
        
        # If comm error, don't process for blackout detection
        if not comm_healthy:
            return True, reg_values  # Still write -1 to CSV
        
        # Convert to numeric for checks
        try:
            freq = float(freq_val)
            intr = int(float(intr_val))
        except (ValueError, TypeError):
            return True, reg_values  # Parse error, treat as data
        
        # --- FEATURE 4 & 6: Blackout Detection (Option C Deferred) ---
        last_intr = self._meter_last_valid_int.get(meter_name)
        suspect_state = self._meter_suspect_state.get(meter_name, {
            'suspect_timestamp': None,
            'suspect_last_int': None,
            'pending_confirmation': False
        })
        
        # Check for deferred confirmation from previous suspect state
        if suspect_state.get('pending_confirmation', False):
            prev_intr = suspect_state.get('suspect_last_int')
            
            if prev_intr is not None and intr > prev_intr:
                # CONFIRMED: Int increased since suspect reading
                # This was a real blackout that started in previous cycle
                self._log_event(
                    timestamp=current_time,
                    event_type='BLACKOUT_CONFIRMED',
                    meter_name=meter_name,
                    details=f'Confirmed from suspect state. Start: {suspect_state.get("suspect_timestamp")}',
                    count_before=str(prev_intr),
                    count_after=str(intr)
                )
                # Also log the main BLACKOUT event
                self._log_event(
                    timestamp=current_time,
                    event_type='BLACKOUT',
                    meter_name=meter_name,
                    details=f'Line blackout detected (Freq=0 with Int increase)',
                    count_before=str(prev_intr),
                    count_after=str(intr)
                )
            
            elif freq > 0:
                # Was comm error or false positive, not blackout (recovered without Int increase)
                self._log_event(
                    timestamp=current_time,
                    event_type='SUSPECT_RESOLVED',
                    meter_name=meter_name,
                    details='Freq recovered, no Int increase - was comm error or glitch',
                    count_before=str(prev_intr) if prev_intr is not None else '',
                    count_after=str(intr)
                )
            
            # Clear suspect state
            suspect_state['pending_confirmation'] = False
            suspect_state['suspect_timestamp'] = None
            self._meter_suspect_state[meter_name] = suspect_state
        
        # Current cycle detection
        if freq == 0:
            if last_intr is not None and intr > last_intr:
                # FEATURE 6: Immediate detection if Freq=0 AND Int already increased
                # This catches ongoing blackout
                self._log_event(
                    timestamp=current_time,
                    event_type='BLACKOUT',
                    meter_name=meter_name,
                    details='Line blackout (Freq=0 with Int increase)',
                    count_before=str(last_intr),
                    count_after=str(intr)
                )
            elif intr == 0 and (last_intr == 0 or last_intr is None):
                # SUSPECT state: Freq=0, Int=0 (rare on UPS)
                # Option C: Defer confirmation to next poll
                suspect_state['suspect_timestamp'] = current_time
                suspect_state['suspect_last_int'] = intr
                suspect_state['pending_confirmation'] = True
                self._meter_suspect_state[meter_name] = suspect_state
                # Don't log yet - wait for next poll to confirm
        
        # Update last valid Int (only if not -1)
        if intr_val != -1:
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
