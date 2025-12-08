#!/usr/bin/env python3
import datetime
import random
import elmeasure_LG6400 as LG6400
import elmeasure_LG5220 as LG5220
import elmeasure_LG5310 as LG5310
import elmeasure_EN8410 as EN8410
import elmeasure_iELR300 as ELR300

from macros import DEV_ELM_LG6400, DEV_ELM_LG5310, DEV_ELM_LG5220, DEV_ELM_EN8400, DEV_ELM_EN8100, DEV_ELM_EN8410, DEV_ELM_ELR300
from macros import PARAMETERS

"""
MeterDevice Module for Individual Meter Communication.

This module defines the MeterDevice class which handles communication with
individual electrical meters via Modbus RTU protocol or simulation mode.
Supports multiple meter models with configurable parameters.
"""

class MeterDevice:
    """
    Represents a single meter device (real or simulated).

    Supports both real hardware communication via Modbus RTU and simulation mode
    for testing and development. Each device can read multiple electrical parameters
    such as voltage, current, power, and harmonics.

    Args:
        name (str): Device name.
        model (str): Device model/type.
        parameters (list): List of parameter names.
        client: Modbus client instance (None for simulation).
        error_file: File object for error logging.
        simulation_mode (bool): True for simulation, False for real meter.

    Attributes:
        name (str): Device identifier.
        model (str): Device model type.
        parameters (List[str]): Parameters being monitored.
        readings_count (int): Total number of successful readings performed.
        last_reading_time (datetime): Timestamp of most recent successful reading.
        simulation_mode (bool): Current operating mode (simulation vs hardware).
    
    Example:
        >>> # Create a simulated device
        >>> device = MeterDevice(
        ...     name="Main Meter", 
        ...     model="LG6400", 
        ...     parameters=["Voltage", "Current", "Power"],
        ...     simulation_mode=True
        ... )
        >>> readings = device.read_data()
        >>> print(f"Voltage: {readings[1]}V")
        
    Methods:
        read_data(): Returns a list of parameter values (simulated or real).
    """
    def __init__(self, name, model, parameters, client=None, error_file=None, simulation_mode=False, device_address=1):
        """
        Initialize a new MeterDevice instance.
        
        Args:
            name (str): Device identifier
            model (str): Device model (e.g., "LG6400")
            parameters (List[str]): Parameter names to read
            client (ModbusClient, optional): Modbus client for hardware communication
            error_file (TextIO, optional): Error logging file handle
            simulation_mode (bool): Enable simulation mode
            device_address (int): Modbus device address (1-247)
        """
        self.name = name
        self.model = model
        self.parameters = parameters
        self.client = client
        self.error_file = error_file
        self.simulation_mode = simulation_mode
        self.device_address = device_address
        self.reg_values = [0] * len(parameters)

    def read_data(self):
        """
        Read current parameter values from the meter device.
        
        Performs either hardware communication via Modbus or generates simulated
        data based on the simulation_mode setting. Returns a complete set of
        parameter readings with timestamp.
        
        Returns:
            List: Parameter values in the same order as self.parameters.
                 - Element 0: ISO format timestamp string (YYYY-MM-DD HH:MM:SS)
                 - Elements 1+: Numerical readings as floats
                 
        Raises:
            ConnectionError: When hardware communication fails (non-simulation mode).
            ValueError: When parameter parsing or validation fails.
            ModbusException: When Modbus protocol errors occur.
            
        Example:
            >>> readings = device.read_data()
            >>> timestamp = readings[0]      # "2025-01-21 14:30:25"
            >>> voltage = readings[1]        # 230.5
            >>> current = readings[2]        # 5.2
            
        Note:
            In simulation mode, generates realistic values with small random variations
            to simulate actual meter behavior. Hardware mode requires a valid Modbus
            client connection. If no client connection is available in hardware mode,
            returns -1 for all parameter values while maintaining timestamp.
        """
        if self.simulation_mode:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            values = [now]
            for _ in range(1, len(self.parameters)):
                values.append(round(random.uniform(0, 500), 2))
            self.reg_values = values
        else:
            # Check if client connection exists
            if self.client is None:
                # No hardware connection available - return -1 for all values
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.reg_values = [now] + [-1] * (len(self.parameters) - 1)
                if self.error_file:
                    self.error_file.write(f"[{now}] No hardware client connection available for device {self.name}\n")
            else:
                # Actual meter reading logic based on model
                if self.model == "LG6400":
                    self.reg_values = LG6400.ReadMeterData(self.client, self.device_address, self.parameters, self.error_file)
                elif self.model == "EN8400":
                    self.reg_values = LG6400.ReadMeterData(self.client, self.device_address, self.parameters, self.error_file)
                elif self.model == "EN8100":
                    self.reg_values = LG6400.ReadMeterData(self.client, self.device_address, self.parameters, self.error_file)
                elif self.model == "LG+5220":
                    self.reg_values = LG5220.ReadMeterData(self.client, self.device_address, self.parameters, self.error_file)
                elif self.model == "LG+5310":
                    self.reg_values = LG5310.ReadMeterData(self.client, self.device_address, self.parameters, self.error_file)
                elif self.model == "EN8410":
                    self.reg_values = EN8410.ReadMeterData(self.client, self.device_address, self.parameters, self.error_file)
                elif self.model == "ELR300":
                    self.reg_values = ELR300.ReadMeterData(self.client, self.device_address, self.parameters, self.error_file)
                else:
                    self.reg_values = [0] * len(self.parameters)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.reg_values[0] = now
        return self.reg_values