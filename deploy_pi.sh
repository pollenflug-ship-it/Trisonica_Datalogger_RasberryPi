#!/bin/bash

# Trisonica Data Logger - Raspberry Pi Deployment Script
# This script sets up the complete Trisonica logging system on a Raspberry Pi

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PI_USER="pi"
INSTALL_DIR="/home/$PI_USER/trisonica"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_NAME="trisonica"

echo -e "${BLUE}Trisonica Data Logger - Raspberry Pi Deployment${NC}"
echo "=================================================="

# Function to print status
print_status() {
    echo -e "${GREEN}[OK] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

print_error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

print_info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Check if running on Raspberry Pi
check_pi() {
    if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        print_warning "This doesn't appear to be a Raspberry Pi, but continuing anyway..."
    else
        print_status "Running on Raspberry Pi"
    fi
}

# Check if running as pi user
check_user() {
    if [[ "$USER" != "$PI_USER" ]]; then
        print_error "This script should be run as the 'pi' user"
        print_info "Switch to pi user: sudo su - pi"
        exit 1
    fi
    print_status "Running as user: $USER"
}

# Update system
update_system() {
    print_info "Updating system packages..."
    sudo apt update && sudo apt upgrade -y
    print_status "System updated"
}

# Install required packages
install_packages() {
    print_info "Installing required packages..."

    local packages=(
        "python3"
        "python3-pip"
        "python3-venv"
        "python3-dev"
        "build-essential"
        "git"
        "udev"
        "systemd"
        "mount"
        "util-linux"
    )

    sudo apt install -y "${packages[@]}"
    print_status "Packages installed"
}

# Create installation directory
setup_directories() {
    print_info "Setting up directories..."

    # Remove existing installation if it exists
    if [[ -d "$INSTALL_DIR" ]]; then
        print_warning "Existing installation found, backing up..."
        sudo mv "$INSTALL_DIR" "${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
    fi

    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    print_status "Installation directory created: $INSTALL_DIR"
}

# Create Python virtual environment
setup_venv() {
    print_info "Creating Python virtual environment..."

    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    pip install --upgrade pip

    # Install required Python packages
    pip install pyserial

    print_status "Virtual environment created and configured"
}

# Copy application files
install_app() {
    print_info "Installing Trisonica logger application..."

    # Copy the main application file (assumes this script is run from the source directory)
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [[ -f "$script_dir/datalogger_pi.py" ]]; then
        cp "$script_dir/datalogger_pi.py" "$INSTALL_DIR/"
        chmod +x "$INSTALL_DIR/datalogger_pi.py"
        print_status "Application files copied"
    else
        print_error "datalogger_pi.py not found in $script_dir"
        print_info "Please ensure you're running this script from the correct directory"
        exit 1
    fi
}

# Setup auto-mount for USB storage
setup_auto_mount() {
    print_info "Setting up auto-mount for external storage..."

    # Create mount point
    sudo mkdir -p /mnt/data_sd
    sudo chown "$PI_USER:$PI_USER" /mnt/data_sd

    # Copy and run the auto-mount setup script
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [[ -f "$script_dir/setup_auto_mount.sh" ]]; then
        cp "$script_dir/setup_auto_mount.sh" "$INSTALL_DIR/"
        chmod +x "$INSTALL_DIR/setup_auto_mount.sh"

        # Run the auto-mount setup
        "$INSTALL_DIR/setup_auto_mount.sh"
        print_status "Auto-mount configured"
    else
        print_warning "Auto-mount setup script not found, will use fallback directory"
    fi
}

# Setup systemd service
setup_service() {
    print_info "Setting up systemd service..."

    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [[ -f "$script_dir/trisonica.service" ]]; then
        # Update service file with correct paths
        sed "s|/home/pi/trisonica|$INSTALL_DIR|g" "$script_dir/trisonica.service" | \
        sed "s|User=pi|User=$PI_USER|g" | \
        sed "s|Group=pi|Group=$PI_USER|g" > "/tmp/$SERVICE_NAME.service"

        sudo mv "/tmp/$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME.service"

        print_status "Systemd service installed and enabled"
    else
        print_error "trisonica.service file not found"
        exit 1
    fi
}

# Add user to dialout group for serial access
setup_permissions() {
    print_info "Setting up permissions..."

    # Add user to dialout group for serial port access
    sudo usermod -a -G dialout "$PI_USER"

    # Set permissions for log directory
    sudo mkdir -p /var/log
    sudo touch /var/log/trisonica.log
    sudo chown "$PI_USER:$PI_USER" /var/log/trisonica.log

    print_status "Permissions configured"
}

# Create helper scripts
create_helpers() {
    print_info "Creating helper scripts..."

    # Service control script
    cat > "$INSTALL_DIR/trisonica-control.sh" << 'EOF'
#!/bin/bash

SERVICE_NAME="trisonica"

case "$1" in
    start)
        sudo systemctl start "$SERVICE_NAME"
        echo "Trisonica service started"
        ;;
    stop)
        sudo systemctl stop "$SERVICE_NAME"
        echo "Trisonica service stopped"
        ;;
    restart)
        sudo systemctl restart "$SERVICE_NAME"
        echo "Trisonica service restarted"
        ;;
    status)
        sudo systemctl status "$SERVICE_NAME"
        ;;
    logs)
        sudo journalctl -u "$SERVICE_NAME" -f
        ;;
    enable)
        sudo systemctl enable "$SERVICE_NAME"
        echo "Trisonica service enabled for auto-start"
        ;;
    disable)
        sudo systemctl disable "$SERVICE_NAME"
        echo "Trisonica service disabled"
        ;;
    test)
        echo "Testing Trisonica logger manually..."
        cd /home/pi/trisonica
        source venv/bin/activate
        python datalogger_pi.py --no-wait
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|enable|disable|test}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the service"
        echo "  stop    - Stop the service"
        echo "  restart - Restart the service"
        echo "  status  - Show service status"
        echo "  logs    - Show live logs"
        echo "  enable  - Enable auto-start on boot"
        echo "  disable - Disable auto-start"
        echo "  test    - Run logger manually for testing"
        exit 1
        ;;
esac
EOF

    chmod +x "$INSTALL_DIR/trisonica-control.sh"

    # Create symlink for easy access
    sudo ln -sf "$INSTALL_DIR/trisonica-control.sh" /usr/local/bin/trisonica

    print_status "Helper scripts created"
}

# Create README for Pi installation
create_readme() {
    print_info "Creating README file..."

    cat > "$INSTALL_DIR/README_PI.md" << 'EOF'
# Trisonica Data Logger - Raspberry Pi Installation

## Quick Start

1. **Start logging**: `trisonica start`
2. **Check status**: `trisonica status`
3. **View logs**: `trisonica logs`
4. **Stop logging**: `trisonica stop`

## Manual Testing

To test the logger manually without the service:
```bash
trisonica test
```

## Data Storage

- **Auto-mount**: External USB/SD cards are automatically mounted to `/mnt/data_sd`
- **Fallback**: If no external storage, data is saved to `~/trisonica_data`
- **Data format**: CSV files with timestamps in filename

## Service Management

- **Auto-start on boot**: `trisonica enable`
- **Disable auto-start**: `trisonica disable`
- **Restart service**: `trisonica restart`

## Troubleshooting

### Check if Trisonica is connected
```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

### Check mount status
```bash
/usr/local/bin/mount-usb-storage.sh status
```

### Manual mount USB storage
```bash
sudo /usr/local/bin/mount-usb-storage.sh mount
```

### View system logs
```bash
sudo journalctl -u trisonica -f
```

## File Locations

- **Installation**: `/home/pi/trisonica/`
- **Data (external)**: `/mnt/data_sd/`
- **Data (fallback)**: `/home/pi/trisonica_data/`
- **System logs**: `/var/log/trisonica.log`
- **Service logs**: `journalctl -u trisonica`

## Updating

To update the application:
1. Stop the service: `trisonica stop`
2. Replace `datalogger_pi.py` with new version
3. Start the service: `trisonica start`
EOF

    print_status "README created"
}

# Main installation flow
main() {
    print_info "Starting Trisonica Data Logger installation on Raspberry Pi..."

    check_pi
    check_user
    update_system
    install_packages
    setup_directories
    setup_venv
    install_app
    setup_auto_mount
    setup_service
    setup_permissions
    create_helpers
    create_readme

    print_status "Installation completed successfully!"
    echo ""
    print_info "Next steps:"
    echo "1. Reboot the Pi: sudo reboot"
    echo "2. Connect Trisonica device via USB"
    echo "3. Insert external USB storage (optional)"
    echo "4. Check status: trisonica status"
    echo "5. View logs: trisonica logs"
    echo ""
    print_info "The service will automatically start on boot and begin logging when Trisonica is connected."
    print_info "Read $INSTALL_DIR/README_PI.md for detailed usage instructions."
}

# Run main installation
main "$@"