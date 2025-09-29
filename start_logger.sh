#!/bin/bash

# Trisonica Logger Launcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== STARTING TRISONICA LOGGER ==="

# Auto-sync UTC time if internet is available
echo "Checking for internet connection..."
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo "Internet detected - syncing UTC time..."

    # Set timezone to UTC
    sudo timedatectl set-timezone UTC

    # Enable NTP sync
    sudo timedatectl set-ntp true

    # Wait for sync (up to 30 seconds)
    echo "Waiting for time sync..."
    for i in {1..30}; do
        if timedatectl status | grep -q "System clock synchronized: yes"; then
            echo "Time synchronized successfully!"
            break
        fi
        sleep 1
        echo -n "."
    done

    # Disable NTP to prevent future attempts when offline
    sudo timedatectl set-ntp false

    sync_status=$(timedatectl status | grep "System clock synchronized")
    echo "$sync_status"
else
    echo "No internet - using current system time"
fi

# Display current time
current_year=$(date +%Y)
current_time=$(date -u)
echo "Current UTC time: $current_time"

# Warn if time still looks wrong
if [[ $current_year -lt 2020 ]]; then
    echo ""
    echo "WARNING: Time still appears incorrect!"
    echo "Manual time setting may be needed:"
    echo "   sudo date -s \"YYYY-MM-DD HH:MM:SS\""
    echo ""
    read -p "Press Enter to continue anyway, or Ctrl+C to stop and fix time: "
fi

echo "Press Ctrl+C to stop logging"
echo "====================================="

# Try external storage first, then local
if [[ -w "/mnt/data_sd" ]]; then
    echo "Using external storage: /mnt/data_sd"
    python3 datalogger_simple.py --log-dir /mnt/data_sd
else
    echo "Using local storage: $SCRIPT_DIR/data"
    python3 datalogger_simple.py --log-dir "$SCRIPT_DIR/data"
fi
