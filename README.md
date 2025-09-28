# Trisonica Datalogger RasberryPi

## Overview
**100% OFFLINE** data logging system for Trisonica Mini anemometer on Raspberry Pi 3 Model B+.

**NO INTERNET REQUIRED** - Everything included in this folder!
![Terminal View](Terminal_View.png)
## What's Included
- **Python data logger** with real-time CSV output
- **All dependencies** (pyserial only - lightweight!)
- **Enhanced console interface** with periodic status updates
- **Automatic device detection** and reconnection
- **Dual storage support**: External SD/USB + local backup
- **No internet required** - fully portable

---

## Quick Start

### 1. Installation
```bash
# Copy this folder to your Pi (USB stick, etc.)
# Place in: Desktop/Trisonica/ (or anywhere)

cd Desktop/Trisonica/

# Fix permissions (if copied from USB/Windows)
bash fix_permissions.sh

# Install system
./install.sh
```

### 2. Set Time & Timezone
```bash
# Set timezone to UTC (recommended for data logging)
sudo timedatectl set-timezone UTC

# Set current UTC time (IMPORTANT!)
sudo date -s "2025-09-28 14:30:00"  # Use current UTC time

# Verify
date  # Should show UTC time
```

### 3. Connect Hardware
- **Trisonica device** -> USB -> **Pi USB port**
- **External SD/USB card** -> USB adapter -> **Pi USB port** (optional, for data storage)

### 4. Start Logging
```bash
./start_logger.sh
```

### 5. Stop Logging
- Press **Ctrl+C**
- Data automatically saved

---

## Console Interface

### Enhanced Terminal Logger (`datalogger_simple.py`)
- **Clean text interface** with periodic status updates
- **Live data readings** every 0.5 seconds (2Hz) showing:
  - Current wind speed, direction, temperature
  - Data collection rate and error statistics
  - Runtime and log file information
- **Low resource usage** - perfect for headless operation
- **Comprehensive error handling** and device reconnection

---

## Data Storage

### Automatic Storage Selection
1. **External USB/SD card**: `/mnt/data_sd/` (preferred)
2. **Local Pi storage**: `./data/` (fallback)

### File Formats
```
TrisonicaData_2025-09-28_143000.csv     # Main data with timestamps
TrisonicaStats_2025-09-28_143000.csv    # Statistical summaries
```

### Data Parameters
| Code | Description | Unit | Range |
|------|-------------|------|-------|
| S    | Wind speed  | m/s  | 0-50  |
| S2   | Alt wind speed | m/s | 0-50  |
| D    | Wind direction | deg | 0-360 |
| T    | Temperature | C | -40 to +60 |
| H    | Humidity | % | 0-100 |
| P    | Pressure | hPa | 900-1100 |

---

## Control Scripts

### Main Operations
- **`start_logger.sh`** - Start console logger
- **`test_connection.sh`** - Test device connection (30 sec)
- **`check_status.sh`** - Check system status

### Utilities
- **`install.sh`** - Main installer
- **`fix_permissions.sh`** - Fix file permissions after copy

---

## Troubleshooting

### No Device Found
```bash
# Check for USB serial devices
ls /dev/ttyUSB* /dev/ttyACM*

# If nothing found:
# 1. Check USB connection
# 2. Try different USB port
# 3. Check if device powers on
```

### Storage Issues
```bash
# Check storage status
./check_status.sh

# Manual external storage mount
sudo mkdir -p /mnt/data_sd
sudo mount /dev/sda1 /mnt/data_sd  # Adjust device as needed
```

### Time Issues
```bash
# Check current time
date
timedatectl status

# Reset time (use current UTC)
sudo date -s "YYYY-MM-DD HH:MM:SS"
```

### Permission Problems
```bash
# Fix all script permissions
bash fix_permissions.sh

# Or manually
chmod +x *.sh *.py
```

---

## Technical Details

### System Requirements
- **Raspberry Pi 3 Model B+** (ARMv7)
- **Python 3.7+** (included with Raspberry Pi OS - COMPATIBLE!)
- **USB port** for Trisonica connection
- **Optional**: External USB storage for data

### Dependencies Included
- **pyserial 3.5** - Serial communication only
- **Standard library** - datetime, collections, signal, etc.
- **Ultra-lightweight** - minimal dependencies for maximum compatibility

### Data Quality Features
- **Error detection** for sensor malfunctions
- **Connection monitoring** with automatic reconnection
- **Data validation** with quality flags
- **Statistical analysis** with error rates

### Storage Management
- **Automatic CSV headers** based on detected parameters
- **File rotation** for large datasets
- **Dual storage** with automatic fallback
- **Timestamp validation**

---

## File Structure

```
Trisonica_Portable/
├── README.md                   # This file
├── QUICK_START.txt            # Basic instructions
├── install.sh                 # Main installer
├── fix_permissions.sh         # Permission fixer
├── datalogger_simple.py       # Simple console logger
├── datalogger_rich.py         # Rich visual logger
├── python_packages/           # Dependencies
│   ├── pyserial-3.5-*.whl   # Serial communication
│   ├── rich-14.1.0-*.whl    # Rich UI library
│   └── [other dependencies]
└── [Generated after install:]
    ├── start_logger.sh        # Start simple logger
    ├── start_rich.sh          # Start rich logger
    ├── test_connection.sh     # Connection test
    ├── check_status.sh        # Status checker
    ├── data/                  # Local data storage
    └── [log files]
```

---

## Support

### Common Issues
1. **"Permission denied"** - Run `bash fix_permissions.sh`
2. **"No device found"** - Check USB connection, try `./test_connection.sh`
3. **"Wrong time in data"** - Set UTC time before logging
4. **"Storage full"** - Use external SD card or clean `./data/` folder

### Data Analysis
- **CSV format** - Import into Excel, Python pandas, R, MATLAB
- **Timestamp format** - ISO 8601 (YYYY-MM-DDTHH:MM:SS)
- **Missing values** - Empty cells for sensor errors
- **Quality flags** - Check statistics file for error rates

