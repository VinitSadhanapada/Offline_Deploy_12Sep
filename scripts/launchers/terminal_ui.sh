#!/bin/bash
# Quick launcher for Terminal Meter UI
# Usage: ./terminal_ui.sh

# Change to project root (two levels up from scripts/launchers)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Check if running in SSH session
if [ -n "$SSH_CLIENT" ] || [ -n "$SSH_TTY" ]; then
    echo "✓ SSH session detected"
else
    echo "⚠ Not in SSH session (running locally)"
fi

# Check terminal size
ROWS=$(tput lines)
COLS=$(tput cols)

if [ "$ROWS" -lt 24 ] || [ "$COLS" -lt 80 ]; then
    echo ""
    echo "⚠ WARNING: Terminal size is ${COLS}x${ROWS}"
    echo "   Recommended minimum: 80x24"
    echo "   Some content may not display correctly."
    echo ""
    read -p "Press ENTER to continue anyway, or Ctrl+C to exit..."
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Python version: $PYTHON_VERSION"

# Set terminal type for better color support
export TERM=xterm-256color

echo ""
echo "Starting Terminal Meter UI..."
echo "Press Q to quit at any time"
echo ""
sleep 1


# Run the UI using absolute path (force Desktop path)
PYTHON_UI_PATH="$HOME/Desktop/offline-setup-12Sep/src/dashboard/terminal_meter_ui.py"
python3 "$PYTHON_UI_PATH"

# Exit status
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "UI exited with error code: $EXIT_CODE"
    echo "Check logs/ directory for more information"
fi

exit $EXIT_CODE
