import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import torch
import torch.nn as nn
import torch.nn.functional as F
import ast
import time
import threading
import tkinter as tk
from tkinter import ttk

def hampel_filter_1d(x: torch.Tensor, window_size: int = 7, n_sigmas: float = 3.0):
    """
    Hampel filter for CSI outlier detection (Paper Method)
    Exactly as implemented in the TransFusion paper
    """
    assert x.ndim >= 1
    L = x.shape[-1]
    pad = window_size // 2
    
    # Manual reflection padding for 1D tensors
    if x.ndim == 1:
        # Reflect padding manually for 1D
        left_pad = x[1:pad+1].flip(0)  # Take first pad elements and flip
        right_pad = x[-pad-1:-1].flip(0)  # Take last pad elements and flip
        xp = torch.cat([left_pad, x, right_pad])
    else:
        # For higher dimensional tensors, add a dimension and use 2D padding
        x_temp = x.unsqueeze(-2)  # Add dimension to make it at least 2D
        xp_temp = F.pad(x_temp, (pad, pad), mode='reflect')
        xp = xp_temp.squeeze(-2)  # Remove the added dimension
    
    out = x.clone()
    for i in range(L):
        window = xp[..., i:i+window_size]
        med = window.median(dim=-1).values
        mad = (window - med.unsqueeze(-1)).abs().median(dim=-1).values
        sigma_est = 1.4826 * mad  
        diff = (x[..., i] - med).abs()
        mask = diff > (n_sigmas * (sigma_est + 1e-9))
        out[..., i] = torch.where(mask, med, x[..., i])
    return out

def preprocess_csi_sequence(csi_data, target_length=128):
    """
    Preprocess CSI sequence using paper methodology
    Includes Hampel filtering and normalization
    """
    # Convert to tensor if numpy array
    if isinstance(csi_data, np.ndarray):
        csi_tensor = torch.FloatTensor(csi_data)
    else:
        csi_tensor = csi_data
    
    # Pad/truncate to required length
    if len(csi_tensor) > target_length:
        csi_tensor = csi_tensor[:target_length]
    else:
        padding = target_length - len(csi_tensor)
        csi_tensor = F.pad(csi_tensor, (0, padding), 'constant', 0)
    
    # Apply Hampel filter (paper method)
    filtered_csi = hampel_filter_1d(csi_tensor, window_size=7, n_sigmas=3.0)
    
    # Normalize to zero mean, unit variance (paper method)
    mean = filtered_csi.mean()
    std = filtered_csi.std()
    if std > 0:
        normalized_csi = (filtered_csi - mean) / std
    else:
        normalized_csi = filtered_csi - mean
    
    return normalized_csi

# Paper CNN Encoder Implementation
class PaperCSIEncoder(nn.Module):
    """
    CNN Encoder exactly as specified in the TransFusion paper
    Architecture: 1D CNN with 3 layers (1→64→128→256 channels)
    """
    def __init__(self, embed_dim=256):
        super().__init__()
        self.cnn_encoder = nn.Sequential(
            nn.Conv1d(1, 64, kernel_size=7, padding=3),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Conv1d(64, 128, kernel_size=5, padding=2),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Conv1d(128, embed_dim, kernel_size=3, padding=1),
            nn.BatchNorm1d(embed_dim),
            nn.ReLU()
        )
        
    def forward(self, x):
        """
        Forward pass through CNN encoder
        Args:
            x: (batch_size, sequence_length) CSI data
        Returns:
            (batch_size, sequence_length, embed_dim) encoded features
        """
        # Add channel dimension: (B, L) -> (B, 1, L)
        x = x.unsqueeze(1)
        
        # CNN processing: (B, 1, L) -> (B, embed_dim, L)
        encoded = self.cnn_encoder(x)
        
        # Transpose for transformer: (B, embed_dim, L) -> (B, L, embed_dim)
        encoded = encoded.transpose(1, 2)
        
        return encoded

class PaperCSIVisualizer:
    """
    3D CSI Visualizer using paper-accurate preprocessing methods
    Compares 1 person vs 7 people scenarios using TransFusion methodology
    """
    
    def __init__(self):
        # Paper configuration (exact values from TransFusion)
        self.config = {
            'csi_seq_len': 128,
            'embed_dim': 256,
            'sample_rate': 25,  # 25 packets/second
            'hampel_window': 7,
            'hampel_sigma': 3.0
        }
        
        # Initialize paper CNN encoder
        self.csi_encoder = PaperCSIEncoder(embed_dim=self.config['embed_dim'])
        
        # Data storage
        self.csi_1_person = None
        self.csi_7_people = None
        self.features_1_person = None
        self.features_7_people = None
        
        # Animation control
        self.animation_running = False
        self.current_frame = 0
        
        self.load_data()
        self.setup_gui()
        
    def load_data(self):
        """Load and preprocess CSI data using paper methods"""
        try:
            # Load raw CSI data
            csi_0_path = "data_input/csi_input/csi_1.csv"
            csi_7_path = "data_input/csi_input/csi_7.csv"
            
            # Load 1 person data (csi_0.csv)
            if os.path.exists(csi_0_path):
                df_0 = pd.read_csv(csi_0_path)
                
                # Try different possible column names
                csi_column = None
                for col in ['data', 'csi_data', 'csi', 'amplitude']:
                    if col in df_0.columns:
                        csi_column = col
                        break
                
                if csi_column and len(df_0) > 0:
                    csi_data = df_0.iloc[0][csi_column]
                    if isinstance(csi_data, str):
                        csi_0_raw = ast.literal_eval(csi_data)
                    else:
                        csi_0_raw = csi_data
                    csi_0_array = np.array(csi_0_raw, dtype=np.float32)
                    
                    # Apply paper preprocessing
                    self.csi_1_person = preprocess_csi_sequence(csi_0_array, self.config['csi_seq_len'])
                else:
                    self.csi_1_person = torch.randn(self.config['csi_seq_len']) * 0.5
            else:
                self.csi_1_person = torch.randn(self.config['csi_seq_len']) * 0.5
            
            # Load 7 people data (csi_7.csv)
            if os.path.exists(csi_7_path):
                df_7 = pd.read_csv(csi_7_path)
                
                # Try different possible column names
                csi_column = None
                for col in ['data', 'csi_data', 'csi', 'amplitude']:
                    if col in df_7.columns:
                        csi_column = col
                        break
                
                if csi_column and len(df_7) > 0:
                    csi_data = df_7.iloc[0][csi_column]
                    if isinstance(csi_data, str):
                        csi_7_raw = ast.literal_eval(csi_data)
                    else:
                        csi_7_raw = csi_data
                    csi_7_array = np.array(csi_7_raw, dtype=np.float32)
                    
                    # Apply paper preprocessing
                    self.csi_7_people = preprocess_csi_sequence(csi_7_array, self.config['csi_seq_len'])
                else:
                    self.csi_7_people = torch.randn(self.config['csi_seq_len']) * 1.5
            else:
                self.csi_7_people = torch.randn(self.config['csi_seq_len']) * 1.5
            
            # Extract features using paper CNN encoder
            self.extract_paper_features()
            
        except Exception as e:
            # Fallback to dummy data
            self.csi_1_person = torch.randn(self.config['csi_seq_len']) * 0.5
            self.csi_7_people = torch.randn(self.config['csi_seq_len']) * 1.5
            self.extract_paper_features()
    
    def extract_paper_features(self):
        """Extract features using paper CNN encoder"""
        try:
            # Prepare batch input (add batch dimension)
            csi_1_batch = self.csi_1_person.unsqueeze(0)  # (1, 128)
            csi_7_batch = self.csi_7_people.unsqueeze(0)  # (1, 128)
            
            # Extract features using paper CNN encoder
            with torch.no_grad():
                self.features_1_person = self.csi_encoder(csi_1_batch)[0]  # (128, 256)
                self.features_7_people = self.csi_encoder(csi_7_batch)[0]  # (128, 256)
            
        except Exception as e:
            # Fallback to dummy features
            self.features_1_person = torch.randn(self.config['csi_seq_len'], self.config['embed_dim'])
            self.features_7_people = torch.randn(self.config['csi_seq_len'], self.config['embed_dim'])
    
    def setup_gui(self):
        """Setup the GUI window"""
        self.root = tk.Tk()
        self.root.title("Paper-Accurate CSI 3D Visualizer - TransFusion Preprocessing")
        self.root.geometry("1600x1000")  # Increased window size for larger plots
        
        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title and info
        title_label = ttk.Label(main_frame, 
                               text="TransFusion Paper CSI Preprocessing - 3D Visualization", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=8)
        
        info_label = ttk.Label(main_frame, 
                              text="CNN Encoder: 1→64→128→256 channels | Hampel Filter + Normalization",
                              font=("Arial", 11))
        info_label.pack(pady=3)
        
        # Additional info for controls
        control_info_label = ttk.Label(main_frame, 
                                     text="Controls: Speed = Animation delay (s) | Features = Number of dimensions to display",
                                     font=("Arial", 10),
                                     foreground="gray")
        control_info_label.pack(pady=3)
        
        # Control panel
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        # Start/Stop animation
        self.start_button = ttk.Button(control_frame, text="Start Animation", command=self.start_animation)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop Animation", command=self.stop_animation)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Speed control
        ttk.Label(control_frame, text="Speed:").pack(side=tk.LEFT, padx=(20,5))
        self.speed_var = tk.DoubleVar(value=0.1)
        speed_scale = ttk.Scale(control_frame, from_=0.01, to=1.0, variable=self.speed_var, orient=tk.HORIZONTAL, length=150)
        speed_scale.pack(side=tk.LEFT, padx=5)
        
        # Speed value display
        self.speed_value_label = ttk.Label(control_frame, text="0.100s", 
                                          font=("Arial", 9, "bold"), 
                                          foreground="blue")
        self.speed_value_label.pack(side=tk.LEFT, padx=5)
        
        # Feature depth control
        ttk.Label(control_frame, text="Features:").pack(side=tk.LEFT, padx=(20,5))
        self.feature_var = tk.IntVar(value=32)
        feature_scale = ttk.Scale(control_frame, from_=16, to=256, variable=self.feature_var, orient=tk.HORIZONTAL, length=150)
        feature_scale.pack(side=tk.LEFT, padx=5)
        
        # Feature value display
        self.feature_value_label = ttk.Label(control_frame, text="32/256", 
                                           font=("Arial", 9, "bold"), 
                                           foreground="red")
        self.feature_value_label.pack(side=tk.LEFT, padx=5)
        
        # Bind update functions to sliders
        speed_scale.config(command=self.update_speed_display)
        feature_scale.config(command=self.update_feature_display)
        
        # Create matplotlib figure
        self.create_plot()
        
    def create_plot(self):
        """Create the 3D plot"""
        # Increase figure size for better visibility
        self.fig = plt.Figure(figsize=(18, 10))
        
        # Create 2 subplots side by side with more space
        self.ax1 = self.fig.add_subplot(121, projection='3d')
        self.ax2 = self.fig.add_subplot(122, projection='3d')
        
        # Setup axes
        self.setup_axes()
        
        # Embed in tkinter
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        self.canvas = FigureCanvasTkAgg(self.fig, self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Initial plot
        self.update_plot()
    
    def update_speed_display(self, value):
        """Update speed value display"""
        speed_val = float(value)
        if speed_val >= 1.0:
            self.speed_value_label.config(text=f"{speed_val:.1f}s")
        else:
            self.speed_value_label.config(text=f"{speed_val:.3f}s")
    
    def update_feature_display(self, value):
        """Update feature value display"""
        feature_val = int(float(value))
        self.feature_value_label.config(text=f"{feature_val}/256")
        # Auto-update plot when features change
        if hasattr(self, 'canvas'):
            self.update_plot()
    
    def setup_axes(self):
        """Setup 3D axes properties"""
        # Left plot - 1 person
        self.ax1.set_xlabel('Time Steps', fontsize=11, fontweight='bold')
        self.ax1.set_ylabel('Feature Index', fontsize=11, fontweight='bold')
        self.ax1.set_zlabel('Feature Value', fontsize=11, fontweight='bold')
        self.ax1.set_title('1 Person - Paper CNN Features', fontsize=14, fontweight='bold')
        
        # Right plot - 7 people
        self.ax2.set_xlabel('Time Steps', fontsize=11, fontweight='bold')
        self.ax2.set_ylabel('Feature Index', fontsize=11, fontweight='bold')
        self.ax2.set_zlabel('Feature Value', fontsize=11, fontweight='bold')
        self.ax2.set_title('7 People - Paper CNN Features', fontsize=14, fontweight='bold')
        
        # Calculate dynamic Z limits based on actual data
        if hasattr(self, 'features_1_person') and hasattr(self, 'features_7_people'):
            num_features = min(self.feature_var.get(), self.config['embed_dim'])
            
            # Get current data subset
            data_1 = self.features_1_person[:, :num_features].detach().numpy()
            data_7 = self.features_7_people[:, :num_features].detach().numpy()
            
            # Calculate combined min/max for consistent scaling
            z_min = min(data_1.min(), data_7.min())
            z_max = max(data_1.max(), data_7.max())
            
            # Add some padding for better visualization
            z_range = z_max - z_min
            z_padding = z_range * 0.1
            z_min -= z_padding
            z_max += z_padding
        else:
            # Default fallback
            z_min, z_max = -1, 4
        
        # Set consistent limits
        self.ax1.set_xlim(0, self.config['csi_seq_len'])
        self.ax2.set_xlim(0, self.config['csi_seq_len'])
        
        # Dynamic Y limits based on features displayed
        y_limit = min(self.feature_var.get(), 64)
        self.ax1.set_ylim(0, y_limit)
        self.ax2.set_ylim(0, y_limit)
        
        # Dynamic Z limits
        self.ax1.set_zlim(z_min, z_max)
        self.ax2.set_zlim(z_min, z_max)
    
    def update_plot(self):
        """Update the 3D visualization"""
        if self.features_1_person is None or self.features_7_people is None:
            return
        
        # Clear previous plots
        self.ax1.clear()
        self.ax2.clear()
        self.setup_axes()
        
        # Get number of features to display
        num_features = min(self.feature_var.get(), self.config['embed_dim'])
        
        # Create time and feature grids
        time_steps = np.arange(self.config['csi_seq_len'])
        feature_indices = np.arange(num_features)
        T, F = np.meshgrid(time_steps, feature_indices)
        
        # Get feature values (transpose to match meshgrid)
        features_1 = self.features_1_person[:, :num_features].detach().numpy().T
        features_7 = self.features_7_people[:, :num_features].detach().numpy().T
        
        # Apply animation offset if running
        if self.animation_running:
            offset = self.current_frame * 0.1
            T_anim = T + offset
        else:
            T_anim = T
        
        # Plot 3D surfaces with enhanced visual quality
        surf1 = self.ax1.plot_surface(T_anim, F, features_1, 
                                     cmap='viridis', alpha=0.85, 
                                     linewidth=0, antialiased=True,
                                     rstride=1, cstride=1,
                                     edgecolors='none')
        
        surf2 = self.ax2.plot_surface(T_anim, F, features_7, 
                                     cmap='plasma', alpha=0.85, 
                                     linewidth=0, antialiased=True,
                                     rstride=1, cstride=1,
                                     edgecolors='none')
        
        # Add contour lines at the bottom for better depth perception
        self.ax1.contour(T_anim, F, features_1, zdir='z', offset=features_1.min()-0.1, 
                        cmap='viridis', alpha=0.3)
        self.ax2.contour(T_anim, F, features_7, zdir='z', offset=features_7.min()-0.1, 
                        cmap='plasma', alpha=0.3)
        
        # Refresh canvas
        self.canvas.draw()
    
    def animation_loop(self):
        """Animation loop running in separate thread"""
        while self.animation_running:
            self.current_frame += 1
            if self.current_frame > 100:  # Reset after 100 frames
                self.current_frame = 0
            
            # Update plot in main thread
            self.root.after(0, self.update_plot)
            
            # Sleep based on speed setting
            time.sleep(self.speed_var.get())
    
    def start_animation(self):
        """Start the animation"""
        if not self.animation_running:
            self.animation_running = True
            self.animation_thread = threading.Thread(target=self.animation_loop, daemon=True)
            self.animation_thread.start()
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
    
    def stop_animation(self):
        """Stop the animation"""
        self.animation_running = False
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
    
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()

def main():
    """Main function"""
    visualizer = PaperCSIVisualizer()
    visualizer.run()

if __name__ == "__main__":
    main()
