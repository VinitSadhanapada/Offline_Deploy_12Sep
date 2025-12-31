#!/usr/bin/env python3
import csv
import time
from datetime import datetime, timedelta
from pathlib import Path


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
    DEFAULT_RETENTION_DAYS = 7

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

    def __init__(self, meters, parameters, csv_filenames, ui_callback=None, mqtt_client=None, publish_mqtt=False):
        """
        Initialize MeterManager with devices and configuration.

        Args:
            meters (List[MeterDevice]): Meter devices to manage
            parameters (List[str]): Parameter names for all devices
            csv_filenames (List[str]): CSV log file paths (should be a single file per location)
            ui_callback (callable, optional): UI update function
            mqtt_client (object, optional): MQTT client for publishing
            publish_mqtt (bool): Enable MQTT message publishing
        """
        self.meters = meters
        self.parameters = parameters

        # Only one CSV file per location is supported
        if len(csv_filenames) != 1:
            raise ValueError(
                "MeterManager expects a single CSV file per location (all meters in one file).")
        # Track CSV path for retention management
        self.csv_path = csv_filenames[0]
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
        self.ui_callback = ui_callback
        self.allRegValues = [[0] * len(parameters) for _ in meters]
        self.published_msg = 0
        self.TotalReadings = 0
        self.mqtt_client = mqtt_client
        self.publish_mqtt = publish_mqtt
        # Rolling log retention controls
        self.retention_days = self.DEFAULT_RETENTION_DAYS
        self._last_prune_epoch = 0  # epoch seconds of last prune

    def read_all(self, stdscr=None, inter_device_delay=0.1):
        """
        Read data from all meters and perform associated operations.

        Coordinates a complete reading cycle across all managed meters, including:
        - Data collection from each MeterDevice
        - CSV logging of readings
        - MQTT publishing (if enabled)
        - UI callback execution (if provided)

        This method is thread-safe and handles errors gracefully, ensuring that
        failure in one meter doesn't prevent reading from others.

        Args:
            stdscr (curses.window, optional): Curses screen object for UI updates.
                                            If provided and ui_callback is set,
                                            passes to callback for display updates.
            inter_device_delay (float): Delay in seconds between reading each device.
                                      Default: 0.1 seconds (100ms)

        Returns:
            None

        Side Effects:
            - Increments self.TotalReadings counter
            - Updates self.allRegValues with latest readings
            - Writes new rows to CSV files
            - Publishes MQTT messages (if enabled)
            - Calls UI callback (if configured)

        Example:
            >>> manager.read_all()  # Simple reading cycle
            >>> manager.read_all(inter_device_delay=0.2)  # With 200ms delay between devices

        Note:
            The stdscr parameter exists for backwards compatibility with legacy
            curses-based implementations but is not used in the modern console
            dashboard (print_dashboard2.py).
        """
        self.TotalReadings += 1
        for i, meter in enumerate(self.meters):
            regValue = meter.read_data()
            # Ensure CSV file exists and is open before writing
            self._ensure_csv_file()
            try:
                formatted_row = [
                    getattr(meter, 'device_address', i +
                            1), getattr(meter, 'name', f"Meter_{i+1}")
                ]
                for j, value in enumerate(regValue):
                    if j == 0:  # Timestamp - keep as-is
                        formatted_row.append(value)
                        # Insert model after time
                        formatted_row.append(
                            getattr(meter, 'model', 'Unknown'))
                    else:
                        param_name = self.parameters[j] if j < len(
                            self.parameters) else "Unknown"
                        formatted_value = format_csv_value(value, param_name)
                        formatted_row.append(formatted_value)
                self.csv_writer.writerow(formatted_row)
                self.csv_file.flush()
            except Exception as e:
                print(f"Error writing to CSV file: {e}")

            if self.publish_mqtt and self.mqtt_client:
                meta = {
                    'device_id': getattr(meter, 'device_address', i + 1),
                    'model': getattr(meter, 'model', None),
                    'location': getattr(meter, 'location', None),
                }
                self.published_msg = self.mqtt_client.publish_message(
                    self.parameters, regValue, meter.name, meta=meta)
            self.allRegValues[i] = regValue.copy()

            # Add delay between device reads to avoid Modbus conflicts
            if i < len(self.meters) - 1 and inter_device_delay > 0:
                time.sleep(inter_device_delay)
        if self.ui_callback and stdscr is not None:
            self.ui_callback(self.TotalReadings, stdscr, self.allRegValues)
        # Periodically prune old rows to enforce rolling retention
        self._maybe_prune_old_rows()

    def close(self):
        """Closes the CSV file safely."""
        if hasattr(self, 'csv_file') and self.csv_file is not None and not self.csv_file.closed:
            try:
                self.csv_file.close()
            except Exception as e:
                print(f"Error closing CSV file: {e}")

    # --- Rolling retention helpers ---
    def _maybe_prune_old_rows(self):
        """
        Prune CSV rows older than retention_days.

        To avoid heavy I/O on every cycle, this runs at most once per hour.
        """
        now = time.time()
        # Run at most once per hour
        if now - self._last_prune_epoch < 3600:
            return
        self._last_prune_epoch = now
        try:
            self._prune_csv_older_than(self.retention_days)
        except Exception as e:
            # Best-effort: never break logging due to retention maintenance
            print(f"Retention prune skipped due to error: {e}")

    def _prune_csv_older_than(self, days):
        """
        Rewrite the CSV keeping only rows whose timestamp column is within the last `days`.

        Assumes the CSV header is: [Device_ID, Meter_Name, Time, Model, ...].
        The Time column index is 2 and formatted as '%Y-%m-%d %H:%M:%S'.
        """
        if not self.csv_path:
            return
        csv_path = Path(self.csv_path)
        if not csv_path.exists():
            return

        # Close current writer to allow safe rewrite
        try:
            if self.csv_file and not self.csv_file.closed:
                self.csv_file.flush()
                self.csv_file.close()
        except Exception:
            pass

        cutoff = datetime.now() - timedelta(days=days)
        tmp_path = csv_path.with_suffix(csv_path.suffix + '.tmp')

        try:
            kept_rows = 0
            with open(csv_path, 'r', newline='') as fin, open(tmp_path, 'w', newline='') as fout:
                reader = csv.reader(fin)
                writer = csv.writer(fout)

                header = next(reader, None)
                if header is None:
                    # Empty file; nothing to do
                    pass
                else:
                    # Write header as-is
                    writer.writerow(header)
                    time_col_idx = 2  # Device_ID, Meter_Name, Time, Model, ...
                    for row in reader:
                        # Basic guard: malformed rows
                        if len(row) <= time_col_idx:
                            continue
                        ts_str = row[time_col_idx]
                        try:
                            ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                        except Exception:
                            # If unparsable, keep the row (avoid accidental data loss)
                            writer.writerow(row)
                            kept_rows += 1
                            continue

                        if ts >= cutoff:
                            writer.writerow(row)
                            kept_rows += 1

            # Atomically replace original with pruned file
            os_replace = getattr(__import__('os'), 'replace')
            os_replace(str(tmp_path), str(csv_path))
        except Exception as e:
            # Cleanup temp on failure
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            raise e
        finally:
            # Reopen the CSV for appending and reset writer
            try:
                self.csv_file = open(self.csv_path, 'a', newline='')
                self.csv_writer = csv.writer(self.csv_file)
            except Exception as e:
                print(f"Error reopening CSV after prune: {e}")
