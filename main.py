import os
import time
import threading
import signal
import sys
import socket
import csv
import subprocess
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("Warning: pyserial not installed. ESP32 serial functions disabled.")

SERIAL_BAUDRATE = 115200  # Khớp với ESP32 
SERIAL_TIMEOUT = 0.1      # Giảm timeout để responsive hơn
COLLECTION_DURATION = 15  # Thời gian thu thập data (giây)

# Cấu trúc thư mục
DATA_DIR = "data"
CSI_DIR = os.path.join(DATA_DIR, "csi")
CHART_DIR = os.path.join(DATA_DIR, "chart")

def create_directories():
    """Tạo các thư mục cần thiết"""
    os.makedirs(CSI_DIR, exist_ok=True)
    os.makedirs(CHART_DIR, exist_ok=True)

def load_csi_data_for_chart(file_path):
    """Đọc dữ liệu CSI từ CSV để tạo chart"""
    try:
        print(f"Doc file: {file_path}")
        
        data_rows = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Skip header
            
            for row_num, row in enumerate(reader):
                try:
                    if len(row) >= 4:
                        timestamp = row[0]
                        rssi = float(row[3])  # RSSI ở cột thứ 4
                        
                        data_rows.append({
                            'timestamp': timestamp,
                            'rssi': rssi
                        })
                except (ValueError, IndexError):
                    continue
        
        if not data_rows:
            print("Khong co du lieu hop le!")
            return None
        
        # Chuyển thành DataFrame
        df = pd.DataFrame(data_rows)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Tính thời gian tương đối (giây)
        start_time = df['timestamp'].min()
        df['elapsed_seconds'] = (df['timestamp'] - start_time).dt.total_seconds()
        
        # Trung bình tích lũy
        df['cumulative_mean'] = df['rssi'].expanding().mean()
        
        print(f"Xu ly {len(df)} records, thoi gian: {df['elapsed_seconds'].max():.1f}s")
        return df
        
    except Exception as e:
        print(f"Loi doc file: {e}")
        return None

def create_chart(df, output_file):
    """Tạo biểu đồ CSI"""
    try:
        # Tắt interactive mode
        plt.ioff()
        
        # Thiết lập font
        plt.rcParams['font.family'] = ['Arial Unicode MS', 'DejaVu Sans', 'sans-serif']
        
        # Tạo figure
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Vùng màu theo mức độ tín hiệu
        ax.axhspan(0, -30, alpha=0.2, color='green', label='Cuc manh (vai cm - 1m)')
        ax.axhspan(-30, -70, alpha=0.2, color='yellow', label='Tot - trung binh (2-10m)')
        ax.axhspan(-70, -90, alpha=0.2, color='orange', label='Yeu (10-20m)')
        ax.axhspan(-90, -120, alpha=0.2, color='red', label='Rat yeu (gan mat)')
        
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
        
        # Giới hạn trục Y
        y_min = min(df['cumulative_mean'].min() - 5, -120)
        y_max = max(df['cumulative_mean'].max() + 5, 0)
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
        
        # Text box thống kê với tổng kết
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
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()  # Đóng figure để giải phóng memory
        
        print(f"Da luu chart: {output_file}")
        return True
        
    except Exception as e:
        print(f"Loi tao chart: {e}")
        return False

class ESP32CSIHandler:
    def __init__(self, data_dir="data", log_callback=None):
        self.data_dir = data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        
        self.log_callback = log_callback or print
        self.serial_available = SERIAL_AVAILABLE
        self.serial_connections = {}
        self.csi_packet_count = {}
        self.serial_threads = {}
        self.serial_listening = {}
        
        # Auto scan and connect
        if self.serial_available:
            self.auto_connect()
    
    def start_serial_csi_listener(self, port_name, csi_receiver):
        """Bắt đầu đọc CSI data từ Serial"""
        if port_name not in self.serial_connections:
            return False
        
        ser = self.serial_connections[port_name]
        self.serial_listening[port_name] = True
        
        def serial_listener():
            while self.serial_listening.get(port_name, False):
                try:
                    # Đọc tất cả data có sẵn trong buffer
                    while ser.in_waiting > 0:
                        try:
                            line = ser.readline().decode('utf-8', errors='ignore').strip()
                            if line.startswith('CSI_DATA,'):
                                # Xử lý CSI data từ Serial
                                csi_receiver.process_serial_data(line)
                        except UnicodeDecodeError:
                            # Bỏ qua những dòng có lỗi encoding
                            continue
                    # Sleep rất ngắn để không chiếm 100% CPU
                    time.sleep(0.001)
                except Exception as e:
                    self.log(f"Loi doc {port_name}: {e}")
                    break
        
        thread = threading.Thread(target=serial_listener, daemon=True)
        thread.start()
        self.serial_threads[port_name] = thread
        
        self.log(f"Doc CSI tu: {port_name}")
        return True
        
    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
    
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
                self.log(f"Tim thay {len(esp32_ports)} ESP32, dang ket noi...")
                
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
                        self.csi_packet_count[port.device] = 0
                        
                        self.log(f"Ket noi: {port.device}")
                        
                    except Exception as e:
                        self.log(f"Loi ket noi {port.device}: {e}")
            else:
                self.log("Khong tim thay ESP32")
                
        except Exception as e:
            self.log(f"Loi auto connect: {e}")
    
    def send_command(self, command):
        """Gửi lệnh đến tất cả ESP32"""
        if not self.serial_available or not self.serial_connections:
            self.log("Khong co ESP32 ket noi")
            return False
        
        success_count = 0
        for port_name, ser in self.serial_connections.items():
            try:
                command_bytes = f"{command}\n".encode('utf-8')
                ser.write(command_bytes)
                ser.flush()
                success_count += 1
                self.log(f"Gui lenh '{command}' den {port_name}")
            except Exception as e:
                self.log(f"Loi gui lenh den {port_name}: {e}")
        
        return success_count > 0
    
    def start_listening(self):
        """Gửi lệnh start_listen (1) đến ESP32"""
        return self.send_command("1")
    
    def get_connected_devices(self):
        return list(self.serial_connections.keys())

class CSIReceiver:
    def __init__(self, port=12346):
        self.port = port
        self.running = False
        self.data_dir = CSI_DIR
        self.packet_count = 0
        self.start_time = None
        self.current_csv_file = None
        self.csv_writer = None
        self.csv_file_handle = None
        self.serial_mode = False
        
        create_directories()  # Tạo thư mục khi khởi tạo
        
        self.headers = [
            "timestamp", "id", "mac", "rssi", "rate", "sig_mode", "mcs", 
            "bandwidth", "smoothing", "not_sounding", "aggregation", 
            "stbc", "fec_coding", "sgi", "noise_floor", "ampdu_cnt", 
            "channel", "secondary_channel", "local_timestamp", "ant", 
            "sig_len", "rx_state", "len", "first_word", "data"
        ]
    
    def start_serial_mode(self):
        """Bắt đầu Serial mode - chỉ tạo file CSV"""
        # Hỏi khoảng cách trước khi bắt đầu
        while True:
            try:
                distance = input("Nhap khoang cach (m): ").strip()
                if distance:
                    break
                else:
                    print("Vui long nhap khoang cach!")
            except KeyboardInterrupt:
                print("\nHuy bo...")
                return
        
        self.running = True
        self.serial_mode = True
        self.start_time = time.time()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_csv_file = os.path.join(self.data_dir, f"csi_{distance}m.csv")
        
        print(f"Bat dau nhan CSI data tu Serial")
        print(f"Khoang cach: {distance}m")
        print(f"Thoi gian: {COLLECTION_DURATION}s")
        print(f"File: {self.current_csv_file}")
        print("=" * 40)
        
        # Mở file CSV
        self.csv_file_handle = open(self.current_csv_file, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file_handle)
        self.csv_writer.writerow(self.headers)
        self.csv_file_handle.flush()
    
    def process_serial_data(self, data):
        """Xử lý CSI data từ Serial"""
        if not self.running or not self.serial_mode:
            return
            
        try:
            # data đã là dạng: CSI_DATA,37,c0:5d:89:de:0d:85,-74,11,1,4,0,1,1,1,0,0,0,-97,1,1,2,30198,0,89,0,128,0,[89,16,5,0,...]
            current_time = time.time()
            timestamp = datetime.now().isoformat()
            
            # Bỏ "CSI_DATA," ở đầu và chỉ thêm timestamp
            csv_data = data[9:]  # Bỏ "CSI_DATA,"
            row = [timestamp] + csv_data.split(',')
            
            self.csv_writer.writerow(row)
            
            self.packet_count += 1
                
        except Exception as e:
            print(f"Loi xu ly data: {e}")
        
    def start(self):
        self.running = True
        self.start_time = time.time()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_csv_file = os.path.join(self.data_dir, f"csi_data_{timestamp}.csv")
        
        print(f"Bắt đầu nhận CSI data...")
        print(f"Lưu vào: {self.current_csv_file}")
        print(f"Listening trên UDP port {self.port}")
        print("=" * 50)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("0.0.0.0", self.port))
            sock.settimeout(1.0)
            
            with open(self.current_csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.headers)
                
                while self.running:
                    try:
                        data, addr = sock.recvfrom(4096)
                        self.process_data(data.decode('utf-8').strip(), writer, f)
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"Lỗi nhận data: {e}")
                        
        except Exception as e:
            print(f"Lỗi khởi tạo: {e}")
        finally:
            if 'sock' in locals():
                sock.close()
            print("Đã dừng CSI receiver")
    
    def process_data(self, data, writer, file_handle):
        if not data:
            return
            
        try:
            timestamp = datetime.now().isoformat()
            row = [timestamp] + data.split(',')
            writer.writerow(row)
            file_handle.flush()
            
            self.packet_count += 1
            
            if self.packet_count % 100 == 0:
                elapsed = time.time() - self.start_time
                rate = self.packet_count / elapsed if elapsed > 0 else 0
                print(f"Đã nhận: {self.packet_count} packets | Tốc độ: {rate:.1f} pkt/s")
                
        except Exception as e:
            print(f"Lỗi xử lý data: {e}")
    
    def stop(self):
        self.running = False
        
        # Đóng file CSV nếu đang mở
        if self.csv_file_handle:
            self.csv_file_handle.close()
            self.csv_file_handle = None
            self.csv_writer = None
        
        elapsed = time.time() - self.start_time if self.start_time else 0
        rate = self.packet_count / elapsed if elapsed > 0 else 0
        
        print("\n" + "=" * 40)
        print("TONG KET:")
        print(f"Packets: {self.packet_count}")
        print(f"Duration: {COLLECTION_DURATION}s")
        print(f"Rate: {rate:.1f}/s")
        if hasattr(self, 'current_csv_file') and self.current_csv_file:
            print(f"File: {self.current_csv_file}")
        print("=" * 40)
        
        # Tạo chart tự động
        if self.packet_count > 0:
            print("\nTao chart...")
            self.create_chart_from_data()

    def create_chart_from_data(self):
        """Tạo chart từ dữ liệu vừa thu thập"""
        if not self.current_csv_file or not os.path.exists(self.current_csv_file):
            print("Khong co file CSV de tao chart")
            return False
        
        try:
            # Tạo tên file chart
            base_name = os.path.splitext(os.path.basename(self.current_csv_file))[0]
            chart_file = os.path.join(CHART_DIR, f"{base_name}_chart.png")
            
            print(f"Tao chart tu file: {self.current_csv_file}")
            
            # Đọc dữ liệu và tạo chart
            df = load_csi_data_for_chart(self.current_csv_file)
            if df is not None:
                success = create_chart(df, chart_file)
                if success:
                    print(f"Chart da luu: {chart_file}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Loi tao chart: {e}")
            return False

class ESP32CSIController:
    def __init__(self):
        self.data_dir = DATA_DIR
        create_directories()  # Tạo thư mục
        self.esp32_handler = ESP32CSIHandler(CSI_DIR, log_callback=self.log_message)
        self.csi_receiver = CSIReceiver()
        self.running = True
        
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def log_message(self, msg):
        print(f"[ESP32] {msg}")

    def signal_handler(self, sig, frame):
        print("\nDang tat he thong...")
        self.running = False
        if self.csi_receiver.running:
            print("Dang tao chart...")
            self.csi_receiver.stop()  # stop() đã tích hợp tạo chart
        sys.exit(0)
    
    def show_menu(self):
        print("\nCommands:")
        print("  1. serial_mode - Thu thap CSI data")
        print("  0. exit - Thoat")
        
        # Show current status
        devices = self.esp32_handler.get_connected_devices()
        print(f"ESP32: {len(devices)} devices | CSI: {'Running' if self.csi_receiver.running else 'Stopped'}")
        if self.csi_receiver.running and self.csi_receiver.start_time:
            elapsed = time.time() - self.csi_receiver.start_time
            rate = self.csi_receiver.packet_count / elapsed if elapsed > 0 else 0
            print(f"Packets: {self.csi_receiver.packet_count} ({rate:.1f} pkt/s)")

    def start_serial_mode(self):
        """Chế độ Serial - không cần WiFi"""
        print(f"Serial mode - Thu thap trong {COLLECTION_DURATION}s")
        print(f"File format: csi_{{distance}}m.csv")
        
        # 1. Bật Serial data mode trên ESP32
        esp32_success = self.esp32_handler.send_command("6")  
        if esp32_success:
            print("ESP32 serial data mode: ON")
        else:
            print("ESP32 serial data mode: FAILED")

        # 2. Bắt đầu ESP32 listening
        self.esp32_handler.start_listening()
        
        # 3. Bắt đầu CSI receiver (Serial mode)
        if self.csi_receiver.running:
            print("CSI receiver: Already running")
        else:
            self.csi_receiver.start_serial_mode()
            
            # Bắt đầu đọc từ tất cả ESP32
            devices = self.esp32_handler.get_connected_devices()
            for device in devices:
                self.esp32_handler.start_serial_csi_listener(device, self.csi_receiver)
            
            print("CSI receiver: Started")

    def run(self):
        print("ESP32 CSI Controller")
        print(f"Data dir: {os.path.abspath(self.data_dir)}")
        print(f"CSI files: {os.path.abspath(CSI_DIR)}")
        print(f"Chart files: {os.path.abspath(CHART_DIR)}")
        
        if not SERIAL_AVAILABLE:
            print("Warning: pyserial not installed")
        
        while self.running:
            try:
                self.show_menu()
                choice = input("\nChon lenh: ").strip()
                
                if choice == '1':
                    self.start_serial_mode()
                elif choice == '0' or choice.lower() == 'exit':
                    break
                else:
                    print("Lenh khong hop le. Chon 1 hoac 0")
                
                input("\nNhan Enter de tiep tuc...")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Loi: {e}")
        
        print("\nDa thoat ESP32 CSI Controller")

def main():
    controller = ESP32CSIController()
    controller.run()

if __name__ == "__main__":
    main()
