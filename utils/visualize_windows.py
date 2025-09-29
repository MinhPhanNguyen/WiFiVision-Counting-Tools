import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from pathlib import Path
from collections import Counter
import random

class WindowVisualizer:
    def __init__(self, data_path="data/processed", output_dir="data/windows"):
        self.data_path = data_path
        self.output_dir = output_dir
        self.X_windows = None
        self.y_labels = None
        
    def load_data(self):
        """Load processed data"""
        print("Dang tai du lieu...")
        
        X_path = os.path.join(self.data_path, "X_windows.npy")
        y_path = os.path.join(self.data_path, "y_labels.npy")
        
        if not os.path.exists(X_path) or not os.path.exists(y_path):
            raise FileNotFoundError("Khong tim thay file processed data")
        
        self.X_windows = np.load(X_path, allow_pickle=True)
        self.y_labels = np.load(y_path, allow_pickle=True)
        
        # Convert X_windows to float if it's object type
        if self.X_windows.dtype == object:
            print("   Converting X_windows from object to float...")
            try:
                # Try to convert each window to float
                converted_windows = []
                valid_labels = []
                skipped_count = 0
                
                for i, window in enumerate(self.X_windows):
                    try:
                        converted_window = np.array(window, dtype=np.float32)
                        if converted_window.shape == (100, 148):  # Ensure correct shape
                            converted_windows.append(converted_window)
                            valid_labels.append(self.y_labels[i])
                        else:
                            print(f"   Skipped window {i}: wrong shape {converted_window.shape}")
                            skipped_count += 1
                    except Exception as e:
                        print(f"   Skipped window {i}: conversion error - {e}")
                        skipped_count += 1
                
                self.X_windows = np.array(converted_windows)
                self.y_labels = np.array(valid_labels)
                print(f"   Conversion successful! Kept {len(converted_windows)} windows, skipped {skipped_count}")
                
            except Exception as e:
                print(f"   Conversion failed: {e}")
                raise
        
        print(f"Da tai du lieu:")
        print(f"   Windows shape: {self.X_windows.shape}")
        print(f"   Labels shape: {self.y_labels.shape}")
        
        # Thống kê labels
        counter = Counter(self.y_labels)
        print(f"   Label distribution:")
        for label in sorted(counter.keys()):
            print(f"      Class {label}: {counter[label]} windows")
    
    def create_output_structure(self):
        """Tạo cấu trúc folder output"""
        print(f"Tao cau truc folder trong {self.output_dir}/")
        
        # Tạo main folder
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Tạo folder cho từng class
        unique_labels = np.unique(self.y_labels)
        for label in unique_labels:
            class_dir = os.path.join(self.output_dir, f"class_{label}_people")
            Path(class_dir).mkdir(parents=True, exist_ok=True)
            print(f"   {class_dir}")
    
    def plot_window(self, window_data, title="CSI Window", figsize=(12, 8)):
        """Vẽ một window CSI data"""
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        
        # 1. Heatmap của toàn bộ window
        im1 = axes[0, 0].imshow(window_data.T, aspect='auto', cmap='viridis', interpolation='nearest')
        axes[0, 0].set_title('CSI Heatmap (Features vs Time)')
        axes[0, 0].set_xlabel('Time Steps')
        axes[0, 0].set_ylabel('CSI Features')
        plt.colorbar(im1, ax=axes[0, 0])
        
        # 2. Average CSI values across time
        avg_features = np.mean(window_data, axis=0)
        axes[0, 1].plot(avg_features)
        axes[0, 1].set_title('Average CSI Features')
        axes[0, 1].set_xlabel('Feature Index')
        axes[0, 1].set_ylabel('Average Value')
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Temporal variation (std across features)
        temporal_std = np.std(window_data, axis=1)
        axes[1, 0].plot(temporal_std)
        axes[1, 0].set_title('Temporal Variation (Std across features)')
        axes[1, 0].set_xlabel('Time Steps')
        axes[1, 0].set_ylabel('Standard Deviation')
        axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Feature correlation heatmap (sample 20 features)
        sample_features = window_data[:, ::7]  # Sample every 7th feature
        corr_matrix = np.corrcoef(sample_features.T)
        im4 = axes[1, 1].imshow(corr_matrix, cmap='coolwarm', vmin=-1, vmax=1)
        axes[1, 1].set_title('Feature Correlation (Sampled)')
        plt.colorbar(im4, ax=axes[1, 1])
        
        plt.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        return fig
    
    def visualize_samples_per_class(self, samples_per_class=5, random_seed=42):
        """Tạo visualization cho mỗi class"""
        random.seed(random_seed)
        np.random.seed(random_seed)
        
        unique_labels = np.unique(self.y_labels)
        
        for label in unique_labels:
            print(f"\nDang tao visualization cho Class {label} ({label} nguoi)...")
            
            # Lấy indices của class này
            class_indices = np.where(self.y_labels == label)[0]
            
            if len(class_indices) == 0:
                print(f"   Khong co du lieu cho class {label}")
                continue
            
            # Random sample
            if len(class_indices) > samples_per_class:
                sampled_indices = np.random.choice(class_indices, samples_per_class, replace=False)
            else:
                sampled_indices = class_indices
            
            # Tạo folder cho class
            class_dir = os.path.join(self.output_dir, f"class_{label}_people")
            
            # Vẽ từng sample
            for i, idx in enumerate(sampled_indices):
                window_data = self.X_windows[idx]
                
                title = f"Class {label} ({label} people) - Sample {i+1}"
                fig = self.plot_window(window_data, title)
                
                # Save plot
                filename = f"sample_{i+1:02d}_window_{idx:04d}.png"
                filepath = os.path.join(class_dir, filename)
                fig.savefig(filepath, dpi=150, bbox_inches='tight')
                plt.close(fig)
                
                print(f"   Saved: {filename}")
            
            print(f"   Hoan thanh {len(sampled_indices)} samples cho class {label}")
    
    def create_class_comparison(self):
        """Tạo comparison plot giữa các class"""
        print(f"\nTao class comparison plot...")
        
        unique_labels = np.unique(self.y_labels)
        n_classes = len(unique_labels)
        
        # Tính average pattern cho mỗi class
        fig, axes = plt.subplots(2, n_classes, figsize=(4*n_classes, 8))
        if n_classes == 1:
            axes = axes.reshape(2, 1)
        
        for i, label in enumerate(unique_labels):
            class_indices = np.where(self.y_labels == label)[0]
            
            if len(class_indices) == 0:
                continue
            
            # Average window cho class này
            class_windows = self.X_windows[class_indices]
            avg_window = np.mean(class_windows, axis=0)
            
            # Heatmap
            im1 = axes[0, i].imshow(avg_window.T, aspect='auto', cmap='viridis', interpolation='nearest')
            axes[0, i].set_title(f'Class {label} ({label} people)\nAverage Pattern')
            axes[0, i].set_xlabel('Time Steps')
            if i == 0:
                axes[0, i].set_ylabel('CSI Features')
            plt.colorbar(im1, ax=axes[0, i])
            
            # Average feature values
            avg_features = np.mean(avg_window, axis=0)
            axes[1, i].plot(avg_features)
            axes[1, i].set_title(f'Class {label} - Avg Features')
            axes[1, i].set_xlabel('Feature Index')
            if i == 0:
                axes[1, i].set_ylabel('Average Value')
            axes[1, i].grid(True, alpha=0.3)
        
        plt.suptitle('Class Comparison - Average Patterns', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # Save comparison
        comparison_path = os.path.join(self.output_dir, "class_comparison.png")
        fig.savefig(comparison_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        print(f"   Saved: class_comparison.png")
    
    def create_summary_statistics(self):
        """Tạo summary statistics cho mỗi class"""
        print(f"\nTao summary statistics...")
        
        unique_labels = np.unique(self.y_labels)
        
        # Tính statistics cho mỗi class
        class_stats = {}
        
        for label in unique_labels:
            class_indices = np.where(self.y_labels == label)[0]
            
            if len(class_indices) == 0:
                continue
            
            class_windows = self.X_windows[class_indices]
            
            stats = {
                'count': len(class_indices),
                'mean_value': np.mean(class_windows),
                'std_value': np.std(class_windows),
                'min_value': np.min(class_windows),
                'max_value': np.max(class_windows),
                'mean_temporal_var': np.mean(np.std(class_windows, axis=1)),
                'mean_feature_var': np.mean(np.std(class_windows, axis=2))
            }
            
            class_stats[label] = stats
        
        # Plot statistics
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        
        labels = list(class_stats.keys())
        
        # Mean values
        means = [class_stats[label]['mean_value'] for label in labels]
        axes[0, 0].bar(labels, means)
        axes[0, 0].set_title('Mean CSI Values by Class')
        axes[0, 0].set_xlabel('Class (People Count)')
        axes[0, 0].set_ylabel('Mean Value')
        
        # Standard deviation
        stds = [class_stats[label]['std_value'] for label in labels]
        axes[0, 1].bar(labels, stds)
        axes[0, 1].set_title('Standard Deviation by Class')
        axes[0, 1].set_xlabel('Class (People Count)')
        axes[0, 1].set_ylabel('Std Value')
        
        # Temporal variation
        temp_vars = [class_stats[label]['mean_temporal_var'] for label in labels]
        axes[1, 0].bar(labels, temp_vars)
        axes[1, 0].set_title('Mean Temporal Variation by Class')
        axes[1, 0].set_xlabel('Class (People Count)')
        axes[1, 0].set_ylabel('Temporal Variation')
        
        # Feature variation
        feat_vars = [class_stats[label]['mean_feature_var'] for label in labels]
        axes[1, 1].bar(labels, feat_vars)
        axes[1, 1].set_title('Mean Feature Variation by Class')
        axes[1, 1].set_xlabel('Class (People Count)')
        axes[1, 1].set_ylabel('Feature Variation')
        
        plt.suptitle('Class Statistics Summary', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        # Save statistics
        stats_path = os.path.join(self.output_dir, "class_statistics.png")
        fig.savefig(stats_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        # Save text summary
        summary_path = os.path.join(self.output_dir, "summary_statistics.txt")
        with open(summary_path, 'w') as f:
            f.write("CSI WINDOW ANALYSIS - SUMMARY STATISTICS\n")
            f.write("=" * 50 + "\n\n")
            
            for label in sorted(labels):
                stats = class_stats[label]
                f.write(f"Class {label} ({label} people):\n")
                f.write(f"  Count: {stats['count']} windows\n")
                f.write(f"  Mean Value: {stats['mean_value']:.4f}\n")
                f.write(f"  Std Value: {stats['std_value']:.4f}\n")
                f.write(f"  Min Value: {stats['min_value']:.4f}\n")
                f.write(f"  Max Value: {stats['max_value']:.4f}\n")
                f.write(f"  Temporal Variation: {stats['mean_temporal_var']:.4f}\n")
                f.write(f"  Feature Variation: {stats['mean_feature_var']:.4f}\n")
                f.write("\n")
        
        print(f"   Saved: class_statistics.png")
        print(f"   Saved: summary_statistics.txt")
    
    def run_full_analysis(self, samples_per_class=5):
        """Chạy full analysis"""
        print("BAT DAU WINDOW VISUALIZATION ANALYSIS")
        print("=" * 60)
        
        try:
            # Load data
            self.load_data()
            
            # Create folder structure
            self.create_output_structure()
            
            # Visualize samples per class
            self.visualize_samples_per_class(samples_per_class)
            
            # Create class comparison
            self.create_class_comparison()
            
            # Create summary statistics
            self.create_summary_statistics()
            
            print("\n" + "=" * 60)
            print("HOAN THANH WINDOW VISUALIZATION!")
            print(f"Ket qua duoc luu trong: {self.output_dir}/")
            print("\nCau truc folder:")
            print(f"   {self.output_dir}/")
            for label in np.unique(self.y_labels):
                print(f"   ├── class_{label}_people/")
                print(f"   │   ├── sample_01_window_XXXX.png")
                print(f"   │   └── ...")
            print(f"   ├── class_comparison.png")
            print(f"   ├── class_statistics.png")
            print(f"   └── summary_statistics.txt")
            
        except Exception as e:
            print(f"Loi: {e}")
            return False
        
        return True

def main():
    """Main function"""
    visualizer = WindowVisualizer()
    
    # Chạy với 3 samples per class để không tạo quá nhiều file
    success = visualizer.run_full_analysis(samples_per_class=3)
    
    if success:
        print("\nBan co the xem cac file visualization de so sanh khac biet giua cac class!")

if __name__ == "__main__":
    main()
