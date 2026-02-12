#!/bin/bash

# Set the output archive name and destination
ARCHIVE_NAME="rpi_core_files_$(date +%Y%m%d_%H%M%S).tar.gz"
ARCHIVE_PATH="/home/pi/$ARCHIVE_NAME"

# List of critical files and folders to include
tar -czvf "$ARCHIVE_PATH" \
    /home/pi/Desktop/offline-setup-12Sep/src/devices/meter_manager.py \
    /home/pi/Desktop/offline-setup-12Sep/src/devices/meter_device.py \
    /home/pi/Desktop/offline-setup-12Sep/src/devices/elmeasure_LG6400.py \
    /home/pi/Desktop/offline-setup-12Sep/src/devices/elmeasure_LG5310.py \
    /home/pi/Desktop/offline-setup-12Sep/src/devices/elmeasure_EN8410.py \
    /home/pi/Desktop/offline-setup-12Sep/src/devices/elmeasure_iELR300.py \
    /home/pi/Desktop/offline-setup-12Sep/data/csv/data_log.xlsx \
    /home/pi/Desktop/offline-setup-12Sep/config/config.json \
    /home/pi/Desktop/offline-setup-12Sep/config/device_config.json \
    /home/pi/Desktop/offline-setup-12Sep/src/dashboard/simple_meter_ui.py \
    /home/pi/Desktop/offline-setup-12Sep/src/dashboard/simple_rpi_dashboard.py \
    /home/pi/Desktop/offline-setup-12Sep/src/dashboard/terminal_meter_ui.py \
    /home/pi/Desktop/offline-setup-12Sep/src/utils/paths.py \
    /home/pi/Desktop/offline-setup-12Sep/src/utils/rtc_module.py \
    /home/pi/Desktop/offline-setup-12Sep/src/utils/set_rtc_from_system.py \
    /home/pi/Desktop/offline-setup-12Sep/src/utils/configure_device.py \
    /home/pi/Desktop/offline-setup-12Sep/scripts/launchers/SimpleMeterUI_Admin.desktop \
    /home/pi/Desktop/offline-setup-12Sep/scripts/setup/one_click_system_py313.sh \
    /home/pi/Desktop/offline-setup-12Sep/master_setup.sh \
    /home/pi/Desktop/offline-setup-12Sep/quick_setup.sh \
    /home/pi/Desktop/offline-setup-12Sep/preflight_check.sh \
    /home/pi/Desktop/offline-setup-12Sep/src/network/mqtt_client.py

echo "Archive created at $ARCHIVE_PATH"

# To download to your local PC, use scp from your PC:
# scp pi@<raspberrypi_ip>:/home/pi/$ARCHIVE_NAME ~/Downloads/

echo "To download, run this on your PC:"
echo "scp pi@<raspberrypi_ip>:$ARCHIVE_PATH ~/Downloads/"