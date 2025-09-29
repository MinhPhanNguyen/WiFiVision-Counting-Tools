from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import os
import time
import threading
import csv
import json
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import base64
from io import BytesIO
import glob
import traceback

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

app = Flask(__name__)
CORS(app)  # Enable CORS for React Native

# Configuration
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT = 0.1
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CSI_DIR = os.path.join(DATA_DIR, "csi")
CHART_DIR = os.path.join(DATA_DIR, "chart")
VIDEO_DIR = os.path.join(DATA_DIR, "video")
IMAGE_DIR = os.path.join(DATA_DIR, "images")

# Global variables for ESP32 serial handler and video recorder
esp32_serial_handler = None
video_recorder = None
collection_active = False
current_csv_file = None

class ESP32SerialHandler:
    def __init__(self):
        self.serial_available = SERIAL_AVAILABLE
        self.serial_connections = {}
        self.serial_threads = {}
        self.serial_listening = {}
        
        # Auto scan and connect khi khởi tạo
        if self.serial_available:
            self.auto_connect()
    
    def auto_connect(self):
        """Tự động scan và connect ESP32"""
        try:
            ports = list(serial.tools.list_ports.comports())
            esp32_ports = []
            
            for port in ports:
                desc = port.description.lower()
                vid_pid = f"{port.vid:04x}:{port.pid:04x}" if port.vid and port.pid else ""
                
                esp32_indicators = [
                    "esp32", "cp210", "ch340", "cp2102", "ft232", "silicon labs",
                    "1a86:7523", "10c4:ea60", "0403:6001"
                ]
                
                if any(indicator in desc or indicator in vid_pid for indicator in esp32_indicators):
                    esp32_ports.append(port)
            
            if esp32_ports:
                print(f"Found {len(esp32_ports)} ESP32 devices, connecting...")
                
                for port in esp32_ports:
                    try:
                        ser = serial.Serial(
                            port=port.device,
                            baudrate=SERIAL_BAUDRATE,
                            timeout=SERIAL_TIMEOUT,
                            write_timeout=2.0
                        )
                        
                        time.sleep(2)
                        ser.write(b'\n')
                        time.sleep(0.5)
                        
                        self.serial_connections[port.device] = ser
                        print(f"Connected to ESP32: {port.device}")
                        
                    except Exception as e:
                        print(f"Error connecting to {port.device}: {e}")
            else:
                print("No ESP32 devices found")
                
        except Exception as e:
            print(f"Error in auto_connect: {e}")
    
    def send_command(self, command):
        """Gửi lệnh đến tất cả ESP32"""
        if not self.serial_available or not self.serial_connections:
            return False
        
        success_count = 0
        for port_name, ser in self.serial_connections.items():
            try:
                command_bytes = f"{command}\n".encode('utf-8')
                ser.write(command_bytes)
                ser.flush()
                success_count += 1
            except Exception as e:
                print(f"Error sending command to {port_name}: {e}")
        
        return success_count > 0
    
    def is_connected(self):
        """Kiểm tra có ESP32 nào đang kết nối không"""
        return self.serial_available and len(self.serial_connections) > 0
    
    def start_serial_listening(self, csi_collector):
        """Bắt đầu đọc CSI data từ tất cả ESP32"""
        for port_name, ser in self.serial_connections.items():
            self.serial_listening[port_name] = True
            
            def serial_listener(port, serial_conn):
                while self.serial_listening.get(port, False):
                    try:
                        while serial_conn.in_waiting > 0:
                            try:
                                line = serial_conn.readline().decode('utf-8', errors='ignore').strip()
                                if line.startswith('CSI_DATA,'):
                                    csi_collector.add_data(line)
                            except UnicodeDecodeError:
                                continue
                        time.sleep(0.001)
                    except Exception as e:
                        print(f"Error reading from {port}: {e}")
                        break
            
            thread = threading.Thread(target=serial_listener, args=(port_name, ser), daemon=True)
            thread.start()
            self.serial_threads[port_name] = thread
        
        return len(self.serial_connections) > 0
    
    def stop_listening(self):
        """Dừng listening từ tất cả ESP32"""
        for port_name in list(self.serial_listening.keys()):
            self.serial_listening[port_name] = False
    
    def get_connected_devices(self):
        return list(self.serial_connections.keys())

class VideoRecorder:
    def __init__(self, ip_camera_url=None):
        # Use environment variable or fallback to default
        if ip_camera_url is None:
            camera_ip = os.getenv('EXPO_PUBLIC_CAMERA_IP', '172.20.10.11')
            camera_port = os.getenv('EXPO_PUBLIC_CAMERA_PORT', '8080')
            ip_camera_url = f"http://{camera_ip}:{camera_port}/video"
        
        self.ip_camera_url = ip_camera_url
        self.cap = None
        self.out = None
        self.recording = False
        self.frame_count = 0
        self.start_time = None
        self.video_thread = None
        self.output_path = None
        self.video_available = CV2_AVAILABLE
        
    def start_recording(self, distance="0"):
        """Bắt đầu quay video và lưu frame"""
        if not self.video_available:
            print("OpenCV not available - video recording disabled")
            return False
            
        if self.recording:
            print("Video recording already active")
            return False
            
        try:
            # Tạo thư mục
            os.makedirs(VIDEO_DIR, exist_ok=True)
            os.makedirs(IMAGE_DIR, exist_ok=True)
            
            # Kết nối camera
            self.cap = cv2.VideoCapture(self.ip_camera_url)
            
            # Đọc frame đầu tiên để lấy kích thước
            ret, frame = self.cap.read()
            if not ret or frame is None:
                print("Không nhận được hình ảnh từ webcam khi khởi tạo.")
                if self.cap:
                    self.cap.release()
                return False
                
            height, width = frame.shape[:2]
            
            # Tạo tên file video
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_path = os.path.join(VIDEO_DIR, f"video_{distance}m_{timestamp}.mp4")
            
            # Thiết lập video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.out = cv2.VideoWriter(self.output_path, fourcc, 25.0, (width, height))
            
            self.recording = True
            self.frame_count = 0
            self.start_time = time.time()
            
            # Bắt đầu thread quay video
            self.video_thread = threading.Thread(target=self._record_video, daemon=True)
            self.video_thread.start()
            
            return True
            
        except Exception as e:
            print(f"Error starting video recording: {e}")
            self.stop_recording()
            return False
    
    def _record_video(self):
        """Thread function để quay video"""
        fps = 25
        frame_interval = 1.0 / fps
        next_frame_time = time.time()

        while self.recording and self.cap and self.out:
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    print("Không nhận được hình ảnh từ webcam.")
                    break

                self.frame_count += 1

                # Lưu frame vào video
                self.out.write(frame)

                # Lưu frame thành ảnh với timestamp
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                image_filename = f"frame_{timestamp_str}.jpg"
                image_path = os.path.join(IMAGE_DIR, image_filename)
                cv2.imwrite(image_path, frame)

                # Đồng bộ chính xác thời gian
                next_frame_time += frame_interval
                sleep_time = next_frame_time - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                print(f"Error during video recording: {e}")
                break
    
    def stop_recording(self):
        """Dừng quay video"""
        if not self.recording:
            return None
            
        self.recording = False
        
        # Đợi thread kết thúc
        if self.video_thread and self.video_thread.is_alive():
            self.video_thread.join(timeout=5)
        
        # Giải phóng resources
        if self.cap:
            self.cap.release()
            self.cap = None
            
        if self.out:
            self.out.release()
            self.out = None
        
        duration = time.time() - self.start_time if self.start_time else 0
        result = {
            'video_path': self.output_path,
            'frame_count': self.frame_count,
            'duration': duration,
            'image_dir': IMAGE_DIR
        }
        
        return result

class CSICollector:
    def __init__(self):
        self.active = False
        self.csv_file = None
        self.csv_writer = None
        self.csv_handle = None
        self.packet_count = 0
        self.start_time = None
        self.latest_rssi = None  # Track latest RSSI for realtime monitoring
        
    def start(self, csv_file, duration=None):
        """Bắt đầu thu thập CSI - không auto stop nếu duration=None"""
        global collection_active, esp32_serial_handler
        
        self.csv_file = csv_file
        self.active = True
        self.packet_count = 0
        self.start_time = time.time()
        collection_active = True
        
        # Gửi lệnh bắt đầu ESP32 listening
        if esp32_serial_handler:
            print(f"Debug: esp32_serial_handler.is_connected() = {esp32_serial_handler.is_connected()}")
            print(f"Debug: serial_connections = {esp32_serial_handler.serial_connections}")
            
            if esp32_serial_handler.is_connected():
                try:
                    result = esp32_serial_handler.send_command("start_listen")  # start_listen command
                    print(f"Sent start_listen command to ESP32, result: {result}")
                except Exception as e:
                    print(f"Failed to send start_listen command to ESP32: {e}")
            else:
                print("ESP32 not connected - attempting reconnection...")
                esp32_serial_handler.auto_connect()
                if esp32_serial_handler.is_connected():
                    try:
                        result = esp32_serial_handler.send_command("start_listen")
                        print(f"Sent start_listen command to ESP32 after reconnect, result: {result}")
                    except Exception as e:
                        print(f"Failed to send start_listen command after reconnect: {e}")
                else:
                    print("Failed to reconnect to ESP32")
        else:
            print("ESP32 serial handler not available")
        
        # Mở file CSV để ghi
        headers = [
            "timestamp", "id", "mac", "rssi", "rate", "sig_mode", "mcs", 
            "bandwidth", "smoothing", "not_sounding", "aggregation", 
            "stbc", "fec_coding", "sgi", "noise_floor", "ampdu_cnt", 
            "channel", "secondary_channel", "local_timestamp", "ant", 
            "sig_len", "rx_state", "len", "first_word", "data"
        ]
        
        self.csv_handle = open(csv_file, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_handle)
        self.csv_writer.writerow(headers)
        self.csv_handle.flush()
        
        # Chỉ auto stop nếu có duration
        if duration and duration > 0:
            def auto_stop():
                time.sleep(duration)
                if self.active:
                    self.stop()
            
            timer_thread = threading.Thread(target=auto_stop, daemon=True)
            timer_thread.start()
            print(f"Auto-stop scheduled for {duration} seconds")
        else:
            print("Collection will run until manually stopped")
        
        return True
    
    def add_data(self, csi_data):
        """Thêm CSI data vào file - xử lý giống main.py"""
        if not self.active or not self.csv_writer:
            return False
            
        try:
            timestamp = datetime.now().isoformat()
            
            if csi_data.startswith('CSI_DATA,'):
                csv_data = csi_data[9:]  # Bỏ "CSI_DATA,"
                row = [timestamp] + csv_data.split(',')
                
                # Extract and store latest RSSI for realtime monitoring
                try:
                    # RSSI is typically the 3rd field after timestamp and id
                    rssi_field = row[3] if len(row) > 3 else None
                    if rssi_field:
                        self.latest_rssi = float(rssi_field)
                            
                except (IndexError, ValueError):
                    pass  # Keep previous RSSI if parsing fails
                
                self.csv_writer.writerow(row)
                self.csv_handle.flush()
                self.packet_count += 1
                
                # Show progress every 50 packets to reduce spam
                if self.packet_count % 50 == 0:
                    elapsed = time.time() - self.start_time
                    rate = self.packet_count / elapsed if elapsed > 0 else 0
                
                return True
            else:
                return False
                
        except Exception as e:
            print(f"Error adding CSI data: {e}")
            
        return False
    
    def stop(self):
        """Dừng thu thập CSI"""
        global collection_active, esp32_serial_handler
        
        if self.active:
            self.active = False
            collection_active = False
            
            # Gửi lệnh dừng ESP32 listening
            print(f"Debug Stop: esp32_serial_handler = {esp32_serial_handler}")
            
            if esp32_serial_handler and esp32_serial_handler.is_connected():
                try:
                    result = esp32_serial_handler.send_command("stop_listen")  # stop_listen command
                    print(f"Sent stop_listen command to ESP32, result: {result}")
                except Exception as e:
                    print(f"Failed to send stop_listen command to ESP32: {e}")
            else:
                print("ESP32 not connected during stop")
            
            if self.csv_handle:
                self.csv_handle.close()
                self.csv_handle = None
                self.csv_writer = None
            
            elapsed = time.time() - self.start_time if self.start_time else 0
            
            # Auto-generate chart after collecting data
            chart_file = None
            if self.csv_file and os.path.exists(self.csv_file) and self.packet_count > 0:
                try:
                    chart_file = self.generate_chart_automatically()
                except Exception as e:
                    print(f"Failed to auto-generate chart: {e}")
            
            return {
                'packets': self.packet_count,
                'duration': elapsed,
                'csv_file': self.csv_file,
                'chart_file': chart_file
            }
        
        return None
    
    def generate_chart_automatically(self):
        """Tự động tạo chart từ CSV file"""
        if not self.csv_file or not os.path.exists(self.csv_file):
            return None
            
        try:
            # Tạo tên file chart
            base_name = os.path.splitext(os.path.basename(self.csv_file))[0]
            chart_file = os.path.join(CHART_DIR, f"{base_name}_chart.png")
            
            # Đọc dữ liệu
            df = load_csi_data_for_chart(self.csv_file)
            if df is None:
                return None
            
            # Tạo chart directory nếu chưa có
            os.makedirs(CHART_DIR, exist_ok=True)
            
            # Tạo chart
            success = self.create_chart_from_dataframe(df, chart_file)
            if success:
                print(f"Auto-generated chart: {chart_file}")
                return chart_file
            
        except Exception as e:
            print(f"Error auto-generating chart: {e}")
            
        return None
    
    def create_chart_from_dataframe(self, df, chart_file):
        """Tạo chart từ DataFrame"""
        try:
            plt.ioff()
            plt.rcParams['font.family'] = ['Arial Unicode MS', 'DejaVu Sans', 'sans-serif']
            
            fig, ax = plt.subplots(figsize=(10, 6))  # Reduced size for mobile
            
            # Vẽ đường CSI từ individual values (nối các điểm đỏ)
            ax.plot(df['elapsed_seconds'], df['rssi'], 'ro-', linewidth=2, markersize=4, alpha=0.8, label='CSI Line (Individual RSSI values)', zorder=3)
            
            # Vẽ đường trung bình tích lũy
            ax.plot(df['elapsed_seconds'], df['cumulative_mean'], 'b-', linewidth=3, alpha=0.9, label='Cumulative Average RSSI', zorder=2)
            
            # Tính và hiển thị thống kê
            mean_rssi = df['rssi'].mean()
            std_rssi = df['rssi'].std()
            
            ax.axhline(y=mean_rssi, color='green', linestyle='--', linewidth=2, label=f'Average: {mean_rssi:.1f} dBm', zorder=1)
            ax.fill_between(df['elapsed_seconds'], mean_rssi - std_rssi, mean_rssi + std_rssi, alpha=0.2, color='green', label=f'±1 StdDev: {std_rssi:.1f} dB', zorder=1)
            
            # Cài đặt trục và labels
            ax.set_xlabel('Time (seconds)', fontsize=12)
            ax.set_ylabel('RSSI (dBm)', fontsize=12)
            ax.set_title(f'CSI Signal Strength Analysis\n{len(df)} packets, Duration: {df["elapsed_seconds"].max():.1f}s', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best', fontsize=10)
            
            # Cài đặt giới hạn trục Y - tự động dựa trên dữ liệu thực
            data_min = df['rssi'].min()
            data_max = df['rssi'].max()
            data_range = data_max - data_min
            
            # Thêm margin 15% cho trục Y để chart không bị sát viền
            margin = max(data_range * 0.15, 3)  # Minimum 3 dBm margin
            y_min = data_min - margin
            y_max = data_max + margin
            
            ax.set_ylim(y_min, y_max)
            
            # Lưu chart với nền trắng và DPI thấp hơn cho mobile
            plt.tight_layout()
            plt.savefig(chart_file, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')  # Reduced DPI from 300
            plt.close()
            
            return True
            
        except Exception as e:
            print(f"Error creating chart: {e}")
            return False

# Global CSI collector instance
csi_collector = CSICollector()

# Global video recorder instance
video_recorder = VideoRecorder()

# Global ESP32 handler instance
print(f"Initializing ESP32 handler... SERIAL_AVAILABLE = {SERIAL_AVAILABLE}")
esp32_serial_handler = ESP32SerialHandler() if SERIAL_AVAILABLE else None
if esp32_serial_handler:
    print(f"ESP32 handler created. Connections: {esp32_serial_handler.serial_connections}")
else:
    print("ESP32 handler not created - serial not available")

def create_directories():
    """Tạo các thư mục cần thiết"""
    os.makedirs(CSI_DIR, exist_ok=True)
    os.makedirs(CHART_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)

def load_csi_data_for_chart(file_path):
    """Đọc dữ liệu CSI từ CSV để tạo chart"""
    try:
        print(f"Reading CSV file: {file_path}")
        
        data_rows = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Skip header
            print(f"CSV Headers: {headers}")
            
            for row_num, row in enumerate(reader):
                try:
                    if len(row) >= 4:
                        timestamp = row[0]
                        rssi = float(row[3])  # RSSI ở cột thứ 4 (index 3)
                        
                        data_rows.append({
                            'timestamp': timestamp,
                            'rssi': rssi
                        })
                        
                        # Debug first few rows
                        if row_num < 3:
                            print(f"Row {row_num}: timestamp={timestamp}, rssi={rssi}")
                            
                except (ValueError, IndexError) as e:
                    print(f"Error parsing row {row_num}: {e}, row: {row}")
                    continue
        
        if not data_rows:
            print("No valid data found in CSV file!")
            return None
        
        print(f"Successfully parsed {len(data_rows)} data points")
        
        # Chuyển thành DataFrame
        df = pd.DataFrame(data_rows)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Tính thời gian tương đối (giây)
        start_time = df['timestamp'].min()
        df['elapsed_seconds'] = (df['timestamp'] - start_time).dt.total_seconds()
        
        # Trung bình tích lũy
        df['cumulative_mean'] = df['rssi'].expanding().mean()
        
        print(f"Processed {len(df)} records, duration: {df['elapsed_seconds'].max():.1f}s")
        print(f"RSSI range: {df['rssi'].min():.1f} to {df['rssi'].max():.1f} dBm")
        
        return df
        
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        import traceback
        traceback.print_exc()
        return None

def load_csi_data_for_overview(file_path):
    """Đọc dữ liệu CSI từ CSV để tính RSSI trung bình"""
    try:
        print(f"Reading CSV for overview: {file_path}")
        
        data_rows = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Skip header
            
            for row_num, row in enumerate(reader):
                try:
                    if len(row) >= 4:
                        rssi = float(row[3])  # RSSI ở cột thứ 4 (index 3)
                        data_rows.append(rssi)
                except (ValueError, IndexError) as e:
                    print(f"Error parsing row {row_num} in {file_path}: {e}")
                    continue
        
        if data_rows:
            print(f"Found {len(data_rows)} RSSI values in {os.path.basename(file_path)}")
            print(f"RSSI range: {min(data_rows):.1f} to {max(data_rows):.1f} dBm")
        
        return data_rows if data_rows else None
        
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

# API Routes

@app.route('/api/status', methods=['GET'])
def get_status():
    """Lấy trạng thái hệ thống"""
    global esp32_serial_handler
    
    try:
        # Check ESP32 connections from serial handler
        esp32_count = 0
        esp32_devices = []
        
        if esp32_serial_handler:
            esp32_devices = esp32_serial_handler.get_connected_devices()
            esp32_count = len(esp32_devices)
        
        # Collection status details
        collection_details = {
            'active': collection_active,
            'packet_count': 0,
            'elapsed_time': 0,
            'csv_file': None,
            'current_rssi': None,
            'current_rate': 0.0
        }
        
        if collection_active and csi_collector.active:
            elapsed = time.time() - csi_collector.start_time if csi_collector.start_time else 0
            rate = csi_collector.packet_count / elapsed if elapsed > 0 else 0
            collection_details.update({
                'packet_count': csi_collector.packet_count,
                'elapsed_time': elapsed,
                'csv_file': csi_collector.csv_file,
                'current_rate': rate
            })
            
            # Get latest RSSI if available
            if hasattr(csi_collector, 'latest_rssi'):
                collection_details['current_rssi'] = csi_collector.latest_rssi
        
        return jsonify({
            'status': 'success',
            'data': {
                'collection_active': collection_active,
                'current_rssi': collection_details.get('current_rssi'),
                'packet_count': collection_details.get('packet_count', 0),
                'current_rate': collection_details.get('current_rate', 0.0),
                'duration': collection_details.get('elapsed_time', 0),
                'esp32_connected': esp32_count > 0,
                # Legacy fields for backward compatibility
                'serial_available': SERIAL_AVAILABLE,
                'esp32_devices': esp32_devices,
                'collection_details': collection_details,
                'data_dir': os.path.abspath(DATA_DIR),
                'csi_dir': os.path.abspath(CSI_DIR),
                'chart_dir': os.path.abspath(CHART_DIR)
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/esp32/scan', methods=['GET'])
def scan_esp32():
    """Quét tìm ESP32 devices"""
    try:
        if not SERIAL_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'Serial not available'
            }), 400
        
        ports = list(serial.tools.list_ports.comports())
        esp32_ports = []
        
        for port in ports:
            desc = port.description.lower()
            vid_pid = f"{port.vid:04x}:{port.pid:04x}" if port.vid and port.pid else ""
            
            esp32_indicators = [
                "esp32", "cp210", "ch340", "cp2102", "ft232", "silicon labs",
                "1a86:7523", "10c4:ea60", "0403:6001"
            ]
            
            if any(indicator in desc or indicator in vid_pid for indicator in esp32_indicators):
                esp32_ports.append({
                    'port': port.device,
                    'description': port.description,
                    'vid_pid': vid_pid
                })
        
        return jsonify({
            'status': 'success',
            'data': {
                'esp32_devices': esp32_ports,
                'total_found': len(esp32_ports)
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Main API Routes

@app.route('/api/collection/start', methods=['POST'])
def start_collection():
    """Bắt đầu thu thập CSI data từ ESP32 và quay video"""
    global collection_active, csi_collector, esp32_serial_handler, video_recorder
    
    try:
        data = request.get_json()
        distance = data.get('distance', '0')
        duration = data.get('duration', None)  # No default duration - manual stop required
        
        if collection_active:
            return jsonify({
                'status': 'error',
                'message': 'Collection already active'
            }), 400
        
        # Kiểm tra ESP32 connection
        if not esp32_serial_handler or len(esp32_serial_handler.get_connected_devices()) == 0:
            return jsonify({
                'status': 'error',
                'message': 'No ESP32 devices connected. Please connect ESP32 and restart server.'
            }), 400
        
        create_directories()
        
        # Tạo tên file CSI
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = os.path.join(CSI_DIR, f"csi_{distance}m.csv")
        
        # Bắt đầu collection với CSICollector (không auto-stop)
        success = csi_collector.start(csv_file, duration=None)
        
        if not success:
            return jsonify({
                'status': 'error',
                'message': 'Failed to start collection'
            }), 500
        
        # Gửi lệnh serial data mode đến ESP32 (command "6")
        serial_mode_success = False
        for attempt in range(3):
            esp32_success = esp32_serial_handler.send_command("6")
            if esp32_success:
                time.sleep(2)
                
                for check in range(10):
                    if any(ser.in_waiting > 0 for ser in esp32_serial_handler.serial_connections.values()):
                        for port_name, ser in esp32_serial_handler.serial_connections.items():
                            if ser.in_waiting > 0:
                                response = ser.readline().decode('utf-8', errors='ignore').strip()
                                if "Serial Data output: ON" in response:
                                    serial_mode_success = True
                                    break
                    if serial_mode_success:
                        break
                    time.sleep(0.2)
                
                if serial_mode_success:
                    break
            
            time.sleep(1)
        
        # Gửi lệnh start listening đến ESP32 (command "1") 
        esp32_serial_handler.send_command("1")
        time.sleep(1)
        
        # Bắt đầu quay video trước khi bắt đầu CSI để đồng bộ thời gian
        video_started = video_recorder.start_recording(distance)
        if not video_started:
            print("Warning: Failed to start video recording - continuing with CSI collection only")
        
        # Bắt đầu đọc CSI data từ ESP32
        listening_started = esp32_serial_handler.start_serial_listening(csi_collector)
        
        if not listening_started:
            csi_collector.stop()
            if video_started:
                video_recorder.stop_recording()
            return jsonify({
                'status': 'error',
                'message': 'Failed to start ESP32 serial listening'
            }), 500
        
        return jsonify({
            'status': 'success',
            'data': {
                'collection_id': timestamp,
                'csv_file': csv_file,
                'distance': distance,
                'duration': 'Manual stop required',
                'esp32_devices': esp32_serial_handler.get_connected_devices(),
                'video_recording': video_started,
                'video_path': video_recorder.output_path if video_started else None,
                'message': f'CSI collection{"and video recording" if video_started else ""} started. Reading data from ESP32. Use Stop button to end collection.'
            }
        })
    except Exception as e:
        collection_active = False
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/collection/stop', methods=['POST'])
def stop_collection():
    """Dừng thu thập CSI data và quay video"""
    global collection_active, csi_collector, esp32_serial_handler, video_recorder
    
    try:
        if not collection_active:
            return jsonify({
                'status': 'error',
                'message': 'No active collection'
            }), 400
        
        # Dừng ESP32 serial listening
        if esp32_serial_handler:
            esp32_serial_handler.stop_listening()
        
        # Dừng collection
        result = csi_collector.stop()
        
        # Dừng video recording
        video_result = video_recorder.stop_recording()
        
        if result:
            response_data = {
                'message': 'Collection and video recording stopped',
                'packets_collected': result['packets'],
                'duration': result['duration'],
                'csv_file': result['csv_file']
            }
            
            # Thêm video info nếu có
            if video_result:
                response_data['video_path'] = video_result['video_path']
                response_data['video_frames'] = video_result['frame_count']
                response_data['video_duration'] = video_result['duration']
                response_data['image_dir'] = video_result['image_dir']
            
            # Thêm chart file info nếu có
            if result.get('chart_file'):
                response_data['chart_file'] = result['chart_file']
                response_data['message'] += ' and chart auto-generated'
            
            return jsonify({
                'status': 'success',
                'data': response_data
            })
        else:
            return jsonify({
                'status': 'success',
                'data': {
                    'message': 'Collection stopped (no active collection found)'
                }
            })
            
    except Exception as e:
        collection_active = False
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/collection/status', methods=['GET'])
def get_collection_status():
    """Lấy trạng thái collection hiện tại"""
    global collection_active, csi_collector
    
    try:
        if collection_active and csi_collector.active:
            elapsed = time.time() - csi_collector.start_time if csi_collector.start_time else 0
            return jsonify({
                'status': 'success',
                'data': {
                    'active': True,
                    'packet_count': csi_collector.packet_count,
                    'elapsed_time': elapsed,
                    'csv_file': csi_collector.csv_file
                }
            })
        else:
            return jsonify({
                'status': 'success',
                'data': {
                    'active': False,
                    'packet_count': 0,
                    'elapsed_time': 0,
                    'csv_file': None
                }
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/esp32/test', methods=['POST'])
def test_esp32_communication():
    """Test ESP32 communication và commands"""
    global esp32_serial_handler
    
    try:
        if not esp32_serial_handler:
            return jsonify({
                'status': 'error',
                'message': 'ESP32 handler not initialized'
            }), 400
        
        devices = esp32_serial_handler.get_connected_devices()
        if not devices:
            return jsonify({
                'status': 'error',
                'message': 'No ESP32 devices connected'
            }), 400
        
        data = request.get_json()
        command = data.get('command', '0')  # Default: status command
        
        print(f"🧪 Testing ESP32 communication with command: {command}")
        
        # Send test command
        success = esp32_serial_handler.send_command(command)
        
        # Wait a bit and check for response
        time.sleep(1)
        
        result = {
            'devices': devices,
            'command_sent': command,
            'send_success': success,
            'message': f'Command "{command}" sent to {len(devices)} device(s)'
        }
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/files/list', methods=['GET'])
def list_files():
    """Lấy danh sách file CSI"""
    try:
        file_type = request.args.get('type', 'csi')  # 'csi', 'chart', or 'images'
        
        if file_type == 'csi':
            target_dir = CSI_DIR
            pattern = "*.csv"
        elif file_type == 'chart':
            target_dir = CHART_DIR
            pattern = "*.png"
        elif file_type == 'images':
            target_dir = IMAGE_DIR
            pattern = "*.jpg"
        else:
            target_dir = CHART_DIR
            pattern = "*.png"
        
        if not os.path.exists(target_dir):
            return jsonify({
                'status': 'success',
                'data': {
                    'files': [],
                    'total': 0
                }
            })
        
        files = []
        for file_path in glob.glob(os.path.join(target_dir, pattern)):
            file_info = {
                'name': os.path.basename(file_path),
                'path': file_path,
                'size': os.path.getsize(file_path),
                'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            }
            
            # Trích xuất khoảng cách từ tên file nếu có
            if file_type == 'csi':
                try:
                    distance_str = file_info['name'].replace('csi_', '').replace('m.csv', '')
                    file_info['distance'] = float(distance_str)
                except:
                    file_info['distance'] = None
            
            files.append(file_info)
        
        # Sắp xếp theo khoảng cách hoặc tên
        if file_type == 'csi':
            files.sort(key=lambda x: x['distance'] if x['distance'] is not None else float('inf'))
        else:
            files.sort(key=lambda x: x['name'])
        
        return jsonify({
            'status': 'success',
            'data': {
                'files': files,
                'total': len(files)
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/chart/generate', methods=['POST'])
def generate_chart():
    """Tạo chart từ file CSI"""
    try:
        data = request.get_json()
        csv_file = data.get('csv_file')
        
        if not csv_file or not os.path.exists(csv_file):
            return jsonify({
                'status': 'error',
                'message': 'CSV file not found'
            }), 404
        
        # Tạo tên file chart
        base_name = os.path.splitext(os.path.basename(csv_file))[0]
        chart_file = os.path.join(CHART_DIR, f"{base_name}_chart.png")
        
        # Đọc dữ liệu
        df = load_csi_data_for_chart(csv_file)
        if df is None:
            return jsonify({
                'status': 'error',
                'message': 'No valid data in CSV file'
            }), 400
        
        # Tạo chart
        try:
            plt.ioff()
            plt.rcParams['font.family'] = ['Arial Unicode MS', 'DejaVu Sans', 'sans-serif']
            
            fig, ax = plt.subplots(figsize=(10, 6))  # Reduced size for mobile
            
            # Vẽ đường CSI từ individual values (nối các điểm đỏ)
            ax.plot(df['elapsed_seconds'], df['rssi'], 'ro-', linewidth=2, markersize=4, alpha=0.8, label='CSI Line (Individual RSSI values)', zorder=3)
            
            # Vẽ đường trung bình tích lũy
            ax.plot(df['elapsed_seconds'], df['cumulative_mean'], 
                    color='blue', linewidth=3, alpha=0.9, 
                    label=f'Trung binh tich luy', zorder=5)
            
            # Định dạng
            ax.set_xlabel('Thoi gian (giay)', fontsize=12, fontweight='bold')
            ax.set_ylabel('RSSI (dBm)', fontsize=12, fontweight='bold')
            ax.set_title('CSI Data - Trung binh tich luy RSSI theo thoi gian', 
                        fontsize=14, fontweight='bold', pad=20)
            
            ax.grid(True, alpha=0.3, linestyle='--')
            
            # Giới hạn trục Y - tự động dựa trên dữ liệu thực
            data_min = df['rssi'].min()
            data_max = df['rssi'].max()
            data_range = data_max - data_min
            
            # Thêm margin 15% cho trục Y để chart không bị sát viền
            margin = max(data_range * 0.15, 3)  # Minimum 3 dBm margin
            y_min = data_min - margin
            y_max = data_max + margin
            
            ax.set_ylim(y_min, y_max)
            
            # Thống kê
            final_avg = df['cumulative_mean'].iloc[-1]
            total_time = df['elapsed_seconds'].max()
            total_packets = len(df)
            rate = total_packets / total_time if total_time > 0 else 0
            
            # Mức độ tín hiệu
            if final_avg >= -30:
                signal_level = "CUC MANH"
                distance_estimate = "vai cm - 1m"
            elif final_avg >= -70:
                signal_level = "TOT - TRUNG BINH"
                distance_estimate = "2-10m"
            elif final_avg >= -90:
                signal_level = "YEU"
                distance_estimate = "10-20m"
            else:
                signal_level = "RAT YEU"
                distance_estimate = "gan mat ket noi"
            
            # Text box thống kê
            stats_text = f'Ket qua cuoi:\n' \
                        f'• Trung binh: {final_avg:.1f} dBm\n' \
                        f'• Muc do: {signal_level}\n' \
                        f'• Khoang cach: {distance_estimate}\n\n' \
                        f'TONG KET:\n' \
                        f'• Packets: {total_packets}\n' \
                        f'• Duration: {total_time:.0f}s\n' \
                        f'• Rate: {rate:.1f}/s'
            
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                    fontsize=9, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.9))
            
            ax.legend(loc='upper right', ncol=2, fontsize=9, framealpha=0.9)
            
            plt.tight_layout()
            plt.savefig(chart_file, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')  # Reduced DPI
            plt.close()
            
            return jsonify({
                'status': 'success',
                'data': {
                    'chart_file': chart_file,
                    'stats': {
                        'final_avg': final_avg,
                        'signal_level': signal_level,
                        'distance_estimate': distance_estimate,
                        'total_packets': total_packets,
                        'total_time': total_time,
                        'rate': rate
                    }
                }
            })
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Chart generation failed: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/chart/overview', methods=['GET'])
def generate_overview_chart():
    """Tạo overview chart từ tất cả file CSI"""
    try:
        # Tìm tất cả file CSV trong CSI directory
        csv_files = glob.glob(os.path.join(CSI_DIR, "*.csv"))
        
        if not csv_files:
            return jsonify({
                'status': 'error',
                'message': 'No CSV files found'
            }), 404
        
        # Thu thập dữ liệu từ tất cả files
        distance_data = []
        
        for csv_file in csv_files:
            # Trích xuất khoảng cách từ tên file
            try:
                filename = os.path.basename(csv_file)
                distance_str = filename.replace('csi_', '').replace('m.csv', '')
                distance = float(distance_str)
            except:
                continue
            
            # Đọc file và tính RSSI trung bình
            rssi_values = load_csi_data_for_overview(csv_file)
            
            if rssi_values is not None and len(rssi_values) > 0:
                avg_rssi = np.mean(rssi_values)
                std_rssi = np.std(rssi_values)
                min_rssi = np.min(rssi_values)
                max_rssi = np.max(rssi_values)
                
                distance_data.append({
                    'distance': distance,
                    'avg_rssi': avg_rssi,
                    'std_rssi': std_rssi,
                    'min_rssi': min_rssi,
                    'max_rssi': max_rssi,
                    'file': filename,
                    'packet_count': len(rssi_values)
                })
        
        if not distance_data:
            return jsonify({
                'status': 'error',
                'message': 'No valid data found in CSV files'
            }), 400
        
        # Sắp xếp theo khoảng cách
        distance_data.sort(key=lambda x: x['distance'])
        
        # Tạo overview chart
        plt.rcParams['font.family'] = ['Arial Unicode MS', 'DejaVu Sans', 'sans-serif']
        
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Vùng màu theo mức độ tín hiệu
        ax.axhspan(0, -30, alpha=0.15, color='green', label='Cuc manh (0 den -30 dBm)')
        ax.axhspan(-30, -70, alpha=0.15, color='yellow', label='Tot - trung binh (-30 den -70 dBm)')
        ax.axhspan(-70, -90, alpha=0.15, color='orange', label='Yeu (-70 den -90 dBm)')
        ax.axhspan(-90, -120, alpha=0.15, color='red', label='Rat yeu (-90 den -120 dBm)')
        
        # Dữ liệu cho chart
        distances = [d['distance'] for d in distance_data]
        rssi_values = [d['avg_rssi'] for d in distance_data]
        std_values = [d['std_rssi'] for d in distance_data]
        
        # Vẽ đường với error bars
        ax.errorbar(distances, rssi_values, yerr=std_values, 
                   fmt='bo-', linewidth=3, markersize=10, capsize=5,
                   color='blue', ecolor='lightblue', 
                   label='RSSI trung binh ± do lech chuan')
        
        # Thêm labels cho từng điểm
        for i, data in enumerate(distance_data):
            ax.annotate(f'{data["avg_rssi"]:.1f}dBm\n({data["packet_count"]} pkts)', 
                       (data['distance'], data['avg_rssi']),
                       textcoords="offset points", xytext=(0,20), ha='center',
                       fontsize=9, fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.8))
        
        # Định dạng trục
        ax.set_xlabel('Khoang cach (m)', fontsize=14, fontweight='bold')
        ax.set_ylabel('RSSI (dBm)', fontsize=14, fontweight='bold')
        ax.set_title('CSI Overview - RSSI theo khoang cach\n(Tong hop tu tat ca file trong data/csi)', 
                    fontsize=16, fontweight='bold', pad=20)
        
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Giới hạn trục với padding
        if rssi_values:
            y_min = min(min(rssi_values) - max(std_values) - 10, -120)
            y_max = max(max(rssi_values) + max(std_values) + 10, 0)
            ax.set_ylim(y_min, y_max)
        
        if distances:
            x_min = max(min(distances) - max(distances) * 0.05, 0)
            x_max = max(distances) + max(distances) * 0.05
            ax.set_xlim(x_min, x_max)
        
        # Thống kê tổng quan
        total_files = len(distance_data)
        total_packets = sum(d['packet_count'] for d in distance_data)
        min_distance = min(distances) if distances else 0
        max_distance = max(distances) if distances else 0
        min_rssi_val = min(rssi_values) if rssi_values else 0
        max_rssi_val = max(rssi_values) if rssi_values else 0
        
        # Tính độ suy hao signal (dBm/m)
        signal_loss_per_m = 0
        if len(distances) >= 2:
            coeffs = np.polyfit(distances, rssi_values, 1)
            signal_loss_per_m = coeffs[0]  # dBm/m
            
            # Vẽ đường trend
            trend_line = np.poly1d(coeffs)
            ax.plot(distances, trend_line(distances), 'r--', alpha=0.7, linewidth=2,
                   label=f'Xu huong ({signal_loss_per_m:.2f} dBm/m)')
        
        stats_text = f'Tong quan:\n' \
                    f'• So file: {total_files}\n' \
                    f'• Tong packets: {total_packets:,}\n' \
                    f'• Khoang cach: {min_distance}m - {max_distance}m\n' \
                    f'• RSSI range: {min_rssi_val:.1f} den {max_rssi_val:.1f} dBm\n' \
                    f'• Suy hao: {abs(signal_loss_per_m):.2f} dBm/m'
        
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                fontsize=11, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.9))
        
        ax.legend(loc='upper right', fontsize=10, framealpha=0.9)
        
        plt.tight_layout()
        
        # Lưu file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        overview_file = os.path.join(CHART_DIR, f'overview_rssi_distance_{timestamp}.png')
        overview_latest = os.path.join(CHART_DIR, 'overview_rssi_distance_latest.png')
        
        plt.savefig(overview_file, dpi=300, bbox_inches='tight')
        plt.savefig(overview_latest, dpi=300, bbox_inches='tight')
        plt.close()
        
        return jsonify({
            'status': 'success',
            'data': {
                'overview_file': overview_file,
                'overview_latest': overview_latest,
                'distance_data': distance_data,
                'stats': {
                    'total_files': total_files,
                    'total_packets': total_packets,
                    'distance_range': [min_distance, max_distance],
                    'rssi_range': [min_rssi_val, max_rssi_val],
                    'signal_loss_per_m': signal_loss_per_m
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/files/delete', methods=['DELETE'])
def delete_file():
    """Xóa file CSV hoặc chart"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        file_type = data.get('type', 'auto')  # 'csv', 'chart', or 'auto'
        
        if not filename:
            return jsonify({
                'status': 'error',
                'message': 'Filename is required'
            }), 400
        
        # Determine file path based on type
        if file_type == 'auto':
            if filename.endswith('.csv'):
                file_path = os.path.join(CSI_DIR, filename)
                file_type = 'csv'
            elif filename.endswith('.png'):
                file_path = os.path.join(CHART_DIR, filename)
                file_type = 'chart'
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Cannot determine file type from filename'
                }), 400
        elif file_type == 'csv':
            file_path = os.path.join(CSI_DIR, filename)
        elif file_type == 'chart':
            file_path = os.path.join(CHART_DIR, filename)
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid file type'
            }), 400
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404
        
        # Delete the file
        os.remove(file_path)
        
        print(f"Deleted {file_type} file: {filename}")
        
        return jsonify({
            'status': 'success',
            'data': {
                'filename': filename,
                'file_type': file_type,
                'message': f'File {filename} deleted successfully'
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/files/delete/all', methods=['DELETE'])
def delete_all_files():
    """Xóa tất cả file CSV và chart"""
    try:
        data = request.get_json() or {}
        file_type = data.get('type', 'all')  # 'csv', 'chart', or 'all'
        
        deleted_files = []
        
        if file_type in ['csv', 'all']:
            # Delete all CSV files
            csv_files = glob.glob(os.path.join(CSI_DIR, "*.csv"))
            for file_path in csv_files:
                try:
                    os.remove(file_path)
                    deleted_files.append({
                        'filename': os.path.basename(file_path),
                        'type': 'csv'
                    })
                except Exception as e:
                    print(f"Error deleting CSV file {file_path}: {e}")
        
        if file_type in ['chart', 'all']:
            # Delete all chart files
            chart_files = glob.glob(os.path.join(CHART_DIR, "*.png"))
            for file_path in chart_files:
                try:
                    os.remove(file_path)
                    deleted_files.append({
                        'filename': os.path.basename(file_path),
                        'type': 'chart'
                    })
                except Exception as e:
                    print(f"Error deleting chart file {file_path}: {e}")
        
        print(f"Deleted {len(deleted_files)} files")
        
        return jsonify({
            'status': 'success',
            'data': {
                'deleted_files': deleted_files,
                'total_deleted': len(deleted_files),
                'message': f'Deleted {len(deleted_files)} files'
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/files/download/<path:filename>', methods=['GET'])
def download_file(filename):
    """Download file (CSV or PNG)"""
    try:
        # Determine file type and directory
        if filename.endswith('.csv'):
            file_path = os.path.join(CSI_DIR, filename)
        elif filename.endswith('.png'):
            file_path = os.path.join(CHART_DIR, filename)
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid file type'
            }), 400
        
        if not os.path.exists(file_path):
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404
        
        # For PNG files, serve as inline image for React Native Image component
        if filename.endswith('.png'):
            return send_file(file_path, mimetype='image/png', as_attachment=False)
        else:
            # For CSV files, serve as attachment for download
            return send_file(file_path, as_attachment=True)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/data/raw/<path:filename>', methods=['GET'])
def get_raw_data(filename):
    """Lấy raw data từ CSV file"""
    try:
        file_path = os.path.join(CSI_DIR, filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404
        
        # Đọc dữ liệu CSV
        data_rows = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Get headers
            
            for row_num, row in enumerate(reader):
                if len(row) >= 4:
                    try:
                        data_rows.append({
                            'timestamp': row[0],
                            'id': row[1] if len(row) > 1 else '',
                            'mac': row[2] if len(row) > 2 else '',
                            'rssi': float(row[3]),
                            'raw_row': row
                        })
                    except (ValueError, IndexError):
                        continue
        
        return jsonify({
            'status': 'success',
            'data': {
                'headers': headers,
                'rows': data_rows,
                'total_rows': len(data_rows)
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/realtime/chart-data', methods=['GET'])
def get_realtime_chart_data():
    """Lấy dữ liệu CSI realtime cho chart"""
    global csi_collector
    
    try:
        if not csi_collector.active or not csi_collector.csv_file:
            return jsonify({
                'status': 'error',
                'message': 'No active CSI collection'
            }), 400
        
        # Đọc dữ liệu từ CSV file hiện tại
        if not os.path.exists(csi_collector.csv_file):
            return jsonify({
                'status': 'error', 
                'message': 'CSV file not found'
            }), 404
        
        # Load recent data for chart
        df = load_csi_data_for_chart(csi_collector.csv_file)
        if df is None or len(df) == 0:
            return jsonify({
                'status': 'success',
                'data': {
                    'chart_data': [],
                    'stats': {},
                    'collection_active': True
                }
            })
        
        # Lấy 100 điểm dữ liệu gần nhất để tránh chart quá nặng
        recent_df = df.tail(100) if len(df) > 100 else df
        
        # Chuẩn bị dữ liệu cho chart
        chart_data = []
        for _, row in recent_df.iterrows():
            chart_data.append({
                'x': float(row['elapsed_seconds']),
                'y': float(row['rssi']),
                'cumulative_avg': float(row['cumulative_mean'])
            })
        
        # Thống kê
        stats = {
            'total_packets': len(df),
            'current_rssi': float(df['rssi'].iloc[-1]) if len(df) > 0 else None,
            'avg_rssi': float(df['rssi'].mean()),
            'min_rssi': float(df['rssi'].min()),
            'max_rssi': float(df['rssi'].max()),
            'duration': float(df['elapsed_seconds'].max()) if len(df) > 0 else 0,
            'rate': csi_collector.packet_count / (time.time() - csi_collector.start_time) if csi_collector.start_time else 0
        }
        
        return jsonify({
            'status': 'success',
            'data': {
                'chart_data': chart_data,
                'stats': stats,
                'collection_active': True,
                'y_range': {
                    'min': float(recent_df['rssi'].min()),
                    'max': float(recent_df['rssi'].max())
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'CSI API is running',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/esp32/status', methods=['GET'])
def esp32_status():
    """Kiểm tra trạng thái ESP32"""
    try:
        status = {
            'serial_available': SERIAL_AVAILABLE,
            'handler_created': esp32_serial_handler is not None,
            'connections': {},
            'is_connected': False
        }
        
        if esp32_serial_handler:
            status['connections'] = {port: 'connected' for port in esp32_serial_handler.serial_connections.keys()}
            status['is_connected'] = esp32_serial_handler.is_connected()
            
        return jsonify({
            'status': 'success',
            'esp32_status': status
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/esp32/reconnect', methods=['POST'])
def esp32_reconnect():
    """Thử kết nối lại ESP32"""
    try:
        global esp32_serial_handler
        
        if not SERIAL_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'Serial library not available'
            }), 400
            
        if not esp32_serial_handler:
            esp32_serial_handler = ESP32SerialHandler()
        else:
            esp32_serial_handler.auto_connect()
            
        status = {
            'connections': list(esp32_serial_handler.serial_connections.keys()),
            'is_connected': esp32_serial_handler.is_connected()
        }
        
        return jsonify({
            'status': 'success',
            'message': 'Reconnection attempted',
            'esp32_status': status
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Camera-specific endpoints
@app.route('/api/camera/status', methods=['GET'])
def get_camera_status():
    """Kiểm tra trạng thái camera"""
    global video_recorder
    
    try:
        camera_status = {
            'opencv_available': CV2_AVAILABLE,
            'camera_url': video_recorder.ip_camera_url if video_recorder else None,
            'recording': video_recorder.recording if video_recorder else False,
            'frame_count': video_recorder.frame_count if video_recorder else 0,
            'connection_test': False
        }
        
        # Test camera connection
        if CV2_AVAILABLE and video_recorder:
            try:
                test_cap = cv2.VideoCapture(video_recorder.ip_camera_url)
                ret, frame = test_cap.read()
                camera_status['connection_test'] = ret and frame is not None
                if test_cap:
                    test_cap.release()
            except Exception as e:
                camera_status['connection_error'] = str(e)
        
        return jsonify({
            'status': 'success',
            'data': camera_status
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/camera/test', methods=['POST'])
def test_camera_connection():
    """Test kết nối camera và lấy 1 frame test"""
    global video_recorder
    
    try:
        if not CV2_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'OpenCV not available'
            }), 400
        
        if not video_recorder:
            return jsonify({
                'status': 'error',
                'message': 'Video recorder not initialized'
            }), 400
        
        # Test connection
        print(f"Testing camera connection to: {video_recorder.ip_camera_url}")
        
        cap = cv2.VideoCapture(video_recorder.ip_camera_url)
        
        # Try to read a frame
        ret, frame = cap.read()
        
        result = {
            'camera_url': video_recorder.ip_camera_url,
            'connection_successful': ret and frame is not None,
            'frame_captured': ret,
            'timestamp': datetime.now().isoformat()
        }
        
        if ret and frame is not None:
            height, width = frame.shape[:2]
            result.update({
                'frame_width': width,
                'frame_height': height,
                'message': f'Camera connected successfully! Frame size: {width}x{height}'
            })
            
            # Save test frame
            os.makedirs(IMAGE_DIR, exist_ok=True)
            test_image_path = os.path.join(IMAGE_DIR, 'camera_test_frame.jpg')
            cv2.imwrite(test_image_path, frame)
            result['test_image_path'] = test_image_path
        else:
            result['message'] = 'Failed to capture frame from camera'
        
        cap.release()
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Camera test failed: {str(e)}'
        }), 500

@app.route('/api/camera/start', methods=['POST'])
def start_camera_only():
    """Chỉ bắt đầu quay video (không thu thập CSI)"""
    global video_recorder
    
    try:
        data = request.get_json() or {}
        distance = data.get('distance', '0')
        
        if not CV2_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'OpenCV not available - cannot record video'
            }), 400
        
        if video_recorder.recording:
            return jsonify({
                'status': 'error',
                'message': 'Video recording already active'
            }), 400
        
        # Start video recording
        print(f"Attempting to start camera recording for distance: {distance}")
        print(f"Camera URL: {video_recorder.ip_camera_url}")
        success = video_recorder.start_recording(distance)
        print(f"Camera start result: {success}")
        
        if success:
            print(f"Camera recording started successfully. Output path: {video_recorder.output_path}")
            return jsonify({
                'status': 'success',
                'data': {
                    'message': 'Camera recording started successfully',
                    'video_path': video_recorder.output_path,
                    'distance': distance,
                    'camera_url': video_recorder.ip_camera_url,
                    'recording': True
                }
            })
        else:
            print("Failed to start camera recording")
            return jsonify({
                'status': 'error',
                'message': 'Failed to start camera recording - check camera connection'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/camera/stop', methods=['POST'])
def stop_camera_only():
    """Chỉ dừng quay video (không ảnh hưởng CSI)"""
    global video_recorder
    
    try:
        if not video_recorder.recording:
            # Không trả về lỗi, chỉ thông báo không có recording active
            return jsonify({
                'status': 'success',
                'data': {
                    'message': 'No active video recording to stop',
                    'recording': False
                }
            })
        
        # Stop video recording
        result = video_recorder.stop_recording()
        
        if result:
            return jsonify({
                'status': 'success',
                'data': {
                    'message': 'Camera recording stopped successfully',
                    'video_path': result['video_path'],
                    'frame_count': result['frame_count'],
                    'duration': result['duration'],
                    'image_dir': result['image_dir'],
                    'recording': False
                }
            })
        else:
            return jsonify({
                'status': 'success',
                'data': {
                    'message': 'Camera recording stopped (no active recording found)',
                    'recording': False
                }
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/camera/config', methods=['GET', 'POST'])
def camera_config():
    """Lấy hoặc cập nhật cấu hình camera"""
    global video_recorder
    
    if request.method == 'GET':
        try:
            config = {
                'camera_ip': os.getenv('EXPO_PUBLIC_CAMERA_IP', '172.20.10.11'),
                'camera_port': os.getenv('EXPO_PUBLIC_CAMERA_PORT', '8080'),
                'camera_url': video_recorder.ip_camera_url if video_recorder else None,
                'opencv_available': CV2_AVAILABLE
            }
            
            return jsonify({
                'status': 'success',
                'data': config
            })
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            camera_ip = data.get('camera_ip')
            camera_port = data.get('camera_port', '8080')
            
            if not camera_ip:
                return jsonify({
                    'status': 'error',
                    'message': 'camera_ip is required'
                }), 400
            
            # Update video recorder URL
            new_url = f"http://{camera_ip}:{camera_port}/video"
            
            if video_recorder:
                video_recorder.ip_camera_url = new_url
            
            # Test new connection
            test_result = False
            try:
                if CV2_AVAILABLE:
                    test_cap = cv2.VideoCapture(new_url)
                    ret, frame = test_cap.read()
                    test_result = ret and frame is not None
                    if test_cap:
                        test_cap.release()
            except:
                pass
            
            return jsonify({
                'status': 'success',
                'data': {
                    'message': 'Camera configuration updated',
                    'new_url': new_url,
                    'test_connection': test_result
                }
            })
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

@app.route('/api/sync/status', methods=['GET'])
def get_sync_status():
    """Lấy trạng thái synchronized data collection"""
    global synchronized_collector
    
    try:
        return jsonify({
            'status': 'success',
            'data': {
                'active': synchronized_collector.active,
                'start_time': synchronized_collector.start_time,
                'frame_buffer_size': len(synchronized_collector.frame_data_buffer),
                'csi_buffer_size': len(synchronized_collector.csi_data_buffer),
                'sync_file': getattr(synchronized_collector, 'sync_file', None)
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/sync/data', methods=['GET'])
def get_sync_data():
    """Lấy dữ liệu synchronized gần đây"""
    try:
        # Tìm file sync mới nhất
        sync_files = glob.glob(os.path.join(DATA_DIR, "synchronized_data_*.csv"))
        if not sync_files:
            return jsonify({
                'status': 'error',
                'message': 'No synchronized data files found'
            }), 404
        
        latest_file = max(sync_files, key=os.path.getctime)
        
        # Đọc 10 dòng cuối
        sync_data = []
        with open(latest_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Lấy header và 10 dòng cuối
            if len(lines) > 1:
                header = lines[0].strip().split(',')
                recent_lines = lines[-10:] if len(lines) > 11 else lines[1:]
                
                for line in recent_lines:
                    values = line.strip().split(',')
                    if len(values) == len(header):
                        sync_data.append(dict(zip(header, values)))
        
        return jsonify({
            'status': 'success',
            'data': {
                'sync_file': os.path.basename(latest_file),
                'total_entries': len(lines) - 1 if lines else 0,
                'recent_sync_data': sync_data
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    # Tạo directories khi start
    create_directories()
    
    # Run Flask app on port 5001 instead of 5000 (which is used by macOS AirPlay)
    app.run(host='0.0.0.0', port=5001, debug=True)