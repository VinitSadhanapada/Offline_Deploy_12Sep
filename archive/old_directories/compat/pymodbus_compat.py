"""Compatibility shim for pymodbus across versions.

This module patches `pymodbus.constants` to provide a minimal `ExcCodes`
symbol when it's missing. Import this module early (before other pymodbus
imports) to avoid ImportError: cannot import name 'ExcCodes' from
`pymodbus.constants` on systems with differing pymodbus versions.
"""
from __future__ import annotations

try:
    import pymodbus.constants as _pm_constants
except Exception:
    # If pymodbus is not installed yet, nothing to patch now.
    _pm_constants = None

if _pm_constants is not None:
    try:
        if not hasattr(_pm_constants, "ExcCodes"):
            class ExcCodes:
                IllegalFunction = 0x01
                IllegalAddress = 0x02
                IllegalValue = 0x03
                SlaveFailure = 0x04
                Acknowledge = 0x05
                SlaveBusy = 0x06
                MemoryParityError = 0x08
                GatewayPathUnavailable = 0x0A
                GatewayNoResponse = 0x0B

            setattr(_pm_constants, "ExcCodes", ExcCodes)
    except Exception:
        # Be defensive: any failure here should not break the importing program.
        pass
