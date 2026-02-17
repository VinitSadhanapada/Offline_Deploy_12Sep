# Logging Disabled Files

The following files have all logging output completely disabled using logging.disable(logging.CRITICAL):

- src/utils/time_sanitizer.py
- src/devices/meter_manager.py

To re-enable logging, remove or comment out the logging.disable(logging.CRITICAL) line at the top of each file.
