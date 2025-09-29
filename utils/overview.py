"""
CSI Overview Chart Generator
Tạo biểu đồ tổng quan RSSI theo khoảng cách từ tất cả file trong data/csi/
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import csv
import os
from datetime import datetime

def load_csi_data_for_overview(file_path):
    """Đọc dữ liệu CSI từ CSV để tính RSSI trung bình"""
    try:
        data_rows = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Skip header
            
            for row_num, row in enumerate(reader):
                try:
                    if len(row) >= 4:
                        rssi = float(row[3])  # RSSI ở cột thứ 4
                        data_rows.append(rssi)
                except (ValueError, IndexError):
                    continue
        
        if not data_rows:
            return None
        
        return data_rows
        
    except Exception as e:
        print(f"Loi doc file {file_path}: {e}")
        return None

def create_overview_chart():
    """Tạo overview chart từ tất cả file CSI"""
    try:
        csi_dir = "data/csi"
        chart_dir = "data/chart"
        os.makedirs(chart_dir, exist_ok=True)
        if not os.path.exists(csi_dir):
            print("Khong tim thay thu muc data/csi")
            return False
        csv_files = [f for f in os.listdir(csi_dir) if f.endswith('.csv')]
        if not csv_files:
            print("Khong co file CSV nao")
            return False
        print(f"Tim thay {len(csv_files)} file CSV")

        # Nối tất cả giá trị RSSI từ các file, gán đúng khoảng cách và gom theo từng vùng
        color_map = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'cyan', 'magenta', 'olive', 'pink', 'gray']
        distance_to_color = {}
        all_points = {}  # {distance: [rssi, ...]}
        for idx, csv_file in enumerate(csv_files):
            try:
                distance_str = csv_file.replace('csi_', '').replace('m.csv', '')
                distance = float(distance_str)
            except:
                print(f"Khong the trich xuat khoang cach tu file: {csv_file}")
                continue
            file_path = os.path.join(csi_dir, csv_file)
            rssi_values = load_csi_data_for_overview(file_path)
            if rssi_values is not None and len(rssi_values) > 0:
                all_points[distance] = rssi_values
                # Gán màu cho từng vùng (lặp lại nếu số vùng > số màu)
                distance_to_color[distance] = color_map[idx % len(color_map)]
                print(f"File {csv_file}: {distance}m, {len(rssi_values)} packets")

        if not all_points:
            print("Khong co du lieu hop le tu cac file CSV")
            return False

        # Vẽ scatter plot từng vùng với màu riêng theo dạng timeline
        plt.rcParams['font.family'] = ['Arial Unicode MS', 'DejaVu Sans', 'sans-serif']
        fig, ax = plt.subplots(figsize=(20, 12))  # Tăng kích thước biểu đồ
        
        # Tính min/max từ dữ liệu thực tế
        all_rssi_temp = []
        for rssi_list in all_points.values():
            all_rssi_temp.extend(rssi_list)
        
        if all_rssi_temp:
            data_min = min(all_rssi_temp)
            data_max = max(all_rssi_temp)
            data_range = data_max - data_min
            
            # Tạo vùng màu dựa trên dữ liệu thực tế (chia thành 4 vùng)
            zone1 = data_max - data_range * 0.25  # Vùng tốt nhất (25% trên)
            zone2 = data_max - data_range * 0.50  # Vùng tốt (25-50%)
            zone3 = data_max - data_range * 0.75  # Vùng trung bình (50-75%)
            # Vùng yếu nhất: từ zone3 đến data_min
            
            ax.axhspan(data_max, zone1, alpha=0.15, color='green', label=f'Tot nhat ({zone1:.1f} den {data_max:.1f} dBm)')
            ax.axhspan(zone1, zone2, alpha=0.15, color='yellow', label=f'Tot ({zone2:.1f} den {zone1:.1f} dBm)')
            ax.axhspan(zone2, zone3, alpha=0.15, color='orange', label=f'Trung binh ({zone3:.1f} den {zone2:.1f} dBm)')
            ax.axhspan(zone3, data_min, alpha=0.15, color='red', label=f'Yeu ({data_min:.1f} den {zone3:.1f} dBm)')

        all_distances = []
        all_rssi = []
        sorted_distances = sorted(all_points.keys())
        current_x_offset = 0
        
        for i, distance in enumerate(sorted_distances):
            rssi_list = all_points[distance]
            color = distance_to_color[distance]
            
            # Tạo x positions liên tục cho mỗi packet (giống như timeline)
            x_positions = np.arange(current_x_offset, current_x_offset + len(rssi_list))
            
            # Vẽ line plot cho mỗi file (giống như biểu đồ individual)
            ax.plot(x_positions, rssi_list, color=color, alpha=0.7, linewidth=1, 
                   label=f'{distance:.0f}m ({len(rssi_list)} packets)')
            ax.scatter(x_positions, rssi_list, color=color, alpha=0.6, s=3)
            
            # Thêm đường phân cách giữa các file
            if i < len(sorted_distances) - 1:
                ax.axvline(x=current_x_offset + len(rssi_list), color='gray', alpha=0.3, linestyle='--')
            
            current_x_offset += len(rssi_list) + 50  # Khoảng cách giữa các file
            all_distances.extend([distance]*len(rssi_list))
            all_rssi.extend(rssi_list)

        # Đảm bảo legend không bị trùng
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize=10, framealpha=0.9)

        ax.set_xlabel('Packet Timeline (theo thu tu cac file)', fontsize=14, fontweight='bold')
        ax.set_ylabel('RSSI (dBm)', fontsize=14, fontweight='bold')
        ax.set_title('CSI Overview - Tat ca gia tri RSSI theo timeline\n(Hien thi ro rang tung file, tong hop tu data/csi)', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3, linestyle='--')

        # Giới hạn trục với padding dựa trên dữ liệu thực tế
        if all_rssi:
            data_min = min(all_rssi)
            data_max = max(all_rssi)
            padding = (data_max - data_min) * 0.05  # 5% padding
            y_min = data_min - padding
            y_max = data_max + padding
            ax.set_ylim(y_min, y_max)
        
        # X axis sẽ hiển thị timeline thay vì khoảng cách
        ax.set_xlim(-50, current_x_offset)

        # Thống kê tổng quan
        total_files = len(csv_files)
        total_packets = sum(len(v) for v in all_points.values())
        min_distance = min(all_distances) if all_distances else 0
        max_distance = max(all_distances) if all_distances else 0
        min_rssi = min(all_rssi) if all_rssi else 0
        max_rssi = max(all_rssi) if all_rssi else 0

        stats_text = f'Tong quan:\n' \
                    f'• So file: {total_files}\n' \
                    f'• Tong packets: {total_packets:,}\n' \
                    f'• Khoang cach: {min_distance}m - {max_distance}m\n' \
                    f'• RSSI range: {min_rssi:.1f} den {max_rssi:.1f} dBm'
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                fontsize=11, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.9))
        plt.tight_layout()

        # Lưu file với timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        overview_file = os.path.join(chart_dir, f'overview_rssi_distance_{timestamp}.png')
        plt.savefig(overview_file, dpi=300, bbox_inches='tight')
        # Cũng lưu bản không có timestamp (để dễ tìm)
        overview_latest = os.path.join(chart_dir, 'overview_rssi_distance_latest.png')
        plt.savefig(overview_latest, dpi=300, bbox_inches='tight')
        plt.show()
        plt.close()
        print(f"\nDa luu overview chart:")
        print(f"• {overview_file}")
        print(f"• {overview_latest}")
        return True
    except Exception as e:
        print(f"Loi tao overview chart: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Hàm chính"""
    print("=" * 60)
    print("CSI OVERVIEW CHART GENERATOR")
    print("=" * 60)
    print("Tao bieu do tong quan RSSI theo khoang cach")
    print("Tu tat ca file trong data/csi/")
    print("-" * 60)
    
    success = create_overview_chart()
    
    if success:
        print("\nHoan thanh! Kiem tra file chart trong data/chart/")
    else:
        print("\nCo loi xay ra!")

if __name__ == "__main__":
    main()
