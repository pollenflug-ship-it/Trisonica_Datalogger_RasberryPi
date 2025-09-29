#!/bin/bash

# Auto-mount setup for external SD card on Raspberry Pi
# This script sets up udev rules and systemd mount units for automatic SD card mounting

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root"
   exit 1
fi

print_info "Setting up auto-mount for external SD card..."

# Create mount point
sudo mkdir -p /mnt/data_sd
sudo chown pi:pi /mnt/data_sd

# Create udev rule for automatic mounting
print_info "Creating udev rule..."
sudo tee /etc/udev/rules.d/99-usb-mount.rules > /dev/null << 'EOF'
# Auto-mount USB storage devices for Trisonica data logging
# This rule triggers when a USB storage device is inserted
ACTION=="add", KERNEL=="sd[a-z][0-9]", SUBSYSTEMS=="usb", ATTRS{removable}=="1", \
    TAG+="systemd", ENV{SYSTEMD_WANTS}="usb-mount@%k.service"

ACTION=="remove", KERNEL=="sd[a-z][0-9]", SUBSYSTEMS=="usb", ATTRS{removable}=="1", \
    RUN+="/bin/systemctl stop usb-mount@%k.service"
EOF

# Create systemd mount service template
print_info "Creating systemd mount service..."
sudo tee /etc/systemd/system/usb-mount@.service > /dev/null << 'EOF'
[Unit]
Description=Mount USB drive %i
After=dev-%i.device
Requires=dev-%i.device

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c ' \
    set -e; \
    DEVICE="/dev/%i"; \
    MOUNT_POINT="/mnt/data_sd"; \
    \
    # Check if device exists and is a block device \
    if [[ ! -b "$DEVICE" ]]; then \
        echo "Device $DEVICE is not a block device"; \
        exit 1; \
    fi; \
    \
    # Check if already mounted \
    if mountpoint -q "$MOUNT_POINT"; then \
        echo "Mount point $MOUNT_POINT already in use"; \
        exit 0; \
    fi; \
    \
    # Create filesystem if needed (only for completely blank devices) \
    if ! blkid "$DEVICE" > /dev/null 2>&1; then \
        echo "Creating ext4 filesystem on $DEVICE"; \
        mkfs.ext4 -F "$DEVICE"; \
    fi; \
    \
    # Mount the device \
    mount "$DEVICE" "$MOUNT_POINT"; \
    \
    # Set ownership \
    chown pi:pi "$MOUNT_POINT"; \
    chmod 755 "$MOUNT_POINT"; \
    \
    # Create data directory structure \
    mkdir -p "$MOUNT_POINT/trisonica_logs"; \
    chown pi:pi "$MOUNT_POINT/trisonica_logs"; \
    \
    echo "Successfully mounted $DEVICE to $MOUNT_POINT"; \
'
ExecStop=/bin/bash -c ' \
    MOUNT_POINT="/mnt/data_sd"; \
    if mountpoint -q "$MOUNT_POINT"; then \
        sync; \
        umount "$MOUNT_POINT"; \
        echo "Unmounted $MOUNT_POINT"; \
    fi; \
'
TimeoutSec=30
EOF

# Create a fallback mount script
print_info "Creating fallback mount script..."
sudo tee /usr/local/bin/mount-usb-storage.sh > /dev/null << 'EOF'
#!/bin/bash

# Fallback script to manually mount USB storage for Trisonica logging

MOUNT_POINT="/mnt/data_sd"

# Function to mount first available USB storage device
mount_first_usb() {
    # Look for USB storage devices
    for device in /dev/sd[a-z]1 /dev/mmcblk[0-9]p1; do
        if [[ -b "$device" ]]; then
            echo "Found storage device: $device"

            # Check if already mounted
            if mountpoint -q "$MOUNT_POINT"; then
                echo "Mount point already in use"
                return 0
            fi

            # Try to mount
            if mount "$device" "$MOUNT_POINT" 2>/dev/null; then
                echo "Successfully mounted $device to $MOUNT_POINT"
                chown pi:pi "$MOUNT_POINT"
                mkdir -p "$MOUNT_POINT/trisonica_logs"
                chown pi:pi "$MOUNT_POINT/trisonica_logs"
                return 0
            else
                echo "Failed to mount $device"
            fi
        fi
    done

    echo "No mountable USB storage devices found"
    return 1
}

case "$1" in
    mount)
        mount_first_usb
        ;;
    umount|unmount)
        if mountpoint -q "$MOUNT_POINT"; then
            sync
            umount "$MOUNT_POINT"
            echo "Unmounted $MOUNT_POINT"
        else
            echo "Nothing mounted at $MOUNT_POINT"
        fi
        ;;
    status)
        if mountpoint -q "$MOUNT_POINT"; then
            echo "USB storage mounted at $MOUNT_POINT"
            df -h "$MOUNT_POINT"
        else
            echo "No USB storage mounted"
        fi
        ;;
    *)
        echo "Usage: $0 {mount|umount|status}"
        exit 1
        ;;
esac
EOF

sudo chmod +x /usr/local/bin/mount-usb-storage.sh

# Reload udev rules
print_info "Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

# Reload systemd
print_info "Reloading systemd..."
sudo systemctl daemon-reload

print_status "Auto-mount setup completed!"
print_info "To test the setup:"
print_info "  1. Insert a USB storage device"
print_info "  2. Check with: mountpoint /mnt/data_sd"
print_info "  3. Manual mount: sudo /usr/local/bin/mount-usb-storage.sh mount"
print_info "  4. Check status: /usr/local/bin/mount-usb-storage.sh status"