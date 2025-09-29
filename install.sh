#!/bin/bash

# Portable Trisonica Logger Installation
# For Raspberry Pi 3 Model B+ (ARMv7)
# No internet required - all dependencies included

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[OK] $1${NC}"
}

print_info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

print_error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR"

echo -e "${BLUE}=== TRISONICA PORTABLE INSTALLER ===${NC}"
echo "Installation directory: $INSTALL_DIR"
echo "Target: Raspberry Pi 3 Model B+"
echo "============================================"

# Check if running on Raspberry Pi
check_pi() {
    if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        print_status "Running on Raspberry Pi"
    else
        print_info "Not a Raspberry Pi, but continuing..."
    fi
}

# Install Python dependencies from local wheels
install_dependencies() {
    print_info "Installing Python dependencies from local packages..."

    if [[ -d "$SCRIPT_DIR/python_packages" ]]; then
        cd "$SCRIPT_DIR/python_packages"

        # Install all wheels from local packages
        for wheel in *.whl; do
            if [[ -f "$wheel" ]]; then
                print_info "Installing $wheel..."
                python3 -m pip install --user --no-index --find-links . "$wheel"
            fi
        done

        print_status "Dependencies installed"
    else
        print_error "Python packages directory not found!"
        exit 1
    fi
}

# Create storage directories
setup_storage() {
    print_info "Setting up storage directories..."

    # Create local data directory
    mkdir -p "$INSTALL_DIR/data"

    # Create external mount point (with sudo if available)
    if command -v sudo >/dev/null 2>&1; then
        sudo mkdir -p /mnt/data_sd 2>/dev/null || true
        sudo chown pi:pi /mnt/data_sd 2>/dev/null || true
    fi

    print_status "Storage directories ready"
}

# Create control scripts
create_scripts() {
    print_info "Creating control scripts..."

    # Main launcher script
    cat > "$INSTALL_DIR/start_logger.sh" << 'EOF'
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
EOF


    # Test script
    cat > "$INSTALL_DIR/test_connection.sh" << 'EOF'
#!/bin/bash

# Test Trisonica connection
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== TESTING TRISONICA CONNECTION ==="
echo "This will test for 30 seconds then exit"
echo "===================================="

timeout 30s python3 datalogger_simple.py --no-wait --log-dir "$SCRIPT_DIR/data"
EOF

    # Status script
    cat > "$INSTALL_DIR/check_status.sh" << 'EOF'
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
EOF

    # Make scripts executable
    chmod +x "$INSTALL_DIR"/*.sh
    chmod +x "$INSTALL_DIR"/*.py

    print_status "Control scripts created"
}

# Create README
create_readme() {
    cat > "$INSTALL_DIR/README.txt" << 'EOF'
=== TRISONICA PORTABLE LOGGER ===

QUICK START:
1. Connect Trisonica to Pi via USB
2. Run: ./start_logger.sh
3. Data will be saved automatically

SCRIPTS:
- start_logger.sh     : Start logging (main script)
- test_connection.sh  : Test Trisonica connection (30 sec)
- check_status.sh     : Check system status
- install.sh          : This installer

DATA STORAGE:
- External USB/SD: /mnt/data_sd/ (preferred)
- Local backup:    ./data/ (fallback)

FILES CREATED:
- TrisonicaData_YYYY-MM-DD_HHMMSS.csv (main data)
- TrisonicaStats_YYYY-MM-DD_HHMMSS.csv (statistics)

STOPPING:
- Press Ctrl+C in the terminal
- Or run: pkill -f datalogger_simple.py

TROUBLESHOOTING:
- Check devices: ls /dev/ttyUSB* /dev/ttyACM*
- Check status: ./check_status.sh
- View recent data: ls -la data/*.csv

NO INTERNET REQUIRED - Everything is included!
EOF

    print_status "README created"
}

# Main installation
main() {
    check_pi
    install_dependencies
    setup_storage
    create_scripts
    create_readme

    echo ""
    print_status "Installation completed!"
    echo ""
    print_info "Next steps:"
    echo "1. Connect Trisonica to Pi via USB"
    echo "2. Run: ./start_logger.sh"
    echo "3. Data will be saved automatically"
    echo ""
    print_info "Test connection: ./test_connection.sh"
    print_info "Check status: ./check_status.sh"
    echo ""
    print_info "Read README.txt for full instructions"
}

# Run installation
main "$@"