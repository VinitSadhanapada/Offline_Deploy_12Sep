#!/bin/bash
# cleanup_tests.sh - Remove test files after deployment

echo "Removing Feature 1 test files..."

cd /home/pi/Desktop/offline-setup-12Sep

# Remove test scripts
rm -f TEST_01_basic_functionality.py
rm -f TEST_02_corruption_recovery.py
rm -f TEST_03_external_rotation.py
rm -f TEST_04_integration_smoke.py

# Remove test virtual environment
rm -rf test_venv

echo "✓ Cleanup complete"
echo ""
echo "Files removed:"
echo "  - TEST_01_basic_functionality.py"
echo "  - TEST_02_corruption_recovery.py"
echo "  - TEST_03_external_rotation.py"
echo "  - TEST_04_integration_smoke.py"
echo "  - test_venv/ (directory)"
echo ""
echo "Implementation file remains:"
echo "  - src/devices/meter_manager.py (updated with Feature 1)"
