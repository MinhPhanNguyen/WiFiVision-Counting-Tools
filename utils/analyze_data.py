import numpy as np
import pandas as pd

def analyze_csi_data():
    """
    Phân tích chi tiết dữ liệu CSI để hiểu range của từng feature
    """
    print("PHÂN TÍCH CHI TIẾT DỮ LIỆU CSI")
    print("="*60)
    
    # Load processed data
    X = np.load('data/processed/X_windows.npy', allow_pickle=True)
    y = np.load('data/processed/y_labels.npy', allow_pickle=True)
    
    print(f"Data shape: {X.shape}")
    print(f"Total features per timestep: {X.shape[2]}")
    
    # Load một file CSV gốc để xem feature names
    try:
        df_sample = pd.read_csv('data/csi_format/csi_0m.csv', nrows=5)
        print(f"\nOriginal CSV columns: {list(df_sample.columns)}")
        
        # 20 features đầu (non-CSI)
        non_csi_features = ['rssi', 'rate', 'sig_mode', 'mcs', 'bandwidth', 
                           'smoothing', 'not_sounding', 'aggregation', 'stbc', 
                           'fec_coding', 'sgi', 'noise_floor', 'ampdu_cnt', 
                           'channel', 'secondary_channel', 'ant', 'sig_len', 
                           'rx_state', 'len', 'first_word']
        
        print(f"\n20 non-CSI features: {non_csi_features}")
        print(f"128 CSI features: csi_0 to csi_127")
        
    except Exception as e:
        print(f"Không thể đọc CSV: {e}")
    
    # Phân tích range của từng feature group
    print(f"\nPHÂN TÍCH RANGE CỦA FEATURES:")
    print("-" * 40)
    
    # Lấy sample để phân tích
    X_sample = X[:100].reshape(-1, X.shape[2])  # 100 windows đầu
    
    # Phân tích 20 features đầu (non-CSI)
    print("NON-CSI FEATURES (0-19):")
    for i in range(min(20, X.shape[2])):
        feature_data = X_sample[:, i]
        min_val = np.min(feature_data)
        max_val = np.max(feature_data)
        mean_val = np.mean(feature_data)
        std_val = np.std(feature_data)
        
        feature_name = non_csi_features[i] if i < len(non_csi_features) else f"feature_{i}"
        print(f"  {i:2d}. {feature_name:15s}: [{min_val:8.2f}, {max_val:8.2f}] mean={mean_val:6.2f} std={std_val:6.2f}")
    
    # Phân tích CSI features (20-147)
    if X.shape[2] > 20:
        print(f"\nCSI FEATURES (20-{X.shape[2]-1}):")
        csi_data = X_sample[:, 20:]
        csi_min = np.min(csi_data)
        csi_max = np.max(csi_data)
        csi_mean = np.mean(csi_data)
        csi_std = np.std(csi_data)
        
        print(f"  CSI Range: [{csi_min:8.2f}, {csi_max:8.2f}] mean={csi_mean:6.2f} std={csi_std:6.2f}")
        
        # Top/bottom CSI values để hiểu distribution
        csi_flat = csi_data.flatten()
        csi_sorted = np.sort(csi_flat)
        print(f"  CSI distribution:")
        print(f"    Min 10 values: {csi_sorted[:10]}")
        print(f"    Max 10 values: {csi_sorted[-10:]}")
        print(f"    Median: {np.median(csi_flat):.2f}")
        print(f"    25th percentile: {np.percentile(csi_flat, 25):.2f}")
        print(f"    75th percentile: {np.percentile(csi_flat, 75):.2f}")
    
    # Tổng kết
    print(f"\nTỔNG KẾT:")
    X_flat = X.reshape(-1, X.shape[2])
    overall_min = np.min(X_flat)
    overall_max = np.max(X_flat)
    overall_mean = np.mean(X_flat)
    overall_std = np.std(X_flat)
    
    print(f"  Overall range: [{overall_min:.2f}, {overall_max:.2f}]")
    print(f"  Overall mean: {overall_mean:.2f}")
    print(f"  Overall std: {overall_std:.2f}")
    
    # Kiểm tra extreme values
    print(f"\nKIỂM TRA EXTREME VALUES:")
    extreme_threshold = 3 * overall_std
    extreme_mask = np.abs(X_flat - overall_mean) > extreme_threshold
    extreme_count = np.sum(extreme_mask)
    extreme_percent = extreme_count / X_flat.size * 100
    
    print(f"  Values beyond 3-sigma: {extreme_count} ({extreme_percent:.2f}%)")
    
    if extreme_count > 0:
        extreme_values = X_flat[extreme_mask]
        print(f"  Extreme values range: [{np.min(extreme_values):.2f}, {np.max(extreme_values):.2f}]")

if __name__ == "__main__":
    analyze_csi_data()
