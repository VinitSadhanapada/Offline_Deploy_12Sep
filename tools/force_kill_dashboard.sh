#!/bin/bash
# Kill all running simple_rpi_dashboard.py processes with SIGKILL

pkill -9 -f simple_rpi_dashboard.py

if [ $? -eq 0 ]; then
    echo "All simple_rpi_dashboard.py processes killed (SIGKILL)."
else
    echo "No matching processes found or kill failed."
fi
