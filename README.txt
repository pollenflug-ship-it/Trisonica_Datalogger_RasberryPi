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
