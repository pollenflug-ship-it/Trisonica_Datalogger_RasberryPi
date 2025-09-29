#!/bin/bash

echo "=== TRISONICA STATUS ==="

# Check for serial devices
echo "Serial devices:"
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "  No USB serial devices found"

echo ""

# Check storage
echo "Storage status:"
if [[ -w "/mnt/data_sd" ]]; then
    echo "  External storage: Available"
    df -h /mnt/data_sd 2>/dev/null || echo "  External storage: Not mounted"
else
    echo "  External storage: Not available"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "  Local storage: $SCRIPT_DIR/data"
ls -la "$SCRIPT_DIR/data"/*.csv 2>/dev/null | tail -5 || echo "  No data files yet"

echo ""

# Check if logger is running
if pgrep -f "datalogger_simple.py" >/dev/null; then
    echo "Logger status: RUNNING"
    echo "To stop: pkill -f datalogger_simple.py"
else
    echo "Logger status: STOPPED"
    echo "To start: ./start_logger.sh"
fi
