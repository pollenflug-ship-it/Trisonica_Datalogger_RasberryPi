#!/bin/bash

# Transfer Trisonica Pi files to Raspberry Pi
# Usage: ./transfer_to_pi.sh <pi_ip_address>

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

# Check arguments
if [[ $# -eq 0 ]]; then
    print_error "Usage: $0 <pi_ip_address> [pi_username]"
    echo "Example: $0 192.168.1.100"
    echo "Example: $0 raspberrypi.local pi"
    exit 1
fi

PI_IP="$1"
PI_USER="${2:-pi}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_info "Transferring Trisonica files to Raspberry Pi..."
print_info "Target: $PI_USER@$PI_IP"

# Files to transfer
FILES=(
    "datalogger_pi.py"
    "deploy_pi.sh"
    "setup_auto_mount.sh"
    "trisonica.service"
)

# Check if all files exist
for file in "${FILES[@]}"; do
    if [[ ! -f "$SCRIPT_DIR/$file" ]]; then
        print_error "File not found: $file"
        exit 1
    fi
done

# Create temporary directory on Pi
print_info "Creating temporary directory on Pi..."
ssh "$PI_USER@$PI_IP" "mkdir -p ~/trisonica_install"

# Transfer files
print_info "Transferring files..."
for file in "${FILES[@]}"; do
    print_info "Copying $file..."
    scp "$SCRIPT_DIR/$file" "$PI_USER@$PI_IP:~/trisonica_install/"
done

# Make scripts executable
print_info "Setting permissions..."
ssh "$PI_USER@$PI_IP" "chmod +x ~/trisonica_install/*.sh ~/trisonica_install/*.py"

print_status "Transfer completed!"
print_info "To install on the Pi, SSH to it and run:"
echo "  ssh $PI_USER@$PI_IP"
echo "  cd ~/trisonica_install"
echo "  ./deploy_pi.sh"