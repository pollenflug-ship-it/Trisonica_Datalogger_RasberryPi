# Offline Raspberry Pi Installation Guide

## Files in this package:
- `datalogger_pi.py` - Main Trisonica logger for Pi
- `deploy_pi.sh` - Automated installation script
- `setup_auto_mount.sh` - USB storage auto-mount setup
- `trisonica.service` - Systemd service file
- `INSTALL_OFFLINE.md` - This guide

## Installation Steps:

### 1. Transfer to Pi
Copy this entire folder to the Pi's home directory:
```bash
# On Pi, create directory
mkdir ~/trisonica_install

# Copy files (via USB stick, SD card, etc.)
# Place all files in ~/trisonica_install/
```

### 2. Make scripts executable
```bash
cd ~/trisonica_install
chmod +x *.sh *.py
```

### 3. Run installation
```bash
./deploy_pi.sh
```

### 4. Reboot Pi
```bash
sudo reboot
```

## After Installation:

### Control the service:
```bash
trisonica start     # Start logging
trisonica stop      # Stop logging
trisonica status    # Check status
trisonica logs      # View logs
```

### Manual test:
```bash
trisonica test      # Test connection manually
```

## Data Storage:
- **External USB/SD**: `/mnt/data_sd/`
- **Internal fallback**: `~/trisonica_data/`

## Troubleshooting:

### Check if Trisonica is connected:
```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

### Check service status:
```bash
sudo systemctl status trisonica
```

### View logs:
```bash
sudo journalctl -u trisonica -f
```

### Mount USB storage manually:
```bash
sudo /usr/local/bin/mount-usb-storage.sh mount
```

## Auto-Start Behavior:
- Service starts automatically on boot
- Waits for Trisonica device to be connected
- Begins logging immediately when device is detected
- Saves CSV files with timestamps

## Expected File Output:
```
/mnt/data_sd/TrisonicaData_YYYY-MM-DD_HHMMSS.csv
/mnt/data_sd/TrisonicaStats_YYYY-MM-DD_HHMMSS.csv
```