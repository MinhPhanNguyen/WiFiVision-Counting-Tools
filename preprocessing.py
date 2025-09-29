import pandas as pd
import os
import re
import ast
from datetime import datetime
import glob
import numpy as np
import shutil
import random

def extract_timestamp_from_image_filename(filename):
    """
    Trích xuất timestamp từ tên file image
    Format: frame_20250912_113933_706.jpg -> timestamp in milliseconds
    """
    pattern = r'frame_(\d{8})_(\d{6})_(\d+)\.jpg'
    match = re.match(pattern, filename)
    if match:
        date_str, time_str, ms_str = match.groups()
        # Tạo datetime object từ date và time
        datetime_str = f"{date_str} {time_str}"
        dt = datetime.strptime(datetime_str, "%Y%m%d %H%M%S")
        
        # Chuyển thành t        return combined_df, balanced_df, data_folder, balanced_folder
        timestamp_ms = int(dt.timestamp() * 1000) + int(ms_str)
        return timestamp_ms
    return None

def parse_csi_timestamp(timestamp_str):
    """
    Chuyển đổi timestamp CSI từ string sang milliseconds
    Format: 2025-09-12T11:39:33.691970
    """
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('T', ' '))
        return int(dt.timestamp() * 1000)
    except:
        return None

def process_csi_data(data_str):
    """
    Xử lý chuỗi CSI data:
    1. Chuyển từ string về list
    2. Bỏ 4 giá trị đầu [91,48,5,0]
    3. Loại bỏ các dải số 0 liền kề (padding)
    4. Chuyển về string format cuối cùng
    """
    try:
        # Parse chuỗi data thành list
        if isinstance(data_str, str) and data_str.startswith('[') and data_str.endswith(']'):
            data_list = ast.literal_eval(data_str)
        else:
            return ""
        
        # Bỏ 4 giá trị đầu tiên [91,48,5,0]
        if len(data_list) >= 4:
            data_list = data_list[4:]
        
        # Loại bỏ các dải số 0 liền kề
        cleaned_data = remove_consecutive_zeros(data_list)
        
        # Chuyển về string
        return str(cleaned_data)
    except Exception as e:
        print(f"Lỗi xử lý CSI data: {e}")
        return ""

def remove_consecutive_zeros(data_list, min_consecutive=5):
    """
    Loại bỏ các dải số 0 liền kề (từ min_consecutive số 0 trở lên)
    """
    if not data_list:
        return data_list
    
    result = []
    zero_count = 0
    temp_zeros = []
    
    for value in data_list:
        if value == 0:
            zero_count += 1
            temp_zeros.append(value)
        else:
            # Nếu có ít hơn min_consecutive số 0, giữ lại
            if zero_count > 0 and zero_count < min_consecutive:
                result.extend(temp_zeros)
            # Reset counter
            zero_count = 0
            temp_zeros = []
            result.append(value)
    
    # Xử lý dải 0 cuối cùng
    if zero_count > 0 and zero_count < min_consecutive:
        result.extend(temp_zeros)
    
    return result

def normalize_subcarrier_length(csi_data_list, target_length=None):
    """
    Chuẩn hóa độ dài subcarriers cho tất cả CSI data
    """
    if not csi_data_list:
        return csi_data_list, 0
    
    # Tìm độ dài phổ biến nhất
    lengths = []
    for data_str in csi_data_list:
        try:
            if data_str and data_str != "":
                data_list = ast.literal_eval(data_str)
                lengths.append(len(data_list))
        except:
            continue
    
    if not lengths:
        return csi_data_list, 0
    
    # Tìm độ dài xuất hiện nhiều nhất
    if target_length is None:
        from collections import Counter
        length_counts = Counter(lengths)
        target_length = length_counts.most_common(1)[0][0]
    
    print(f"Chuẩn hóa subcarriers về độ dài: {target_length}")
    
    # Chuẩn hóa tất cả về cùng độ dài
    normalized_data = []
    for data_str in csi_data_list:
        try:
            if data_str and data_str != "":
                data_list = ast.literal_eval(data_str)
                
                if len(data_list) > target_length:
                    # Cắt bớt nếu dài hơn
                    data_list = data_list[:target_length]
                elif len(data_list) < target_length:
                    # Pad với 0 nếu ngắn hơn
                    data_list.extend([0] * (target_length - len(data_list)))
                
                normalized_data.append(str(data_list))
            else:
                # Tạo data rỗng với độ dài chuẩn
                normalized_data.append(str([0] * target_length))
        except:
            # Tạo data rỗng với độ dài chuẩn nếu có lỗi
            normalized_data.append(str([0] * target_length))
    
    return normalized_data, target_length

def find_closest_timestamp_match(csi_timestamps, image_timestamp, tolerance_ms=30):
    """
    Tìm CSI timestamp gần nhất với image timestamp
    tolerance_ms: sai lệch tối đa cho phép (mặc định 30ms)
    """
    if not csi_timestamps:
        return None, float('inf')
    
    # Tính khoảng cách với tất cả CSI timestamps
    distances = [abs(ts - image_timestamp) for ts in csi_timestamps]
    min_distance = min(distances)
    
    if min_distance <= tolerance_ms:
        min_idx = distances.index(min_distance)
        return min_idx, min_distance
    
    return None, min_distance

def process_single_action(action_folder_path, action_name):
    """
    Xử lý dữ liệu cho một action cụ thể
    """
    print(f"\n=== Xử lý action: {action_name} ===")
    
    # Đường dẫn các folder
    csi_folder = os.path.join(action_folder_path, 'csi')
    images_folder = os.path.join(action_folder_path, 'images')
    
    # 1. Đọc CSI data
    csv_files = glob.glob(os.path.join(csi_folder, '*.csv'))
    if not csv_files:
        print(f"Không tìm thấy file CSV trong {csi_folder}")
        return None
    
    csv_file = csv_files[0]
    print(f"Đọc CSI data từ: {os.path.basename(csv_file)}")
    
    try:
        # Đọc CSV với quote character để xử lý array data đúng cách
        csi_df = pd.read_csv(csv_file, on_bad_lines='skip', low_memory=False, quotechar='"')
        
        # Nếu vẫn có vấn đề, thử đọc từng dòng
        if 'data' not in csi_df.columns or csi_df['data'].isna().all() or not str(csi_df['data'].iloc[0]).startswith('['):
            print("Thử đọc CSV theo cách khác...")
            # Đọc raw text và parse manually
            with open(csv_file, 'r') as f:
                lines = f.readlines()
            
            # Parse header
            header = lines[0].strip().split(',')
            
            # Parse tất cả data lines
            data_rows = []
            for line in lines[1:]:  # Parse tất cả dòng, không chỉ 5 dòng
                # Tìm vị trí bắt đầu của array data
                array_start = line.find('[')
                if array_start != -1:
                    # Tách phần trước array và array data
                    before_array = line[:array_start].rstrip(',')
                    array_data = line[array_start:].strip()
                    
                    # Split phần trước array
                    row_data = before_array.split(',') + [array_data]
                    if len(row_data) == len(header):
                        data_rows.append(row_data)
            
            if data_rows:
                csi_df = pd.DataFrame(data_rows, columns=header)
                print(f"Đọc được {len(csi_df)} records với manual parsing")
        
        print(f"Số lượng CSI records: {len(csi_df)}")
        
    except Exception as e:
        print(f"Lỗi đọc file CSV: {e}")
        return None
    
    # 2. Xử lý CSI data
    print("Xử lý CSI data...")
    csi_df['csi_timestamp_ms'] = csi_df['timestamp'].apply(parse_csi_timestamp)
    csi_df['processed_data'] = csi_df['data'].apply(process_csi_data)
    
    # Loại bỏ các dòng không có timestamp hợp lệ
    csi_df = csi_df.dropna(subset=['csi_timestamp_ms'])
    csi_df['csi_timestamp_ms'] = csi_df['csi_timestamp_ms'].astype(int)
    
    # Loại bỏ các dòng có processed_data rỗng
    csi_df = csi_df[csi_df['processed_data'] != ""]
    
    # Chuẩn hóa độ dài subcarriers
    print("Chuẩn hóa độ dài subcarriers...")
    processed_data_list = csi_df['processed_data'].tolist()
    normalized_data, target_length = normalize_subcarrier_length(processed_data_list)
    csi_df['normalized_data'] = normalized_data
    
    print(f"Độ dài subcarrier chuẩn: {target_length}")
    print(f"Số CSI records hợp lệ sau xử lý: {len(csi_df)}")
    
    # 3. Đọc và xử lý images
    image_files = glob.glob(os.path.join(images_folder, 'frame_*.jpg'))
    print(f"Số lượng image files: {len(image_files)}")
    
    image_data = []
    for img_path in image_files:
        filename = os.path.basename(img_path)
        timestamp_ms = extract_timestamp_from_image_filename(filename)
        if timestamp_ms:
            image_data.append({
                'image_filename': filename,
                'image_path': img_path,
                'image_timestamp_ms': timestamp_ms
            })
    
    if not image_data:
        print("Không tìm thấy images hợp lệ")
        return None
    
    images_df = pd.DataFrame(image_data)
    print(f"Số lượng images hợp lệ: {len(images_df)}")
    
    # 4. Match CSI với Images theo timestamp
    print("Đang match CSI với images...")
    matched_data = []
    
    csi_timestamps = csi_df['csi_timestamp_ms'].tolist()
    
    # Debug timestamp ranges
    if csi_timestamps and len(images_df) > 0:
        csi_min, csi_max = min(csi_timestamps), max(csi_timestamps)
        img_min = images_df['image_timestamp_ms'].min()
        img_max = images_df['image_timestamp_ms'].max()
        
        print(f"CSI timestamp range: {csi_min} - {csi_max}")
        print(f"Image timestamp range: {img_min} - {img_max}")
        print(f"Time difference: CSI vs Image min = {abs(csi_min - img_min)} ms")
    
    match_count = 0
    for _, img_row in images_df.iterrows():
        img_timestamp = img_row['image_timestamp_ms']
        
        # Tìm CSI record gần nhất
        match_idx, distance = find_closest_timestamp_match(csi_timestamps, img_timestamp)
        
        if match_idx is not None:
            csi_row = csi_df.iloc[match_idx]
            
            matched_data.append({
                'action': action_name,
                'image_filename': img_row['image_filename'],
                'image_path': img_row['image_path'],
                'image_timestamp_ms': img_row['image_timestamp_ms'],
                'csi_timestamp': csi_row['timestamp'],
                'csi_timestamp_ms': csi_row['csi_timestamp_ms'],
                'original_csi_data': csi_row['data'],
                'processed_csi_data': csi_row['processed_data'],
                'normalized_csi_data': csi_row['normalized_data'],
                'timestamp_diff_ms': distance,
                'rssi': csi_row.get('rssi', ''),
                'mac': csi_row.get('mac', ''),
                'channel': csi_row.get('channel', ''),
                'rate': csi_row.get('rate', ''),
                'subcarrier_length': target_length
            })
            match_count += 1
    
    print(f"Đã match thành công: {match_count}/{len(images_df)} images")
    
    if matched_data:
        result_df = pd.DataFrame(matched_data)
        # Sắp xếp theo timestamp
        result_df = result_df.sort_values('image_timestamp_ms')
        return result_df
    
    return None

def create_data_folder_structure(base_path):
    """
    Tạo cấu trúc folder data để chứa dữ liệu đã xử lý
    """
    data_folder = os.path.join(base_path, 'data')
    
    # Tạo các subfolder
    subfolders = [
        'processed',
        'matched_pairs',
        'statistics',
        'visualizations'
    ]
    
    for subfolder in subfolders:
        folder_path = os.path.join(data_folder, subfolder)
        os.makedirs(folder_path, exist_ok=True)
        print(f"Tạo folder: {folder_path}")
    
    return data_folder

def create_classification_structure(base_path):
    """
    Tạo cấu trúc folder cho classification theo tên hành động
    """
    actions = [
        'Dung', 'KeoGhe', 'KhongHanhDong', 'Nam', 
        'Nga', 'Ngoi', 'NhatDo', 'VayTay'
    ]
    
    classification_folder = os.path.join(base_path, 'data', 'classification')
    
    for action in actions:
        action_folder = os.path.join(classification_folder, action)
        csi_folder = os.path.join(action_folder, 'csi')
        image_folder = os.path.join(action_folder, 'images')
        
        os.makedirs(csi_folder, exist_ok=True)
        os.makedirs(image_folder, exist_ok=True)
        
        print(f"Tạo classification structure cho {action}")
    
    return classification_folder

def copy_matched_data_to_classification(matched_data, classification_folder, base_data_activity_path):
    """
    Copy dữ liệu đã match vào cấu trúc classification
    """
    import shutil
    
    action = matched_data['action'].iloc[0] if len(matched_data) > 0 else None
    if not action:
        return
    
    action_csi_folder = os.path.join(classification_folder, action, 'csi')
    action_image_folder = os.path.join(classification_folder, action, 'images')
    
    print(f"Copying {len(matched_data)} matched pairs cho action {action}...")
    
    # Tạo CSV với dữ liệu CSI đã xử lý
    csi_output_file = os.path.join(action_csi_folder, f'{action.lower()}_processed_csi.csv')
    
    # Chọn các cột cần thiết cho CSI
    csi_columns = [
        'image_filename', 'csi_timestamp', 'normalized_csi_data', 
        'timestamp_diff_ms', 'rssi', 'channel', 'rate'
    ]
    
    csi_data = matched_data[csi_columns].copy()
    csi_data.to_csv(csi_output_file, index=False)
    
    # Copy images
    copied_images = 0
    for _, row in matched_data.iterrows():
        src_image_path = row['image_path']
        dst_image_path = os.path.join(action_image_folder, row['image_filename'])
        
        try:
            if os.path.exists(src_image_path) and not os.path.exists(dst_image_path):
                shutil.copy2(src_image_path, dst_image_path)
                copied_images += 1
        except Exception as e:
            print(f"Lỗi copy image {row['image_filename']}: {e}")
    
    print(f"Đã copy {copied_images} images và tạo file CSI: {csi_output_file}")
    
    return csi_output_file, copied_images

def generate_statistics(all_matched_data, output_folder):
    """
    Tạo thống kê tổng quan về dữ liệu đã xử lý
    """
    stats = {}
    
    for action, df in all_matched_data.items():
        if df is not None and len(df) > 0:
            stats[action] = {
                'total_matches': len(df),
                'avg_timestamp_diff_ms': df['timestamp_diff_ms'].mean(),
                'max_timestamp_diff_ms': df['timestamp_diff_ms'].max(),
                'min_timestamp_diff_ms': df['timestamp_diff_ms'].min(),
                'time_span_minutes': (df['image_timestamp_ms'].max() - df['image_timestamp_ms'].min()) / (1000 * 60)
            }
    
    # Lưu thống kê
    stats_df = pd.DataFrame(stats).T
    stats_file = os.path.join(output_folder, 'statistics', 'matching_statistics.csv')
    stats_df.to_csv(stats_file)
    
    print(f"\n=== THỐNG KÊ TỔNG QUAN ===")
    print(stats_df)
    print(f"\nThống kê chi tiết đã lưu: {stats_file}")
    
    return stats

def balance_dataset(all_matched_data, classification_folder, base_path, target_pairs=1250):
    """
    Cân bằng dataset về số lượng pairs cố định cho mỗi class
    """
    print(f"\n=== CÂN BẰNG DATASET VỀ {target_pairs} PAIRS MỖI CLASS ===")
    
    balanced_folder = os.path.join(base_path, 'data', 'classification_balanced')
    
    # Tạo folder balanced mới
    os.makedirs(balanced_folder, exist_ok=True)
    
    balanced_stats = {}
    all_balanced_data = []
    
    for action, df in all_matched_data.items():
        if df is None or len(df) == 0:
            continue
            
        print(f"\nXử lý action: {action}")
        
        # Đường dẫn source
        source_action_folder = os.path.join(classification_folder, action)
        source_images_folder = os.path.join(source_action_folder, "images")
        
        # Đường dẫn destination
        dest_action_folder = os.path.join(balanced_folder, action)
        dest_csi_folder = os.path.join(dest_action_folder, "csi")
        dest_images_folder = os.path.join(dest_action_folder, "images")
        
        # Tạo folder destination
        os.makedirs(dest_csi_folder, exist_ok=True)
        os.makedirs(dest_images_folder, exist_ok=True)
        
        original_count = len(df)
        print(f"  Số pairs ban đầu: {original_count}")
        
        if original_count < target_pairs:
            # Oversample (duplicate random)
            print(f"  Oversample từ {original_count} lên {target_pairs}")
            
            random.seed(42)  # Reproducible
            indices = list(range(original_count))
            
            balanced_indices = []
            while len(balanced_indices) < target_pairs:
                remaining = target_pairs - len(balanced_indices)
                if remaining >= original_count:
                    balanced_indices.extend(indices)
                else:
                    balanced_indices.extend(random.sample(indices, remaining))
            
            balanced_df = df.iloc[balanced_indices].reset_index(drop=True)
            method = 'oversample'
            
        else:
            # Undersample (random selection)
            print(f"  Undersample từ {original_count} xuống {target_pairs}")
            
            random.seed(42)  # Reproducible
            balanced_df = df.sample(n=target_pairs, random_state=42).reset_index(drop=True)
            method = 'undersample'
        
        # Lưu balanced CSV
        balanced_csv_file = os.path.join(dest_csi_folder, f'{action.lower()}_balanced_csi.csv')
        
        # Chọn các cột cần thiết cho CSI
        csi_columns = [
            'image_filename', 'csi_timestamp', 'normalized_csi_data', 
            'timestamp_diff_ms', 'rssi', 'channel', 'rate', 'action'
        ]
        
        # Đảm bảo có cột action
        balanced_df['action'] = action
        balanced_csi_data = balanced_df[csi_columns].copy()
        balanced_csi_data.to_csv(balanced_csv_file, index=False)
        
        # Copy images tương ứng
        copied_images = 0
        missing_images = 0
        
        for _, row in balanced_df.iterrows():
            image_filename = row['image_filename']
            source_image_path = os.path.join(source_images_folder, image_filename)
            dest_image_path = os.path.join(dest_images_folder, image_filename)
            
            try:
                if os.path.exists(source_image_path):
                    # Nếu file đã tồn tại trong destination, tạo tên unique
                    counter = 1
                    original_dest_path = dest_image_path
                    while os.path.exists(dest_image_path):
                        name, ext = os.path.splitext(original_dest_path)
                        dest_image_path = f"{name}_copy{counter}{ext}"
                        counter += 1
                    
                    shutil.copy2(source_image_path, dest_image_path)
                    copied_images += 1
                else:
                    missing_images += 1
                    print(f"    Warning: Không tìm thấy image {image_filename}")
            except Exception as e:
                missing_images += 1
                print(f"    Error copying {image_filename}: {e}")
        
        # Thống kê
        balanced_stats[action] = {
            'original_pairs': original_count,
            'balanced_pairs': len(balanced_df),
            'copied_images': copied_images,
            'missing_images': missing_images,
            'method': method
        }
        
        print(f"  Balanced pairs: {len(balanced_df)}")
        print(f"  Copied images: {copied_images}")
        print(f"  Missing images: {missing_images}")
        
        # Thêm vào dataset tổng hợp
        all_balanced_data.append(balanced_csi_data)
    
    # Tạo combined balanced dataset
    if all_balanced_data:
        print(f"\n=== TẠO COMBINED BALANCED DATASET ===")
        combined_balanced_df = pd.concat(all_balanced_data, ignore_index=True)
        
        # Lưu combined dataset
        combined_balanced_file = os.path.join(base_path, "data", "matched_pairs", "combined_balanced_dataset.csv")
        combined_balanced_df.to_csv(combined_balanced_file, index=False)
        
        print(f"Combined balanced dataset: {len(combined_balanced_df)} records")
        print(f"Đã lưu: {combined_balanced_file}")
        
        # Phân bố theo action
        action_counts = combined_balanced_df['action'].value_counts().sort_index()
        print(f"\nPhân bố balanced theo action:")
        print(action_counts)
        
        # Lưu thống kê balanced
        stats_df = pd.DataFrame(balanced_stats).T
        balanced_stats_file = os.path.join(base_path, "data", "statistics", "balanced_statistics.csv")
        stats_df.to_csv(balanced_stats_file)
        
        print(f"\n=== THỐNG KÊ BALANCED ===")
        print(stats_df)
        print(f"Thống kê balanced đã lưu: {balanced_stats_file}")
        
        return combined_balanced_df, balanced_folder, balanced_stats
    
    return None, balanced_folder, balanced_stats

def main():
    """
    Hàm chính để xử lý tất cả dữ liệu
    """
    # Đường dẫn gốc
    base_path = "/Users/macos/Downloads/Multi-CSI-Frame-App"
    data_activity_path = os.path.join(base_path, "data_activity")
    
    # Tạo cấu trúc folder data
    print("Tạo cấu trúc folder data...")
    data_folder = create_data_folder_structure(base_path)
    
    # Tạo cấu trúc classification
    print("Tạo cấu trúc classification...")
    classification_folder = create_classification_structure(base_path)
    
    # Danh sách 8 actions
    actions = [
        'Dung', 'KeoGhe', 'KhongHanhDong', 'Nam', 
        'Nga', 'Ngoi', 'NhatDo', 'VayTay'
    ]
    
    all_matched_data = {}
    
    # Xử lý từng action
    for action in actions:
        action_path = os.path.join(data_activity_path, action)
        
        if os.path.exists(action_path):
            result_df = process_single_action(action_path, action)
            
            if result_df is not None:
                all_matched_data[action] = result_df
                
                # Lưu kết quả cho từng action
                output_file = os.path.join(data_folder, 'processed', f'{action}_matched_data.csv')
                result_df.to_csv(output_file, index=False)
                print(f"Đã lưu: {output_file}")
                
                # Copy dữ liệu vào cấu trúc classification
                copy_matched_data_to_classification(result_df, classification_folder, data_activity_path)
        else:
            print(f"Không tìm thấy folder: {action_path}")
    
    # Tạo dataset tổng hợp
    if all_matched_data:
        print(f"\n=== TẠO DATASET TỔNG HỢP ===")
        combined_df = pd.concat(all_matched_data.values(), ignore_index=True)
        
        # Lưu dataset tổng hợp
        combined_file = os.path.join(data_folder, 'matched_pairs', 'combined_dataset.csv')
        combined_df.to_csv(combined_file, index=False)
        
        print(f"Dataset tổng hợp: {len(combined_df)} records")
        print(f"Đã lưu: {combined_file}")
        
        # Phân bố theo action
        action_counts = combined_df['action'].value_counts()
        print(f"\nPhân bố theo action:")
        print(action_counts)
        
        # Tạo thống kê
        generate_statistics(all_matched_data, data_folder)
        
        # Lưu phân bố action
        distribution_file = os.path.join(data_folder, 'statistics', 'action_distribution.csv')
        action_counts.to_csv(distribution_file, header=['count'])
        
        # Cân bằng dataset
        print(f"\n" + "="*50)
        balanced_df, balanced_folder, balanced_stats = balance_dataset(
            all_matched_data, classification_folder, base_path, target_pairs=1250
        )
        
        print(f"\n=== HOÀN THÀNH ===")
        print(f"Tổng số original matched pairs: {len(combined_df)}")
        print(f"Tổng số balanced pairs: {len(balanced_df) if balanced_df is not None else 0}")
        print(f"Dữ liệu gốc đã được lưu trong folder: {data_folder}")
        print(f"Dữ liệu balanced đã được lưu trong folder: {balanced_folder}")
        
        return combined_df, balanced_df, data_folder, balanced_folder
    else:
        print("Không có dữ liệu nào được xử lý thành công!")
        return None, None, None, None

if __name__ == "__main__":
    original_data, balanced_data, data_folder, balanced_folder = main()