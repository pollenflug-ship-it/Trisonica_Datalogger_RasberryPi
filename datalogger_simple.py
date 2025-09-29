#!/usr/bin/env python3

import serial
import datetime
import time
import sys
import signal
import os
import glob
import argparse
import logging
import threading
from collections import deque
from typing import Dict, Optional, List
from dataclasses import dataclass, field

# --- Configuration ---
DEFAULT_BAUD_RATE = 115200
MAX_DATAPOINTS = 10000
DEVICE_CHECK_INTERVAL = 5
EXTERNAL_SD_MOUNTPOINT = "/mnt/data_sd"

class LEDController:
    """Control Raspberry Pi built-in LEDs for status indication"""

    def __init__(self):
        # Only use Activity LED - don't interfere with Power LED
        self.activity_led_path = "/sys/class/leds/ACT/brightness"  # Activity LED (green)
        self.led_available = self._check_led_availability()
        self.blink_thread = None
        self.stop_blink = False

    def _check_led_availability(self):
        """Check if Activity LED control is available"""
        try:
            # Only check Activity LED - don't interfere with Power LED
            paths_to_check = [
                "/sys/class/leds/ACT/brightness",
                "/sys/class/leds/led1/brightness"  # Alternative path
            ]

            for path in paths_to_check:
                if os.path.exists(path):
                    self.activity_led_path = path  # Use the path that exists
                    return True
            return False
        except:
            return False

    def _write_led(self, led_path, value):
        """Write value to LED control file"""
        if not self.led_available:
            return

        try:
            # Try to write directly (if we have permissions)
            with open(led_path, 'w') as f:
                f.write(str(value))
        except (PermissionError, FileNotFoundError):
            try:
                # Fall back to using echo with sudo
                os.system(f"echo {value} | sudo tee {led_path} > /dev/null 2>&1")
            except:
                pass

    def set_activity_led(self, state: bool):
        """Control activity LED (green) - indicates logging activity"""
        self._write_led(self.activity_led_path, 1 if state else 0)

    def blink_activity_led(self, interval=0.5):
        """Start blinking activity LED to indicate active logging"""
        self.stop_blink = False

        def blink_worker():
            state = False
            while not self.stop_blink:
                self.set_activity_led(state)
                state = not state
                time.sleep(interval)

        if self.blink_thread is None or not self.blink_thread.is_alive():
            self.blink_thread = threading.Thread(target=blink_worker, daemon=True)
            self.blink_thread.start()

    def stop_blinking(self):
        """Stop LED blinking"""
        self.stop_blink = True
        if self.blink_thread:
            self.blink_thread.join(timeout=1)
        self.set_activity_led(False)

    def flash_write_indicator(self):
        """Quick flash to indicate data write to SD card"""
        if not self.led_available:
            return

        def flash_worker():
            # Brief bright flash for data write indication
            self.set_activity_led(True)
            time.sleep(0.05)  # Shorter flash
            self.set_activity_led(False)
            time.sleep(0.05)
            # Return to blinking state - blink_activity_led will continue

        flash_thread = threading.Thread(target=flash_worker, daemon=True)
        flash_thread.start()

@dataclass
class Config:
    serial_port: str = "auto"
    baud_rate: int = DEFAULT_BAUD_RATE
    log_dir: str = EXTERNAL_SD_MOUNTPOINT
    save_statistics: bool = True
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
    count: int = 0
    values: deque = field(default_factory=lambda: deque(maxlen=100))

class TrisonicaLogger:
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
            'parameter_errors': {}
        }

        # LED status indicator
        self.led_controller = LEDController()
        if self.led_controller.led_available:
            logging.info("Activity LED indicator available")
        else:
            logging.info("Activity LED indicator not available (running on non-Pi or insufficient permissions)")

        # Setup logging
        self.setup_logging()
        self.setup_storage()

        # Signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        print("=== TRISONICA DATA LOGGER ===")
        print(f"Platform: {sys.platform}")
        print(f"Python: {sys.version.split()[0]}")
        print(f"Log Directory: {self.config.log_dir}")
        print("=" * 30)

    def setup_logging(self):
        """Setup console logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )

    def setup_storage(self):
        """Setup storage directory"""
        # Try external storage first
        if not os.path.exists(self.config.log_dir):
            # Fallback to local directory
            self.config.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

        os.makedirs(self.config.log_dir, exist_ok=True)

        # Test write access
        try:
            test_file = os.path.join(self.config.log_dir, 'write_test.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logging.info(f"Using storage: {self.config.log_dir}")
        except Exception as e:
            logging.error(f"Storage not writable: {e}")
            sys.exit(1)

        # Setup data files
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')

        self.log_filename = f"TrisonicaData_{timestamp}.csv"
        self.log_path = os.path.join(self.config.log_dir, self.log_filename)
        self.log_file = open(self.log_path, 'w', newline='')

        if self.config.save_statistics:
            self.stats_filename = f"TrisonicaStats_{timestamp}.csv"
            self.stats_path = os.path.join(self.config.log_dir, self.stats_filename)
            self.stats_file = open(self.stats_path, 'w', newline='')
            self.stats_file.write("timestamp,parameter,min,max,mean,count,error_count,total_readings\n")

        logging.info(f"Data file: {self.log_filename}")

    def find_serial_ports(self) -> List[str]:
        """Find all available serial ports"""
        patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyAMA*']
        ports = []
        for pattern in patterns:
            ports.extend(glob.glob(pattern))
        return sorted(set(ports))

    def wait_for_trisonica(self) -> Optional[str]:
        """Wait for Trisonica device"""
        logging.info("Waiting for Trisonica device...")

        while self.running:
            ports = self.find_serial_ports()

            if not ports:
                logging.info("No serial ports found, waiting...")
                time.sleep(DEVICE_CHECK_INTERVAL)
                continue

            for port in ports:
                try:
                    logging.info(f"Testing {port}...")
                    ser = serial.Serial(port, self.config.baud_rate, timeout=2)

                    # Test for Trisonica data
                    for _ in range(10):
                        try:
                            line = ser.readline().decode('ascii', errors='ignore').strip()
                            if line and any(param in line for param in ['S ', 'D ', 'T ', 'U ', 'V ']):
                                ser.close()
                                logging.info(f"Trisonica found on {port}")
                                return port
                        except:
                            continue

                    ser.close()

                except Exception as e:
                    logging.debug(f"Error testing {port}: {e}")

            logging.info("No Trisonica found, retrying...")
            time.sleep(DEVICE_CHECK_INTERVAL)

        return None

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logging.info(f"Received signal {signum}, shutting down...")
        self.led_controller.stop_blinking()
        self.save_final_statistics()
        self.running = False

    def connect_serial(self, port: str) -> bool:
        """Connect to serial port"""
        try:
            self.serial_port = serial.Serial(port, self.config.baud_rate, timeout=1)
            logging.info(f"Connected to {port}")
            return True
        except Exception as e:
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
        """Update CSV columns"""
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

        # Flash LED to indicate data write
        self.led_controller.flash_write_indicator()

    def calculate_statistics(self, key: str, value: float):
        """Calculate statistics"""
        if key not in self.stats:
            self.stats[key] = Statistics()

        stat = self.stats[key]
        stat.current_val = value
        stat.count += 1
        stat.values.append(value)

        if stat.count == 1:
            stat.min_val = stat.max_val = stat.mean_val = value
        else:
            stat.min_val = min(stat.min_val, value)
            stat.max_val = max(stat.max_val, value)
            stat.mean_val = sum(stat.values) / len(stat.values)

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

                    # Check for sensor errors and negative temperature
                    is_error = value <= -99.0
                    if key == 'T' and value < 0:  # Temperature should not be negative
                        is_error = True

                    if is_error:
                        self.data_quality['parameter_errors'][key]['error_count'] += 1
                        self.data_quality['error_count'] += 1
                    else:
                        self.calculate_statistics(key, value)

                except ValueError:
                    pass

            return DataPoint(timestamp, line, parsed)

        except Exception as e:
            logging.warning(f"Error reading data: {e}")
            return None

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
                good_count = stat.count
            else:
                min_val = max_val = mean_val = 0.0
                good_count = 0

            if key in self.data_quality['parameter_errors']:
                error_data = self.data_quality['parameter_errors'][key]
                error_count = error_data['error_count']
                total_readings = error_data['total_count']
            else:
                error_count = 0
                total_readings = good_count

            self.stats_file.write(f"{timestamp},{key},{min_val:.6f},{max_val:.6f},"
                                f"{mean_val:.6f},{good_count},{error_count},{total_readings}\n")

        self.stats_file.flush()

    def print_status(self):
        """Print detailed periodic status"""
        elapsed = time.time() - self.start_time
        rate = self.point_count / elapsed if elapsed > 0 else 0
        error_rate = (self.data_quality['error_count'] / max(1, self.data_quality['total_readings'])) * 100

        print(f"\n=== STATUS UPDATE [{datetime.datetime.now().strftime('%H:%M:%S')}] ===")
        print(f"Runtime: {datetime.timedelta(seconds=int(elapsed))}")
        print(f"Data points: {self.point_count:,} | Rate: {rate:.1f} Hz | Errors: {error_rate:.1f}%")

        # Show current values for key parameters
        if self.stats:
            print("Current readings:")
            key_params = ['S', 'S2', 'D', 'T', 'H', 'P']
            for param in key_params:
                if param in self.stats:
                    stat = self.stats[param]
                    unit = self.get_unit(param)
                    print(f"  {param}: {stat.current_val:.2f} {unit}")

        print(f"Log file: {os.path.basename(self.log_path)}")
        print("=" * 50)

    def get_unit(self, param):
        """Get unit for parameter"""
        units = {
            'S': 'm/s', 'S2': 'm/s', 'D': 'deg', 'T': '°C',
            'H': '%', 'P': 'hPa', 'U': 'm/s', 'V': 'm/s', 'W': 'm/s'
        }
        return units.get(param, '')

    def run(self):
        """Main execution loop"""
        self.running = True

        while self.running:
            # Wait for device
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

            # Connect
            if not self.connect_serial(port):
                if self.config.wait_for_device:
                    time.sleep(DEVICE_CHECK_INTERVAL)
                    continue
                else:
                    break

            logging.info("Starting data logging...")

            # Start Activity LED indicator (don't touch Power LED)
            self.led_controller.blink_activity_led(1.0)  # Activity LED blinking = logging active

            last_status = time.time()

            # Data logging loop
            while self.running and self.serial_port and self.serial_port.is_open:
                try:
                    data_point = self.read_serial_data()
                    if data_point:
                        self.point_count += 1
                        self.data_points.append(data_point)

                        # Periodic saves and status
                        if self.point_count % 100 == 0:
                            self.save_final_statistics()

                        if time.time() - last_status > 0.5:  # Every 0.5 seconds (2Hz)
                            self.print_status()
                            last_status = time.time()

                    time.sleep(0.01)

                except serial.SerialException as e:
                    logging.warning(f"Serial connection lost: {e}")
                    if self.config.wait_for_device:
                        break
                    else:
                        self.running = False

                except Exception as e:
                    logging.error(f"Error: {e}")
                    break

            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()

        self.cleanup()
        return True

    def cleanup(self):
        """Cleanup resources"""
        # Turn off Activity LED indicator (leave Power LED alone)
        self.led_controller.stop_blinking()
        self.led_controller.set_activity_led(False)

        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()

        if self.log_file and not self.log_file.closed:
            self.log_file.close()
            logging.info(f"Data saved: {self.log_path}")

        if self.stats_file and not self.stats_file.closed:
            self.stats_file.close()

        if self.point_count > 0:
            elapsed = time.time() - self.start_time
            avg_rate = self.point_count / elapsed if elapsed > 0 else 0
            logging.info(f"Session: {self.point_count:,} points, {avg_rate:.1f} Hz average")

def main():
    parser = argparse.ArgumentParser(description='Simple Trisonica Data Logger')
    parser.add_argument('--port', default='auto', help='Serial port')
    parser.add_argument('--baud', type=int, default=DEFAULT_BAUD_RATE, help='Baud rate')
    parser.add_argument('--log-dir', help='Log directory')
    parser.add_argument('--no-wait', action='store_true', help='Do not wait for device')

    args = parser.parse_args()

    config = Config(
        serial_port=args.port,
        baud_rate=args.baud,
        log_dir=args.log_dir or EXTERNAL_SD_MOUNTPOINT,
        wait_for_device=not args.no_wait
    )

    logger = TrisonicaLogger(config)
    sys.exit(0 if logger.run() else 1)

if __name__ == '__main__':
    main()