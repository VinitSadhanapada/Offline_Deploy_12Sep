#!/usr/bin/env python3
"""
Configuration Constants and Device Definitions.

This module centralizes all configuration constants, device model definitions,
parameter names, and register addresses used throughout the meter reading system.
Provides a single location for system-wide configuration management.

Constants defined:
    - Device model identifiers (DEV_ELM_*)
    - Device naming arrays (DEVICE_NAMES)
    - Parameter name lists (PARAMETERS)
    - Modbus register addresses (REG_ADDRESSES)
    
Device Support:
    - LG6400: Advanced power meter with harmonic analysis
    - LG5220/LG5310: Standard power meters
    - EN8410/EN8400/EN8100: Energy meters
    - ELR300: Compact energy meter
    
Usage:
    Import required constants in other modules:
    >>> from macros import DEVICE_NAMES, PARAMETERS, DEV_ELM_LG6400
    
Author: Selvakumar Sadhanpada
Date: 21/07/25
Version: 1.0
"""

import elmeasure_LG6400 as LG6400
import elmeasure_LG5220 as LG5220
import elmeasure_LG5310 as LG5310
import elmeasure_EN8410 as EN8410
import elmeasure_iELR300 as ELR300

# Device Types
# Device Type Constants
"""
Device Model Identifiers.

String constants that identify different meter models supported by the system.
Used when configuring MeterDevice instances to specify the hardware type.
"""
DEV_ELM_LG6400 = "LG6400"
DEV_ELM_LG5310 = "LG+5310"
DEV_ELM_LG5220 = "LG+5220"
DEV_ELM_EN8400 = "EN8400"
DEV_ELM_EN8100 = "EN8100"
DEV_ELM_EN8410 = "EN8410"
DEV_ELM_ELR300 = "ELR300"

# Device Names Array
"""
Human-readable device names for display purposes.

List of string identifiers used in dashboards and logging to provide
meaningful names for meter devices. Index corresponds to device position
in the meters array.

Example:
    >>> print(f"Reading from {DEVICE_NAMES[0]}")  # "Device 1"
"""
DEVICE_NAMES = ["Device 1", "Device 2", "Device 3", "Device 4", "Device 5", "Device 6", "Device 7", "Device 8", "Device 9", "Device 10",
                    "Device 11", "Device 12", "Device 13", "Device 14", "Device 15"]


# Parameter Names Array
"""
Electrical parameter names for data collection.

Ordered list of parameter names that define what electrical measurements
are collected from each meter device. The order must match the register
addresses in REG_ADDRESSES.

Parameters include:
    - Time: Timestamp of reading
    - Power measurements (total, per-phase)
    - Voltage measurements (average, per-phase)
    - Current measurements (average, per-phase)  
    - Frequency
    - Energy counters
    - Harmonic measurements
    
Note: First parameter 'Time' is always added automatically by MeterDevice
"""
PARAMETERS = ['Time', LG6400.WATTS_TOTAL_STR, LG6400.WATTS_R_PH_STR, LG6400.WATTS_Y_PH_STR, LG6400.WATTS_B_PH_STR,
                        LG6400.PH_AVG_STR, LG6400.PH_R_PH_STR, LG6400.PH_Y_PH_STR, LG6400.PH_B_PH_STR,
                        LG6400.VLN_AVG_STR, LG6400.V_R_PH_STR, LG6400.V_Y_PH_STR, LG6400.V_B_PH_STR,
                        LG6400.A_AVG_STR, LG6400.A_R_PH_STR, LG6400.A_Y_PH_STR, LG6400.A_B_PH_STR,
                        LG6400.FREQUENCY_STR,
                        LG6400.WH_RCVD_STR,
                        LG6400.LOAD_HRS_DL_STR,
                        LG6400.NO_OF_INTR_STR,
                        LG6400.ON_HRS_STR,
                        LG6400.V_R_HARMO_STR, LG6400.V_Y_HARMO_STR, LG6400.V_B_HARMO_STR,
                        LG6400.A_R_HARMO_STR, LG6400.A_Y_HARMO_STR, LG6400.A_B_HARMO_STR]

# Register Addresses Array
"""
Modbus register addresses corresponding to PARAMETERS.

Array of register addresses used for Modbus RTU communication with meters.
Each address corresponds to the parameter at the same index in PARAMETERS
(excluding 'Time' which is generated automatically).

Usage:
    Used internally by MeterDevice for hardware communication.
    Should not be modified unless adding support for new parameters.
"""
REG_ADDRESSES = [         LG6400.WATTS_TOTAL_ADD, LG6400.WATTS_R_PH_ADD, LG6400.WATTS_Y_PH_ADD, LG6400.WATTS_B_PH_ADD,
                        LG6400.PH_AVG_ADD, LG6400.PH_R_PH_ADD, LG6400.PH_Y_PH_ADD, LG6400.PH_B_PH_ADD,
                        LG6400.VLN_AVG_ADD, LG6400.V_R_PH_ADD, LG6400.V_Y_PH_ADD, LG6400.V_B_PH_ADD,
                        LG6400.A_AVG_ADD, LG6400.A_R_PH_ADD, LG6400.A_Y_PH_ADD, LG6400.A_B_PH_ADD,
                        LG6400.FREQUENCY_ADD,
                        LG6400.WH_RCVD_ADD,
                        LG6400.LOAD_HRS_DL_ADD,
                        LG6400.NO_OF_INTR_ADD,
                        LG6400.ON_HRS_ADD,
                        LG6400.V_R_HARMO_ADD, LG6400.V_Y_HARMO_ADD, LG6400.V_B_HARMO_ADD,
                        LG6400.A_R_HARMO_ADD, LG6400.A_Y_HARMO_ADD, LG6400.A_B_HARMO_ADD]

