#!/bin/bash

# Test Trisonica connection
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== TESTING TRISONICA CONNECTION ==="
echo "This will test for 30 seconds then exit"
echo "===================================="

timeout 30s python3 datalogger_simple.py --no-wait --log-dir "$SCRIPT_DIR/data"
