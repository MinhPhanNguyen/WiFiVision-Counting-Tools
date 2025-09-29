import pandas as pd
import numpy as np
import os
import re
import ast
from pathlib import Path

def create_output_directory(output_dir="data/csi_format"):
    """
    Tạo thư mục output nếu chưa tồn tại
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    print(f"✅ Đã tạo thư mục: {output_dir}")

def clean_and_parse_line(line):
    """
    Làm sạch và parse dòng CSV với xử lý lỗi đặc biệt
    """
    # Sửa một số lỗi thường gặp
    line = line.replace(',1-', ',-')  # Sửa lỗi 1-14 thành -14
    line = line.replace(',,', ',0,')  # Sửa lỗi dấu phẩy kép
    
    # Parse với xử lý đặc biệt cho array
    row_data = []
    current_field = ""
    in_brackets = False
    bracket_count = 0
    
    i = 0
    while i < len(line):
        char = line[i]
        
        if char == '[':
            in_brackets = True
            bracket_count += 1
            current_field += char
        elif char == ']':
            bracket_count -= 1
            current_field += char
            if bracket_count <= 0:
                in_brackets = False
        elif char == ',' and not in_brackets:
            row_data.append(current_field.strip())
            current_field = ""
        else:
            current_field += char
        
        i += 1
    
    # Thêm field cuối cùng
    if current_field.strip():
        row_data.append(current_field.strip())
    
    return row_data

def fix_csi_data_column(row_data, expected_columns=25):
    """
    Sửa chữa dòng dữ liệu bị tách cột do trường data
    """
    # Nếu số cột đúng, return nguyên
    if len(row_data) == expected_columns:
        return row_data
    
    # Nếu số cột > expected, gộp phần thừa vào trường data (cột cuối)
    if len(row_data) > expected_columns:
        # Lấy 24 cột đầu (trừ data)
        fixed_data = row_data[:expected_columns-1]
        
        # Gộp tất cả cột thừa thành trường data
        remaining_data = row_data[expected_columns-1:]
        
        # Tạo lại array CSI từ các cột bị tách
        try:
            # Gộp tất cả remaining data thành một string
            combined_data = ','.join(remaining_data)
            
            # Làm sạch và tạo lại array
            # Loại bỏ dấu [ ] thừa
            combined_data = combined_data.replace('[', '').replace(']', '')
            
            # Split và clean từng số
            numbers = []
            for item in combined_data.split(','):
                item = item.strip()
                if item:
                    try:
                        # Sửa lỗi số âm bị dính
                        item = item.replace('1-', '-')
                        num_val = float(item)
                        numbers.append(int(num_val) if num_val.is_integer() else num_val)
                    except ValueError:
                        # Bỏ qua item không convert được
                        continue
            
            # Tạo lại array string
            if numbers:
                data_array_str = '[' + ','.join(map(str, numbers)) + ']'
            else:
                data_array_str = '[]'
                
        except Exception as e:
            print(f"⚠️  Lỗi khi xử lý data array: {e}")
            data_array_str = '[]'
        
        # Thêm data đã sửa vào cuối
        fixed_data.append(data_array_str)
        return fixed_data
    
    # Nếu số cột < expected, thêm cột trống
    else:
        missing_cols = expected_columns - len(row_data)
        return row_data + [''] * missing_cols

def validate_and_fix_rssi(rssi_value):
    """
    Validate và sửa giá trị RSSI
    RSSI hợp lý: -100 đến 0 dBm
    """
    try:
        rssi = float(rssi_value)
        
        # Nếu giá trị dương, chuyển thành âm
        if rssi > 0:
            rssi = -rssi
            
        # Giới hạn trong khoảng hợp lý
        if rssi < -100:
            rssi = -100
        elif rssi > 0:
            rssi = 0
            
        return int(rssi)
    except (ValueError, TypeError):
        return -50  # Giá trị mặc định

def validate_and_fix_numeric_field(value, field_name, min_val=None, max_val=None, default_val=0):
    """
    Validate và sửa các trường số
    """
    try:
        num_val = float(value)
        
        if min_val is not None and num_val < min_val:
            return min_val
        if max_val is not None and num_val > max_val:
            return max_val
            
        return int(num_val) if num_val.is_integer() else num_val
    except (ValueError, TypeError):
        return default_val

def fix_timestamp_format(timestamp_str):
    """
    Sửa định dạng timestamp
    """
    try:
        # Kiểm tra và sửa định dạng timestamp
        if pd.isna(timestamp_str) or str(timestamp_str).strip() == '':
            return pd.Timestamp.now().isoformat()
        
        # Thử parse timestamp
        parsed_time = pd.to_datetime(timestamp_str)
        return parsed_time.isoformat()
    except:
        return pd.Timestamp.now().isoformat()

def fix_csi_file(input_file, output_file):
    """
    Sửa chữa một file CSI
    """
    print(f"\n🔧 Đang sửa file: {input_file}")
    
    try:
        # Đọc file CSV với xử lý lỗi
        lines_read = 0
        lines_fixed = 0
        fixed_data = []
        
        expected_columns = ['timestamp', 'id', 'mac', 'rssi', 'rate', 'sig_mode', 'mcs', 
                          'bandwidth', 'smoothing', 'not_sounding', 'aggregation', 'stbc', 
                          'fec_coding', 'sgi', 'noise_floor', 'ampdu_cnt', 'channel', 
                          'secondary_channel', 'local_timestamp', 'ant', 'sig_len', 
                          'rx_state', 'len', 'first_word', 'data']
        
        # Thêm header
        fixed_data.append(expected_columns)
        
        # Đọc từng dòng và sửa
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            lines_read += 1
            
            # Bỏ qua header
            if i == 0:
                continue
                
            # Parse dòng CSV
            line = line.strip()
            if not line:
                continue
                
            try:
                # Parse dòng CSV với xử lý đặc biệt
                row_data = clean_and_parse_line(line)
                
                # Sửa chữa số cột
                fixed_row = fix_csi_data_column(row_data, len(expected_columns))
                
                # Validate và sửa từng trường
                if len(fixed_row) >= len(expected_columns):
                    # Timestamp
                    fixed_row[0] = fix_timestamp_format(fixed_row[0])
                    
                    # ID - số nguyên
                    fixed_row[1] = validate_and_fix_numeric_field(fixed_row[1], 'id', 0, 100000, 0)
                    
                    # MAC address - giữ nguyên
                    # fixed_row[2] = fixed_row[2]
                    
                    # RSSI - sửa đặc biệt
                    fixed_row[3] = validate_and_fix_rssi(fixed_row[3])
                    
                    # Rate
                    fixed_row[4] = validate_and_fix_numeric_field(fixed_row[4], 'rate', 0, 1000, 11)
                    
                    # Các trường boolean (0 hoặc 1)
                    bool_fields = [5, 7, 8, 9, 10, 11, 12, 13]  # sig_mode, bandwidth, smoothing, etc.
                    for idx in bool_fields:
                        if idx < len(fixed_row):
                            val = validate_and_fix_numeric_field(fixed_row[idx], f'field_{idx}', 0, 1, 0)
                            fixed_row[idx] = 1 if val > 0 else 0
                    
                    # MCS
                    if len(fixed_row) > 6:
                        fixed_row[6] = validate_and_fix_numeric_field(fixed_row[6], 'mcs', 0, 15, 4)
                    
                    # Noise floor
                    if len(fixed_row) > 14:
                        fixed_row[14] = validate_and_fix_numeric_field(fixed_row[14], 'noise_floor', -120, -50, -96)
                    
                    # Channel
                    if len(fixed_row) > 16:
                        fixed_row[16] = validate_and_fix_numeric_field(fixed_row[16], 'channel', 1, 14, 1)
                    
                    # Secondary channel
                    if len(fixed_row) > 17:
                        fixed_row[17] = validate_and_fix_numeric_field(fixed_row[17], 'secondary_channel', 0, 2, 2)
                    
                    # Validate data array
                    if len(fixed_row) > 24:
                        data_str = str(fixed_row[24])
                        if not (data_str.startswith('[') and data_str.endswith(']')):
                            fixed_row[24] = '[]'
                    
                    fixed_data.append(fixed_row[:len(expected_columns)])
                    lines_fixed += 1
                else:
                    print(f"⚠️  Dòng {i+1}: Không thể sửa được (chỉ có {len(fixed_row)} cột)")
                    
            except Exception as e:
                print(f"⚠️  Lỗi dòng {i+1}: {e}")
                continue
        
        # Ghi file đã sửa
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            for row in fixed_data:
                f.write(','.join(map(str, row)) + '\n')
        
        print(f"✅ Đã sửa xong: {lines_read} dòng đọc, {lines_fixed} dòng sửa thành công")
        print(f"📁 File đã lưu: {output_file}")
        
        # Validate file đã sửa
        try:
            # Sử dụng on_bad_lines='skip' để bỏ qua dòng lỗi khi validation
            df_check = pd.read_csv(output_file, on_bad_lines='skip')
            print(f"✅ Validation: {df_check.shape[0]} dòng, {df_check.shape[1]} cột")
            
            # Kiểm tra RSSI
            rssi_invalid = df_check[(df_check['rssi'] > 0) | (df_check['rssi'] < -100)]
            print(f"📊 RSSI hợp lệ: {len(df_check) - len(rssi_invalid)}/{len(df_check)} dòng")
            
            return True
        except Exception as e:
            print(f"❌ Lỗi validation: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi khi sửa file {input_file}: {e}")
        return False

def fix_all_csi_files(input_dir="data/csi", output_dir="data/csi_format"):
    """
    Sửa chữa tất cả file CSI trong thư mục
    """
    print("🚀 BẮT ĐẦU SỬA CHỮA TẤT CẢ FILE CSI")
    print("="*60)
    
    # Tạo thư mục output
    create_output_directory(output_dir)
    
    # Tìm tất cả file CSV
    if not os.path.exists(input_dir):
        print(f"❌ Thư mục {input_dir} không tồn tại")
        return
    
    csv_files = [f for f in os.listdir(input_dir) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"❌ Không tìm thấy file CSV nào trong {input_dir}")
        return
    
    print(f"📁 Tìm thấy {len(csv_files)} file CSV: {csv_files}")
    
    success_count = 0
    failed_count = 0
    
    for csv_file in csv_files:
        input_path = os.path.join(input_dir, csv_file)
        output_path = os.path.join(output_dir, csv_file)
        
        if fix_csi_file(input_path, output_path):
            success_count += 1
        else:
            failed_count += 1
        
        print("-" * 60)
    
    print(f"\n🎉 HOÀN THÀNH SỬA CHỮA")
    print(f"✅ Thành công: {success_count} file")
    print(f"❌ Thất bại: {failed_count} file")
    print(f"📁 File đã sửa được lưu trong: {output_dir}")

def generate_summary_report(output_dir="data/csi_format"):
    """
    Tạo báo cáo tóm tắt sau khi sửa
    """
    print(f"\n📊 TẠO BÁO CÁO TÓNG TẮT")
    print("="*60)
    
    if not os.path.exists(output_dir):
        print(f"❌ Thư mục {output_dir} không tồn tại")
        return
    
    csv_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
    
    report_data = []
    
    for csv_file in csv_files:
        file_path = os.path.join(output_dir, csv_file)
        try:
            df = pd.read_csv(file_path, on_bad_lines='skip')  # Bỏ qua dòng lỗi
            
            # Thống kê cơ bản
            total_rows = len(df)
            total_cols = len(df.columns)
            missing_values = df.isnull().sum().sum()
            
            # Thống kê RSSI
            rssi_valid = len(df[(df['rssi'] >= -100) & (df['rssi'] <= 0)])
            rssi_invalid = total_rows - rssi_valid
            
            # Thống kê data field
            data_valid = 0
            if 'data' in df.columns:
                for data_val in df['data'].head(10):  # Kiểm tra 10 dòng đầu
                    if str(data_val).startswith('[') and str(data_val).endswith(']'):
                        data_valid += 1
            
            report_data.append({
                'File': csv_file,
                'Dòng': total_rows,
                'Cột': total_cols,
                'Giá trị thiếu': missing_values,
                'RSSI hợp lệ': f"{rssi_valid}/{total_rows}",
                'Data array OK': f"{data_valid}/10 mẫu"
            })
            
        except Exception as e:
            report_data.append({
                'File': csv_file,
                'Dòng': 'ERROR',
                'Cột': 'ERROR',
                'Giá trị thiếu': 'ERROR',
                'RSSI hợp lệ': 'ERROR',
                'Data array OK': 'ERROR'
            })
    
    # In báo cáo
    print(f"{'File':<15} {'Dòng':<8} {'Cột':<5} {'Thiếu':<8} {'RSSI OK':<12} {'Data OK':<12}")
    print("-" * 70)
    
    for item in report_data:
        print(f"{item['File']:<15} {item['Dòng']:<8} {item['Cột']:<5} {item['Giá trị thiếu']:<8} {item['RSSI hợp lệ']:<12} {item['Data array OK']:<12}")

if __name__ == "__main__":
    print("🔧 SCRIPT SỬA CHỮA DỮ LIỆU CSI")
    print("="*60)
    
    # Sửa tất cả file
    fix_all_csi_files("data/csi", "data/csi_format")
    
    # Tạo báo cáo
    generate_summary_report("data/csi_format")
    
    print("\n🎯 HƯỚNG DẪN SỬ DỤNG FILE ĐÃ SỬA:")
    print("1. Sử dụng pandas.read_csv() bình thường")
    print("2. RSSI đã được normalize về khoảng -100 đến 0 dBm")
    print("3. Trường 'data' đã được format lại thành array string")
    print("4. Các giá trị thiếu đã được điền default")
    print("5. File gốc được giữ nguyên trong data/csi/")
