#!/usr/bin/env python3

import serial
import datetime
import time
import sys
import signal
import re
import os
import glob
import argparse
import logging
import subprocess
from collections import deque
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from pathlib import Path

# --- Configuration ---
DEFAULT_BAUD_RATE = 115200
MAX_DATAPOINTS = 10000  # Increased for Pi deployment
LOG_ROTATION_SIZE = 100 * 1024 * 1024  # 100MB logs
DEVICE_CHECK_INTERVAL = 5  # Check for devices every 5 seconds
EXTERNAL_SD_MOUNTPOINT = "/mnt/data_sd"

@dataclass
class Config:
    serial_port: str = "auto"
    baud_rate: int = DEFAULT_BAUD_RATE
    log_dir: str = EXTERNAL_SD_MOUNTPOINT
    save_statistics: bool = True
    max_log_size: int = LOG_ROTATION_SIZE
    headless: bool = True
    wait_for_device: bool = True

@dataclass
class DataPoint:
    timestamp: datetime.datetime
    raw_data: str
    parsed_data: Dict[str, str] = field(default_factory=dict)

@dataclass
class Statistics:
    min_val: float = 0.0
    max_val: float = 0.0
    mean_val: float = 0.0
    current_val: float = 0.0
    std_dev: float = 0.0
    count: int = 0
    values: deque = field(default_factory=lambda: deque(maxlen=100))

class TrisonicaDataLoggerPi:
    def __init__(self, config: Config):
        self.config = config
        self.serial_port = None
        self.log_file = None
        self.stats_file = None
        self.running = False
        self.start_time = time.time()

        # Data storage
        self.data_points = deque(maxlen=MAX_DATAPOINTS)
        self.point_count = 0
        self.stats = {}

        # CSV column management
        self.csv_columns = ['timestamp']
        self.csv_headers_written = False

        # Data quality tracking
        self.data_quality = {
            'total_readings': 0,
            'error_count': 0,
            'last_error_time': None,
            'sensor_health': {},
            'connection_drops': 0,
            'last_connection_time': time.time(),
            'parameter_errors': {}
        }

        # Initialize sensor health tracking
        for param in ['S', 'S2', 'D', 'T', 'H', 'P', 'U', 'V', 'W']:
            self.data_quality['sensor_health'][param] = {
                'status': 'Unknown',
                'error_rate': 0.0,
                'last_good_reading': None
            }

        # Setup logging
        self.setup_logging()

        # Signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        # Setup console logging
        self.setup_console_logging()

        logging.info("Trisonica Data Logger for Raspberry Pi initialized")
        logging.info(f"Platform: {sys.platform}")
        logging.info(f"Python: {sys.version.split()[0]}")
        logging.info(f"Log Directory: {self.config.log_dir}")

    def setup_console_logging(self):
        """Setup logging to console and file"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('/var/log/trisonica.log') if os.access('/var/log', os.W_OK)
                else logging.FileHandler(os.path.expanduser('~/trisonica.log'))
            ]
        )

    def check_external_sd_card(self) -> bool:
        """Check if external SD card is mounted and accessible"""
        if not os.path.exists(self.config.log_dir):
            logging.warning(f"External SD card not found at {self.config.log_dir}")

            # Try to create mount point and mount
            try:
                os.makedirs(self.config.log_dir, exist_ok=True)

                # Look for USB storage devices
                usb_devices = glob.glob('/dev/sd[a-z]1') + glob.glob('/dev/mmcblk[0-9]p1')

                for device in usb_devices:
                    logging.info(f"Attempting to mount {device} to {self.config.log_dir}")
                    try:
                        result = subprocess.run(['sudo', 'mount', device, self.config.log_dir],
                                             capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            logging.info(f"Successfully mounted {device}")
                            break
                    except Exception as e:
                        logging.warning(f"Failed to mount {device}: {e}")
                        continue
                else:
                    # No external device found, use home directory
                    self.config.log_dir = os.path.expanduser("~/trisonica_data")
                    os.makedirs(self.config.log_dir, exist_ok=True)
                    logging.warning(f"Using fallback directory: {self.config.log_dir}")

            except Exception as e:
                logging.error(f"Failed to setup storage: {e}")
                return False

        # Test write access
        try:
            test_file = os.path.join(self.config.log_dir, 'write_test.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logging.info(f"Storage is accessible: {self.config.log_dir}")
            return True
        except Exception as e:
            logging.error(f"Storage not writable: {e}")
            return False

    def find_serial_ports(self) -> List[str]:
        """Find all available serial ports on Pi"""
        patterns = [
            '/dev/ttyUSB*',      # USB-to-serial adapters
            '/dev/ttyACM*',      # USB CDC devices
            '/dev/ttyAMA*',      # Pi GPIO UART
            '/dev/serial/by-id/*'  # Persistent device names
        ]

        ports = []
        for pattern in patterns:
            ports.extend(glob.glob(pattern))

        return sorted(set(ports))

    def wait_for_trisonica(self) -> Optional[str]:
        """Wait for Trisonica device to be connected"""
        logging.info("Waiting for Trisonica device...")

        while self.running:
            ports = self.find_serial_ports()

            if not ports:
                logging.debug("No serial ports found, waiting...")
                time.sleep(DEVICE_CHECK_INTERVAL)
                continue

            # Test each port for Trisonica data
            for port in ports:
                try:
                    logging.debug(f"Testing {port}...")
                    ser = serial.Serial(port, self.config.baud_rate, timeout=2)

                    # Read several lines to detect Trisonica
                    trisonica_detected = False
                    for _ in range(10):
                        try:
                            line = ser.readline().decode('ascii', errors='ignore').strip()
                            if line and any(param in line for param in ['S ', 'S2', 'D ', 'T ', 'U ', 'V ']):
                                trisonica_detected = True
                                break
                        except:
                            continue

                    ser.close()

                    if trisonica_detected:
                        logging.info(f"Trisonica detected on {port}")
                        return port
                    else:
                        logging.debug(f"No Trisonica data on {port}")

                except Exception as e:
                    logging.debug(f"Error testing {port}: {e}")

            logging.info("No Trisonica found, retrying in 5 seconds...")
            time.sleep(DEVICE_CHECK_INTERVAL)

        return None

    def setup_logging(self):
        """Setup file logging"""
        if not self.check_external_sd_card():
            logging.error("Failed to setup storage, cannot continue")
            sys.exit(1)

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')

        # Data log
        self.log_filename = f"TrisonicaData_{timestamp}.csv"
        self.log_path = os.path.join(self.config.log_dir, self.log_filename)
        self.log_file = open(self.log_path, 'w', newline='')

        # Statistics log
        if self.config.save_statistics:
            self.stats_filename = f"TrisonicaStats_{timestamp}.csv"
            self.stats_path = os.path.join(self.config.log_dir, self.stats_filename)
            self.stats_file = open(self.stats_path, 'w', newline='')
            self.stats_file.write("timestamp,parameter,min,max,mean,std_dev,count,error_count,error_rate_percent,total_readings\n")

        logging.info(f"Data Log: {self.log_path}")
        if self.config.save_statistics:
            logging.info(f"Stats Log: {self.stats_path}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logging.info(f"Received signal {signum}, shutting down...")
        self.save_final_statistics()
        self.running = False

    def connect_serial(self, port: str) -> bool:
        """Connect to serial port"""
        try:
            self.serial_port = serial.Serial(port, self.config.baud_rate, timeout=1)
            logging.info(f"Connected to {port} at {self.config.baud_rate:,} baud")
            return True
        except serial.SerialException as e:
            logging.error(f"Connection failed: {e}")
            return False

    def parse_data_line(self, line: str) -> Dict[str, str]:
        """Parse Trisonica data line"""
        parsed = {}
        try:
            if ',' in line:
                pairs = line.strip().split(',')
                for pair in pairs:
                    pair = pair.strip()
                    if ' ' in pair:
                        parts = pair.split(' ', 1)
                        if len(parts) == 2:
                            key, value = parts
                            parsed[key.strip()] = value.strip()
            else:
                parts = line.strip().split()
                for i in range(0, len(parts)-1, 2):
                    if i+1 < len(parts):
                        parsed[parts[i]] = parts[i+1]
        except Exception:
            pass
        return parsed

    def update_csv_columns(self, parsed_data: Dict[str, str]):
        """Update CSV columns based on new parameters"""
        for key in parsed_data.keys():
            if key not in self.csv_columns:
                self.csv_columns.append(key)

        if not self.csv_headers_written:
            self.log_file.write(','.join(self.csv_columns) + '\n')
            self.csv_headers_written = True

    def write_csv_row(self, timestamp: datetime.datetime, parsed_data: Dict[str, str]):
        """Write CSV row"""
        row_values = []
        for column in self.csv_columns:
            if column == 'timestamp':
                row_values.append(timestamp.isoformat())
            else:
                value = parsed_data.get(column, '')
                row_values.append(value)

        self.log_file.write(','.join(row_values) + '\n')
        self.log_file.flush()

    def calculate_statistics(self, key: str, value: float):
        """Calculate statistics for parameter"""
        if key not in self.stats:
            self.stats[key] = Statistics()

        stat = self.stats[key]
        stat.current_val = value
        stat.count += 1
        stat.values.append(value)

        if stat.count == 1:
            stat.min_val = stat.max_val = stat.mean_val = value
            stat.std_dev = 0.0
        else:
            stat.min_val = min(stat.min_val, value)
            stat.max_val = max(stat.max_val, value)
            stat.mean_val = sum(stat.values) / len(stat.values)

            if len(stat.values) > 1:
                variance = sum((x - stat.mean_val) ** 2 for x in stat.values) / len(stat.values)
                stat.std_dev = variance ** 0.5

    def read_serial_data(self) -> Optional[DataPoint]:
        """Read and process serial data"""
        if not self.serial_port or not self.serial_port.is_open:
            return None

        try:
            line = self.serial_port.readline().decode('ascii', errors='ignore').strip()
            if not line:
                return None

            timestamp = datetime.datetime.now()
            parsed = self.parse_data_line(line)

            self.update_csv_columns(parsed)
            self.write_csv_row(timestamp, parsed)

            self.data_quality['total_readings'] += 1

            for key, value_str in parsed.items():
                try:
                    value = float(value_str)

                    if key not in self.data_quality['parameter_errors']:
                        self.data_quality['parameter_errors'][key] = {
                            'error_count': 0,
                            'total_count': 0
                        }

                    self.data_quality['parameter_errors'][key]['total_count'] += 1

                    is_error = value <= -99.0
                    self.update_sensor_health(key, value, is_error)

                    if is_error:
                        self.data_quality['parameter_errors'][key]['error_count'] += 1
                    else:
                        self.calculate_statistics(key, value)

                except ValueError:
                    self.update_sensor_health(key, 0, True)

            return DataPoint(timestamp, line, parsed)

        except Exception as e:
            logging.warning(f"Error reading serial data: {e}")
            return None

    def update_sensor_health(self, parameter: str, value: float, is_error: bool = False):
        """Update sensor health status"""
        current_time = datetime.datetime.now()

        if parameter not in self.data_quality['sensor_health']:
            self.data_quality['sensor_health'][parameter] = {
                'status': 'Unknown',
                'error_rate': 0.0,
                'last_good_reading': None
            }

        sensor = self.data_quality['sensor_health'][parameter]

        if is_error:
            self.data_quality['error_count'] += 1
            self.data_quality['last_error_time'] = current_time
            sensor['status'] = 'Error'
        else:
            sensor['last_good_reading'] = current_time
            if parameter.startswith('T') and value > 100000:
                sensor['status'] = 'Malfunction'
            elif parameter == 'P' and value == -99.70:
                sensor['status'] = 'Offline'
            else:
                sensor['status'] = 'Good'

        if self.data_quality['total_readings'] > 0:
            sensor['error_rate'] = (self.data_quality['error_count'] / self.data_quality['total_readings']) * 100

    def save_final_statistics(self):
        """Save final statistics"""
        if not self.config.save_statistics or not self.stats_file:
            return

        timestamp = datetime.datetime.now().isoformat()
        all_parameters = set(self.stats.keys()) | set(self.data_quality['parameter_errors'].keys())

        for key in all_parameters:
            if key in self.stats:
                stat = self.stats[key]
                min_val = stat.min_val
                max_val = stat.max_val
                mean_val = stat.mean_val
                std_dev = stat.std_dev
                good_count = stat.count
            else:
                min_val = max_val = mean_val = std_dev = 0.0
                good_count = 0

            if key in self.data_quality['parameter_errors']:
                error_data = self.data_quality['parameter_errors'][key]
                error_count = error_data['error_count']
                total_readings = error_data['total_count']
                error_rate = (error_count / total_readings * 100) if total_readings > 0 else 0.0
            else:
                error_count = 0
                total_readings = good_count
                error_rate = 0.0

            self.stats_file.write(f"{timestamp},{key},{min_val:.6f},{max_val:.6f},"
                                f"{mean_val:.6f},{std_dev:.6f},{good_count},"
                                f"{error_count},{error_rate:.2f},{total_readings}\n")

        self.stats_file.flush()

    def log_status_update(self):
        """Log periodic status updates"""
        elapsed = time.time() - self.start_time
        rate = self.point_count / elapsed if elapsed > 0 else 0
        error_rate = (self.data_quality['error_count'] / max(1, self.data_quality['total_readings'])) * 100

        logging.info(f"Status: {self.point_count:,} points, {rate:.1f} Hz, {error_rate:.1f}% errors, "
                    f"{len(self.stats)} parameters")

    def run(self):
        """Main execution loop"""
        self.running = True

        while self.running:
            # Wait for Trisonica if needed
            if self.config.wait_for_device:
                port = self.wait_for_trisonica()
                if not port:
                    break
            else:
                ports = self.find_serial_ports()
                if not ports:
                    logging.error("No serial ports found")
                    break
                port = ports[0]

            # Connect to device
            if not self.connect_serial(port):
                if self.config.wait_for_device:
                    logging.warning("Connection failed, waiting for device...")
                    time.sleep(DEVICE_CHECK_INTERVAL)
                    continue
                else:
                    break

            logging.info("Starting data logging...")
            last_status_log = time.time()

            # Data logging loop
            while self.running and self.serial_port and self.serial_port.is_open:
                try:
                    data_point = self.read_serial_data()
                    if data_point:
                        self.point_count += 1
                        self.data_points.append(data_point)

                        # Periodic statistics save
                        if self.point_count % 100 == 0:
                            self.save_final_statistics()

                        # Periodic status logging
                        if time.time() - last_status_log > 30:  # Every 30 seconds
                            self.log_status_update()
                            last_status_log = time.time()

                    time.sleep(0.01)  # Small delay to prevent CPU overload

                except serial.SerialException as e:
                    logging.warning(f"Serial connection lost: {e}")
                    if self.config.wait_for_device:
                        logging.info("Will wait for device to reconnect...")
                        break  # Break inner loop to wait for device again
                    else:
                        self.running = False

                except Exception as e:
                    logging.error(f"Unexpected error: {e}")
                    break

            # Close serial port if open
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()

        self.cleanup()
        return True

    def cleanup(self):
        """Cleanup resources"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            logging.info("Serial port closed")

        if self.log_file and not self.log_file.closed:
            self.log_file.close()
            logging.info(f"Data log saved: {self.log_path}")

        if self.stats_file and not self.stats_file.closed:
            self.stats_file.close()
            logging.info(f"Statistics saved: {self.stats_path}")

        if self.point_count > 0:
            elapsed = time.time() - self.start_time
            avg_rate = self.point_count / elapsed if elapsed > 0 else 0
            logging.info(f"Session Summary: {self.point_count:,} points, "
                        f"{datetime.timedelta(seconds=int(elapsed))} runtime, "
                        f"{avg_rate:.1f} Hz average")

        logging.info("Cleanup complete")

def main():
    parser = argparse.ArgumentParser(description='Trisonica Data Logger for Raspberry Pi')
    parser.add_argument('--port', default='auto', help='Serial port (default: auto-detect)')
    parser.add_argument('--baud', type=int, default=DEFAULT_BAUD_RATE, help='Baud rate')
    parser.add_argument('--log-dir', default=EXTERNAL_SD_MOUNTPOINT, help='Log directory')
    parser.add_argument('--no-stats', action='store_true', help='Disable statistics logging')
    parser.add_argument('--no-wait', action='store_true', help='Do not wait for device')

    args = parser.parse_args()

    config = Config(
        serial_port=args.port,
        baud_rate=args.baud,
        log_dir=args.log_dir,
        save_statistics=not args.no_stats,
        wait_for_device=not args.no_wait
    )

    logger = TrisonicaDataLoggerPi(config)
    sys.exit(0 if logger.run() else 1)

if __name__ == '__main__':
    main()