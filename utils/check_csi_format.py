import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

def check_csi_data(file_path):
    """
    Kiểm tra tính chính xác và phát hiện lỗi trong dữ liệu CSI
    """
    print(f"=== KIỂM TRA FILE: {file_path} ===")
    
    try:
        # Đọc file CSV với xử lý lỗi
        try:
            df = pd.read_csv(file_path)
        except pd.errors.ParserError as e:
            print(f"❌ Lỗi parser: {e}")
            # Thử đọc với on_bad_lines='skip'
            print("🔄 Thử đọc với skip bad lines...")
            df = pd.read_csv(file_path, on_bad_lines='skip')
            print("✅ Đã đọc file thành công với một số dòng bị bỏ qua")
        
        # 1. KIỂM TRA THÔNG TIN CƠ BẢN
        print("\n=== THÔNG TIN CƠ BẢN ===")
        print(f"📊 Kích thước dữ liệu: {df.shape[0]} dòng, {df.shape[1]} cột")
        print(f"📋 Tên các cột: {list(df.columns)}")
        
        # 2. KIỂM TRA HEADER
        print("\n=== KIỂM TRA HEADER ===")
        expected_columns = ['timestamp', 'id', 'mac', 'rssi', 'rate', 'sig_mode', 'mcs', 
                          'bandwidth', 'smoothing', 'not_sounding', 'aggregation', 'stbc', 
                          'fec_coding', 'sgi', 'noise_floor', 'ampdu_cnt', 'channel', 
                          'secondary_channel', 'local_timestamp', 'ant', 'sig_len', 
                          'rx_state', 'len', 'first_word', 'data']
        
        missing_cols = set(expected_columns) - set(df.columns)
        extra_cols = set(df.columns) - set(expected_columns)
        
        if missing_cols:
            print(f"⚠️  Thiếu cột: {list(missing_cols)}")
        if extra_cols:
            print(f"➕ Cột thêm: {list(extra_cols)}")
        if not missing_cols and not extra_cols:
            print("✅ Header đúng chuẩn")
        
        # 3. KIỂM TRA GIÁ TRỊ THIẾU
        print("\n=== KIỂM TRA GIÁ TRỊ THIẾU ===")
        missing_data = df.isnull().sum()
        total_missing = missing_data.sum()
        if total_missing > 0:
            print(f"❌ Tổng số giá trị thiếu: {total_missing}")
            for col, count in missing_data[missing_data > 0].items():
                percentage = (count / len(df)) * 100
                print(f"   - {col}: {count} giá trị ({percentage:.2f}%)")
        else:
            print("✅ Không có giá trị thiếu")
        
        # 4. KIỂM TRA DỮ LIỆU TRÙNG LẶP
        print("\n=== KIỂM TRA DỮ LIỆU TRÙNG LẶP ===")
        duplicates = df.duplicated().sum()
        if duplicates > 0:
            print(f"⚠️  Có {duplicates} dòng trùng lặp ({duplicates/len(df)*100:.2f}%)")
        else:
            print("✅ Không có dữ liệu trùng lặp")
        
        # 5. KIỂM TRA TÍNH NHẤT QUÁN CỦA SỐ CỘT
        print("\n=== KIỂM TRA TÍNH NHẤT QUÁN ===")
        expected_cols_count = len(expected_columns)
        actual_rows_cols = []
        
        # Đọc file để kiểm tra số cột từng dòng
        with open(file_path, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines[:100]):  # Kiểm tra 100 dòng đầu
                cols_count = len(line.strip().split(','))
                if i == 0:  # Header
                    header_cols = cols_count
                else:
                    if cols_count != header_cols:
                        actual_rows_cols.append((i+1, cols_count))
        
        if actual_rows_cols:
            print(f"⚠️  Phát hiện {len(actual_rows_cols)} dòng có số cột không khớp:")
            for row_num, col_count in actual_rows_cols[:10]:  # Hiển thị 10 dòng đầu
                print(f"   - Dòng {row_num}: {col_count} cột (mong đợi {header_cols})")
        else:
            print("✅ Tất cả dòng có số cột nhất quán")
        
        # 6. KIỂM TRA GIÁ TRỊ RSSI
        if 'rssi' in df.columns:
            print("\n=== KIỂM TRA GIÁ TRỊ RSSI ===")
            rssi_values = df['rssi']
            valid_rssi = rssi_values[(rssi_values >= -100) & (rssi_values <= 0)]
            invalid_rssi = len(rssi_values) - len(valid_rssi)
            
            if invalid_rssi > 0:
                print(f"⚠️  {invalid_rssi} giá trị RSSI không hợp lý (ngoài khoảng -100 đến 0 dBm)")
                print(f"   - Min: {rssi_values.min()}, Max: {rssi_values.max()}")
            else:
                print("✅ Tất cả giá trị RSSI hợp lý")
        
        # 7. KIỂM TRA TIMESTAMP
        if 'timestamp' in df.columns:
            print("\n=== KIỂM TRA TIMESTAMP ===")
            try:
                df['timestamp_parsed'] = pd.to_datetime(df['timestamp'])
                print("✅ Timestamp có định dạng hợp lệ")
                
                # Kiểm tra tính liên tục
                time_diff = df['timestamp_parsed'].diff().dropna()
                if len(time_diff) > 0:
                    avg_interval = time_diff.mean()
                    print(f"📊 Khoảng thời gian trung bình giữa các mẫu: {avg_interval}")
                    
                    # Tìm khoảng cách bất thường
                    outlier_threshold = avg_interval * 10
                    large_gaps = time_diff[time_diff > outlier_threshold]
                    if len(large_gaps) > 0:
                        print(f"⚠️  Phát hiện {len(large_gaps)} khoảng cách thời gian bất thường")
                    
            except Exception as e:
                print(f"❌ Lỗi khi parse timestamp: {e}")
        
        # 8. KIỂM TRA TRƯỜNG DATA
        if 'data' in df.columns:
            print("\n=== KIỂM TRA TRƯỜNG DATA ===")
            data_sample = df['data'].iloc[0] if len(df) > 0 else None
            if data_sample:
                print(f"📋 Mẫu dữ liệu CSI đầu tiên: {str(data_sample)[:100]}...")
                
                # Kiểm tra định dạng array
                if str(data_sample).startswith('[') and str(data_sample).endswith(']'):
                    print("✅ Dữ liệu CSI có định dạng array")
                    try:
                        import ast
                        parsed_data = ast.literal_eval(str(data_sample))
                        print(f"📊 Số phần tử trong CSI array: {len(parsed_data)}")
                    except:
                        print("⚠️  Không thể parse CSI array")
                else:
                    print("⚠️  Dữ liệu CSI không có định dạng array chuẩn")
        
        # 9. THỐNG KÊ MÔ TẢ
        print("\n=== THỐNG KÊ MÔ TẢ CÁC CỘT SỐ ===")
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            print(df[numeric_cols].describe())
        
        # 10. PHÁT HIỆN OUTLIERS
        print("\n=== PHÁT HIỆN OUTLIERS ===")
        for col in numeric_cols[:5]:  # Kiểm tra 5 cột đầu tiên
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
            
            if len(outliers) > 0:
                print(f"⚠️  {col}: {len(outliers)} outliers ({len(outliers)/len(df)*100:.2f}%)")
            else:
                print(f"✅ {col}: Không có outliers")
        
        print(f"\n=== TỔNG KẾT KIỂM TRA FILE {os.path.basename(file_path)} ===")
        issues = []
        if total_missing > 0:
            issues.append("Có giá trị thiếu")
        if duplicates > 0:
            issues.append("Có dữ liệu trùng lặp")
        if actual_rows_cols:
            issues.append("Số cột không nhất quán")
        if missing_cols or extra_cols:
            issues.append("Header không chuẩn")
        
        if issues:
            print(f"⚠️  Phát hiện {len(issues)} vấn đề: {', '.join(issues)}")
        else:
            print("✅ Dữ liệu có vẻ ổn định!")
            
        return df
        
    except Exception as e:
        print(f"❌ Lỗi khi kiểm tra file: {e}")
        return None

def check_all_csi_files(data_dir="data/csi"):
    """
    Kiểm tra tất cả file CSI trong thư mục
    """
    print("=== KIỂM TRA TẤT CẢ FILE CSI ===\n")
    
    if not os.path.exists(data_dir):
        print(f"❌ Thư mục {data_dir} không tồn tại")
        return
    
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"❌ Không tìm thấy file CSV nào trong {data_dir}")
        return
    
    print(f"📁 Tìm thấy {len(csv_files)} file CSV: {csv_files}\n")
    
    for csv_file in csv_files:
        file_path = os.path.join(data_dir, csv_file)
        df = check_csi_data(file_path)
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    # Kiểm tra file cụ thể
    file_path = "data/csi_format/csi_0m.csv"
    if os.path.exists(file_path):
        check_csi_data(file_path)
    else:
        print(f"❌ File {file_path} không tồn tại")
        
    print("\n" + "="*80)
    
    # Kiểm tra tất cả file trong thư mục
    check_all_csi_files("data/csi_format")