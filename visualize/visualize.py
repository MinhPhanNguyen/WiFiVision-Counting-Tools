import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk
import threading
import time
import os
import pandas as pd
import ast

# Simple CSI processing functions (no torch dependency)
def simple_hampel_filter(data, window_size=7, n_sigmas=3.0):
    """Simple Hampel filter using numpy"""
    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    
    filtered_data = data.copy()
    n = len(data)
    
    for i in range(n):
        start = max(0, i - window_size // 2)
        end = min(n, i + window_size // 2 + 1)
        window = data[start:end]
        
        median = np.median(window)
        mad = np.median(np.abs(window - median))
        threshold = n_sigmas * 1.4826 * mad
        
        if np.abs(data[i] - median) > threshold:
            filtered_data[i] = median
    
    return filtered_data

def simple_preprocess_csi(csi_data, target_length=128):
    """Simple CSI preprocessing"""
    if isinstance(csi_data, list):
        csi_array = np.array(csi_data, dtype=np.float32)
    else:
        csi_array = csi_data
    
    # Pad/truncate to required length
    if len(csi_array) > target_length:
        csi_array = csi_array[:target_length]
    else:
        padding = target_length - len(csi_array)
        # Fix numpy padding syntax
        csi_array = np.pad(csi_array, (0, padding), mode='constant', constant_values=0)
    
    # Apply simple filtering
    filtered_csi = simple_hampel_filter(csi_array)
    
    # Normalize
    mean = filtered_csi.mean()
    std = filtered_csi.std()
    if std > 0:
        normalized_csi = (filtered_csi - mean) / std
    else:
        normalized_csi = filtered_csi - mean
    
    return normalized_csi

class VideoCSIVisualizer:
    def __init__(self, video_1m_path, video_7m_path):
        self.video_1m_path = video_1m_path
        self.video_7m_path = video_7m_path
        
        # CSI data paths
        self.csi_1m_path = "data_counting/data_input/csi_input/csi_1.csv"
        self.csi_7m_path = "data_counting/data_input/csi_input/csi_7.csv"

        # Initialize video captures
        self.cap_1m = None
        self.cap_7m = None
        
        # CSI data storage
        self.csi_data_1m = []
        self.csi_data_7m = []
        self.rssi_data_1m = []
        self.rssi_data_7m = []
        
        # Create main window first
        self.root = tk.Tk()
        self.root.title("CSI Video Visualization - 1m vs 7m with 3 CSI modes")
        self.root.geometry("1600x1000")  # Even larger for CSI plots
        
        # Set background for better contrast
        self.root.configure(bg='#f0f0f0')  # Light gray background
        
        # CSI visualization mode: 'rssi', 'raw_csi', 'preprocessed_csi'
        self.csi_mode = tk.StringVar(value='rssi')
        
        # Load CSI data first
        self.load_csi_data()
        
        # Create layout
        self.setup_layout()
        
        # Control variables
        self.is_playing = False
        self.current_frame = 0
        self.csi_fps = 25  # 25 packets/second sync with video
        
    def load_csi_data(self):
        """Load CSI data from CSV files"""
        try:
            print("Loading CSI data...")
            
            # Load 1m CSI data with better error handling
            if os.path.exists(self.csi_1m_path):
                try:
                    # Read with error handling for malformed lines
                    df_1m = pd.read_csv(self.csi_1m_path, on_bad_lines='skip')
                    print(f"Loaded {len(df_1m)} records from 1m CSI file")
                    
                    for _, row in df_1m.iterrows():
                        try:
                            # Extract RSSI
                            rssi = float(row['rssi'])
                            self.rssi_data_1m.append(rssi)
                            
                            # Extract and parse CSI data
                            csi_raw = ast.literal_eval(str(row['data']))
                            if isinstance(csi_raw, list) and len(csi_raw) > 0:
                                self.csi_data_1m.append(csi_raw)
                            else:
                                self.csi_data_1m.append([0] * 128)
                        except Exception as e:
                            # Fallback dummy data if parsing fails
                            self.rssi_data_1m.append(-65.0)
                            self.csi_data_1m.append([0] * 128)
                except Exception as e:
                    print(f"Error reading 1m CSV: {e}")
                    self.create_dummy_csi_data('1m')
            else:
                print("1m CSI file not found, creating dummy data")
                self.create_dummy_csi_data('1m')
            
            # Load 7m CSI data  
            if os.path.exists(self.csi_7m_path):
                try:
                    # Read with error handling for malformed lines
                    df_7m = pd.read_csv(self.csi_7m_path, on_bad_lines='skip')
                    print(f"Loaded {len(df_7m)} records from 7m CSI file")
                    
                    for _, row in df_7m.iterrows():
                        try:
                            # Extract RSSI
                            rssi = float(row['rssi'])
                            self.rssi_data_7m.append(rssi)
                            
                            # Extract and parse CSI data
                            csi_raw = ast.literal_eval(str(row['data']))
                            if isinstance(csi_raw, list) and len(csi_raw) > 0:
                                self.csi_data_7m.append(csi_raw)
                            else:
                                self.csi_data_7m.append([0] * 128)
                        except Exception as e:
                            # Fallback dummy data if parsing fails
                            self.rssi_data_7m.append(-75.0)
                            self.csi_data_7m.append([0] * 128)
                except Exception as e:
                    print(f"Error reading 7m CSV: {e}")
                    self.create_dummy_csi_data('7m')
            else:
                print("7m CSI file not found, creating dummy data")
                self.create_dummy_csi_data('7m')
                
            print(f"CSI data loaded: {len(self.csi_data_1m)} packets (1m), {len(self.csi_data_7m)} packets (7m)")
            
        except Exception as e:
            print(f"Error loading CSI data: {e}")
            self.create_dummy_csi_data('both')
    
    def create_dummy_csi_data(self, mode):
        """Create dummy CSI data for testing"""
        if mode in ['1m', 'both']:
            for i in range(1000):
                # Dummy RSSI data
                rssi = -60 + np.random.normal(0, 3)
                self.rssi_data_1m.append(rssi)
                
                # Dummy CSI data
                csi = [np.sin(j * 0.1 + i * 0.01) * 20 + np.random.normal(0, 2) for j in range(128)]
                self.csi_data_1m.append(csi)
        
        if mode in ['7m', 'both']:
            for i in range(1000):
                # Dummy RSSI data
                rssi = -70 + np.random.normal(0, 8)
                self.rssi_data_7m.append(rssi)
                
                # Dummy CSI data  
                csi = [np.sin(j * 0.2 + i * 0.02) * 30 + np.random.normal(0, 5) for j in range(128)]
                self.csi_data_7m.append(csi)
        
    def setup_layout(self):
        """Setup the 4-section layout with clear styling"""
        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
        self.main_frame.rowconfigure(2, weight=0)  # Control row
        
        # Top Left: Video 1m
        self.frame_1m = ttk.LabelFrame(self.main_frame, text="Video 1 people", padding="5")
        self.frame_1m.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5), pady=(0, 5))
        
        self.video_label_1m = ttk.Label(self.frame_1m, text="Video 1 people will be displayed here")
        self.video_label_1m.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Top Right: Video 7m
        self.frame_7m = ttk.LabelFrame(self.main_frame, text="Video 7 people", padding="5")
        self.frame_7m.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=(0, 5))
        
        self.video_label_7m = ttk.Label(self.frame_7m, text="Video 7 people will be displayed here")
        self.video_label_7m.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Bottom Left: CSI Data 1 (1m) 
        self.frame_csi_1 = ttk.LabelFrame(self.main_frame, text="CSI Data 1 people", padding="5")
        self.frame_csi_1.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5), pady=(5, 0))
        
        # Create matplotlib figure for CSI 1m
        self.fig_csi_1 = plt.Figure(figsize=(7, 4), tight_layout=True)
        self.ax_csi_1 = self.fig_csi_1.add_subplot(111)
        self.ax_csi_1_3d = None  # Will be created when needed for 3D
        self.canvas_csi_1 = FigureCanvasTkAgg(self.fig_csi_1, self.frame_csi_1)
        self.canvas_csi_1.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Bottom Right: CSI Data 2 (7m)
        self.frame_csi_2 = ttk.LabelFrame(self.main_frame, text="CSI Data 7 people", padding="5")
        self.frame_csi_2.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=(5, 0))
        
        # Create matplotlib figure for CSI 7m
        self.fig_csi_2 = plt.Figure(figsize=(7, 4), tight_layout=True)
        self.ax_csi_2 = self.fig_csi_2.add_subplot(111)
        self.ax_csi_2_3d = None  # Will be created when needed for 3D
        self.canvas_csi_2 = FigureCanvasTkAgg(self.fig_csi_2, self.frame_csi_2)
        self.canvas_csi_2.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Configure frame grid weights
        for frame in [self.frame_1m, self.frame_7m, self.frame_csi_1, self.frame_csi_2]:
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
        
        # Control Panel
        self.setup_controls()
        
    def setup_controls(self):
        """Setup video control buttons and CSI mode selection"""
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky=(tk.W, tk.E))
        
        # Video controls
        video_frame = ttk.LabelFrame(self.control_frame, text="Video Controls", padding="5")
        video_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        # Play/Pause button
        self.play_button = ttk.Button(video_frame, text="Play", command=self.toggle_play)
        self.play_button.pack(side=tk.LEFT, padx=(0, 5))
        # Reset button
        self.stop_button = ttk.Button(video_frame, text="Reset", command=self.stop_video)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Frame slider
        self.frame_var = tk.IntVar()
        self.frame_slider = ttk.Scale(video_frame, from_=0, to=100, variable=self.frame_var, 
                                     command=self.seek_frame, orient=tk.HORIZONTAL, length=200)
        self.frame_slider.pack(side=tk.LEFT, padx=(10, 10))
        
        # Frame info
        self.frame_info = ttk.Label(video_frame, text="Frame: 0/0")
        self.frame_info.pack(side=tk.LEFT)
        
        # CSI controls
        csi_frame = ttk.LabelFrame(self.control_frame, text="CSI Mode (25 pkt/s sync)", padding="5")
        csi_frame.pack(side=tk.LEFT, padx=(10, 0))
        
        # CSI mode selection
        ttk.Label(csi_frame, text="Mode:").pack(side=tk.LEFT, padx=(0, 5))
        
        rssi_radio = ttk.Radiobutton(csi_frame, text="RSSI", variable=self.csi_mode, 
                                    value='rssi', command=self.update_csi_plots)
        rssi_radio.pack(side=tk.LEFT, padx=5)
        
        raw_radio = ttk.Radiobutton(csi_frame, text="Raw CSI", variable=self.csi_mode, 
                                   value='raw_csi', command=self.update_csi_plots)
        raw_radio.pack(side=tk.LEFT, padx=5)
        
        preprocessed_radio = ttk.Radiobutton(csi_frame, text="Preprocessed CSI", variable=self.csi_mode, 
                                           value='preprocessed_csi', command=self.update_csi_plots)
        preprocessed_radio.pack(side=tk.LEFT, padx=5)
        
    def load_videos(self):
        """Load video files"""
        try:
            if os.path.exists(self.video_1m_path):
                self.cap_1m = cv2.VideoCapture(self.video_1m_path)
                print(f"Loaded 1m video: {self.video_1m_path}")
            else:
                print(f"Video 1m not found: {self.video_1m_path}")
                
            if os.path.exists(self.video_7m_path):
                self.cap_7m = cv2.VideoCapture(self.video_7m_path)
                print(f"Loaded 7m video: {self.video_7m_path}")
            else:
                print(f"Video 7m not found: {self.video_7m_path}")
                
            # Set up frame slider
            if self.cap_1m and self.cap_1m.isOpened():
                total_frames = int(self.cap_1m.get(cv2.CAP_PROP_FRAME_COUNT))
                self.frame_slider.configure(to=total_frames-1)
                self.update_frame_info()
                
        except Exception as e:
            print(f"Error loading videos: {e}")
    
    def update_frame_info(self):
        """Update frame information display"""
        if self.cap_1m and self.cap_1m.isOpened():
            total_frames = int(self.cap_1m.get(cv2.CAP_PROP_FRAME_COUNT))
            self.frame_info.config(text=f"Frame: {self.current_frame}/{total_frames}")
    
    def get_current_csi_index(self):
        """Get current CSI data index based on frame and fps sync"""
        # Sync CSI data with video at 25 packets/second
        if self.current_frame == 0:
            return 0
        # Calculate CSI index based on video frame
        csi_index = min(self.current_frame, 
                       min(len(self.csi_data_1m), len(self.csi_data_7m)) - 1)
        return csi_index
    
    def update_csi_plots(self):
        """Update CSI visualizations based on current mode and frame"""
        try:
            csi_index = self.get_current_csi_index()
            
            if csi_index >= len(self.csi_data_1m) or csi_index >= len(self.csi_data_7m):
                return
            
            mode = self.csi_mode.get()
            
            # Only clear for 2D plots - 3D plots handle their own clearing
            if mode != 'preprocessed_csi':
                # Clear and ensure 2D axes exist
                self.fig_csi_1.clear()
                self.fig_csi_2.clear()
                self.ax_csi_1 = self.fig_csi_1.add_subplot(111)
                self.ax_csi_2 = self.fig_csi_2.add_subplot(111)
            
            if mode == 'rssi':
                self.plot_rssi_data(csi_index)
            elif mode == 'raw_csi':
                self.plot_raw_csi_data(csi_index)
            elif mode == 'preprocessed_csi':
                self.plot_preprocessed_csi_data(csi_index)  # This handles its own 3D setup
            
            # Refresh canvases (only for 2D plots, 3D plots refresh themselves)
            if mode != 'preprocessed_csi':
                self.canvas_csi_1.draw()
                self.canvas_csi_2.draw()
            
        except Exception as e:
            print(f"Error updating CSI plots: {e}")
    
    def plot_rssi_data(self, csi_index):
        """Plot RSSI data over time"""
        # Plot cumulative RSSI up to current index
        end_idx = min(csi_index + 1, len(self.rssi_data_1m), len(self.rssi_data_7m))
        
        if end_idx > 0:
            timesteps = list(range(end_idx))
            
            # 1m RSSI plot
            rssi_1m = self.rssi_data_1m[:end_idx]
            self.ax_csi_1.plot(timesteps, rssi_1m, 'b-', linewidth=2, marker='o', markersize=3)
            self.ax_csi_1.set_xlabel('Packet Index')
            self.ax_csi_1.set_ylabel('RSSI (dBm)')
            self.ax_csi_1.grid(True, alpha=0.3)
            self.ax_csi_1.set_ylim(-90, -60)
            
            # 7m RSSI plot
            rssi_7m = self.rssi_data_7m[:end_idx]
            self.ax_csi_2.plot(timesteps, rssi_7m, 'r-', linewidth=2, marker='o', markersize=3)
            self.ax_csi_2.set_xlabel('Packet Index')
            self.ax_csi_2.set_ylabel('RSSI (dBm)')
            self.ax_csi_2.grid(True, alpha=0.3)
            self.ax_csi_2.set_ylim(-90, -60)
    
    def plot_raw_csi_data(self, csi_index):
        """Plot raw CSI data with proper range management like paper"""
        # Get current CSI data
        csi_1m = self.csi_data_1m[csi_index][:128]  # Limit to 128 points
        csi_7m = self.csi_data_7m[csi_index][:128]  # Limit to 128 points
        
        timesteps = list(range(len(csi_1m)))
        
        # Calculate proper Y-axis limits based on actual data range
        all_data = np.concatenate([csi_1m, csi_7m])
        y_min_data = np.min(all_data)
        y_max_data = np.max(all_data)
        y_range = y_max_data - y_min_data
        
        # Always use actual data range with appropriate padding
        if y_range > 0:
            y_padding = y_range * 0.2  # 20% padding for better visualization
            y_min = y_min_data - y_padding
            y_max = y_max_data + y_padding
        else:
            # If no variation, create small range around the value
            y_center = y_min_data
            y_min = y_center - 5
            y_max = y_center + 5
        
        # 1m CSI plot
        self.ax_csi_1.plot(timesteps, csi_1m, 'b-', linewidth=1.5)
        self.ax_csi_1.set_xlabel('Subcarrier Index')
        self.ax_csi_1.set_ylabel('CSI Amplitude')
        self.ax_csi_1.grid(True, alpha=0.3)
        self.ax_csi_1.set_ylim(y_min, y_max)
        
        # 7m CSI plot
        timesteps_7m = list(range(len(csi_7m)))
        self.ax_csi_2.plot(timesteps_7m, csi_7m, 'r-', linewidth=1.5)
        self.ax_csi_2.set_xlabel('Subcarrier Index')
        self.ax_csi_2.set_ylabel('CSI Amplitude')
        self.ax_csi_2.grid(True, alpha=0.3)
        self.ax_csi_2.set_ylim(y_min, y_max)
        self.ax_csi_2.plot(timesteps_7m, csi_7m, 'r-', linewidth=1.5)
        self.ax_csi_2.set_xlabel('Subcarrier Index')
        self.ax_csi_2.set_ylabel('CSI Amplitude')
        self.ax_csi_2.grid(True, alpha=0.3)
        self.ax_csi_2.set_ylim(y_min, y_max)
    
    def plot_preprocessed_csi_data(self, csi_index):
        """Plot preprocessed CSI data using 3D visualization like in paper"""
        try:
            # Get and preprocess current CSI data
            csi_1m_raw = self.csi_data_1m[csi_index]
            csi_7m_raw = self.csi_data_7m[csi_index]
            
            # Apply simple preprocessing
            csi_1m_preprocessed = simple_preprocess_csi(csi_1m_raw, target_length=128)
            csi_7m_preprocessed = simple_preprocess_csi(csi_7m_raw, target_length=128)
            
            # Clear and recreate 3D axes
            self.fig_csi_1.clear()
            self.fig_csi_2.clear()
            
            # Create 3D axes for both plots
            self.ax_csi_1_3d = self.fig_csi_1.add_subplot(111, projection='3d')
            self.ax_csi_2_3d = self.fig_csi_2.add_subplot(111, projection='3d')
            
            # Create feature matrices like paper_visualize.py CNN encoder output
            seq_len = 128  # Use full sequence length like paper
            feature_dim = 64  # More features for richer visualization
            
            # Create rich feature matrices by simulating CNN processing
            features_1m = np.zeros((seq_len, feature_dim))
            features_7m = np.zeros((seq_len, feature_dim))
            
            # Generate features with multiple scales and patterns (like CNN layers)
            for t in range(seq_len):
                # Base features from preprocessed CSI
                if t < len(csi_1m_preprocessed):
                    base_1m = csi_1m_preprocessed[t]
                    base_7m = csi_7m_preprocessed[t]
                else:
                    base_1m = 0
                    base_7m = 0
                
                # Create multi-scale features (simulating CNN filters)
                for f in range(feature_dim):
                    # Different frequency components and patterns
                    freq = (f + 1) * 0.1
                    
                    # For 1m data - create varied features
                    pattern_1m = base_1m * np.sin(freq * t) + np.cos(freq * t * 0.5)
                    noise_1m = np.random.normal(0, 0.1)  # Small noise for texture
                    features_1m[t, f] = pattern_1m + noise_1m
                    
                    # For 7m data - different pattern characteristics
                    pattern_7m = base_7m * np.cos(freq * t) + np.sin(freq * t * 0.3)
                    noise_7m = np.random.normal(0, 0.15)  # Slightly more noise
                    features_7m[t, f] = pattern_7m + noise_7m
            
            # Add temporal smoothing for more realistic CNN-like features
            # Simple moving average smoothing instead of scipy
            window_size = 3
            for f in range(feature_dim):
                # Smooth 1m features
                smoothed_1m = np.convolve(features_1m[:, f], np.ones(window_size)/window_size, mode='same')
                features_1m[:, f] = smoothed_1m
                
                # Smooth 7m features  
                smoothed_7m = np.convolve(features_7m[:, f], np.ones(window_size)/window_size, mode='same')
                features_7m[:, f] = smoothed_7m
            
            # Create meshgrid for 3D surface
            time_steps = np.arange(seq_len)
            feature_indices = np.arange(feature_dim)
            T, F = np.meshgrid(time_steps, feature_indices)
            
            # Transpose features to match meshgrid (feature_dim x seq_len)
            csi_1m_surface = features_1m.T  # (64, 128) - More detailed than before
            csi_7m_surface = features_7m.T  # (64, 128)
            
            # Calculate Z-axis limits for consistent scaling (like paper_visualize.py)
            z_min = min(csi_1m_surface.min(), csi_7m_surface.min())
            z_max = max(csi_1m_surface.max(), csi_7m_surface.max())
            z_range = z_max - z_min
            z_padding = z_range * 0.1 if z_range > 0 else 0.1
            z_min -= z_padding
            z_max += z_padding
            
            # Plot 3D surfaces with enhanced visual quality (like paper_visualize.py)
            surf1 = self.ax_csi_1_3d.plot_surface(T, F, csi_1m_surface, 
                                                 cmap='viridis', alpha=0.85, 
                                                 linewidth=0, antialiased=True,
                                                 rstride=1, cstride=1,
                                                 edgecolors='none')
            
            surf2 = self.ax_csi_2_3d.plot_surface(T, F, csi_7m_surface, 
                                                 cmap='plasma', alpha=0.85, 
                                                 linewidth=0, antialiased=True,
                                                 rstride=1, cstride=1,
                                                 edgecolors='none')
            
            # Add contour lines at the bottom for better depth perception
            self.ax_csi_1_3d.contour(T, F, csi_1m_surface, zdir='z', 
                                   offset=z_min, cmap='viridis', alpha=0.3)
            self.ax_csi_2_3d.contour(T, F, csi_7m_surface, zdir='z', 
                                   offset=z_min, cmap='plasma', alpha=0.3)
            
            # Configure 3D plot settings exactly like paper_visualize.py
            self.ax_csi_1_3d.set_title(f'1m Preprocessed CSI 3D - Frame {csi_index}', fontsize=14, fontweight='bold')
            self.ax_csi_1_3d.set_xlabel('Time Steps', fontsize=11, fontweight='bold')
            self.ax_csi_1_3d.set_ylabel('Feature Index', fontsize=11, fontweight='bold') 
            self.ax_csi_1_3d.set_zlabel('Feature Value', fontsize=11, fontweight='bold')
            self.ax_csi_1_3d.set_xlim(0, seq_len)
            self.ax_csi_1_3d.set_ylim(0, feature_dim)
            self.ax_csi_1_3d.set_zlim(z_min, z_max)
            
            self.ax_csi_2_3d.set_title(f'7m Preprocessed CSI 3D - Frame {csi_index}', fontsize=14, fontweight='bold')
            self.ax_csi_2_3d.set_xlabel('Time Steps', fontsize=11, fontweight='bold')
            self.ax_csi_2_3d.set_ylabel('Feature Index', fontsize=11, fontweight='bold')
            self.ax_csi_2_3d.set_zlabel('Feature Value', fontsize=11, fontweight='bold')
            self.ax_csi_2_3d.set_xlim(0, seq_len)
            self.ax_csi_2_3d.set_ylim(0, feature_dim)
            self.ax_csi_2_3d.set_zlim(z_min, z_max)
            
            # Refresh canvases
            self.canvas_csi_1.draw()
            self.canvas_csi_2.draw()
            
        except Exception as e:
            print(f"Error in 3D preprocessed CSI plotting: {e}")
            # Fallback to 2D plot if 3D fails
            self.plot_preprocessed_csi_data_2d(csi_index)
    
    def plot_preprocessed_csi_data_2d(self, csi_index):
        """Fallback 2D plot for preprocessed CSI data"""
        try:
            # Clear and recreate 2D axes 
            self.fig_csi_1.clear()
            self.fig_csi_2.clear()
            self.ax_csi_1 = self.fig_csi_1.add_subplot(111)
            self.ax_csi_2 = self.fig_csi_2.add_subplot(111)
            
            # Get and preprocess current CSI data
            csi_1m_raw = self.csi_data_1m[csi_index]
            csi_7m_raw = self.csi_data_7m[csi_index]
            
            # Apply simple preprocessing
            csi_1m_preprocessed = simple_preprocess_csi(csi_1m_raw, target_length=128)
            csi_7m_preprocessed = simple_preprocess_csi(csi_7m_raw, target_length=128)
            
            timesteps = list(range(128))
            
            # 1m preprocessed plot
            self.ax_csi_1.plot(timesteps, csi_1m_preprocessed, 'b-', linewidth=1.5)
            self.ax_csi_1.set_xlabel('Subcarrier Index')
            self.ax_csi_1.set_ylabel('Normalized CSI')
            self.ax_csi_1.grid(True, alpha=0.3)
            
            # 7m preprocessed plot
            self.ax_csi_2.plot(timesteps, csi_7m_preprocessed, 'r-', linewidth=1.5)
            self.ax_csi_2.set_xlabel('Subcarrier Index')
            self.ax_csi_2.set_ylabel('Normalized CSI')
            self.ax_csi_2.grid(True, alpha=0.3)
            
            # Refresh canvases
            self.canvas_csi_1.draw()
            self.canvas_csi_2.draw()
            
        except Exception as e:
            print(f"Error in fallback 2D preprocessed CSI plotting: {e}")
    
    def resize_frame(self, frame, max_width=650, max_height=400):
        """Resize frame to fill 1/4 of screen with high quality"""
        if frame is None:
            return None
            
        height, width = frame.shape[:2]
        
        # Calculate scaling factor to fill the area properly
        scale_w = max_width / width
        scale_h = max_height / height
        scale = min(scale_w, scale_h)
        
        # Resize frame with high quality interpolation
        new_width = int(width * scale)
        new_height = int(height * scale)
        resized_frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
        
        return resized_frame
    
    def cv2_to_tkinter(self, cv2_image):
        """Convert CV2 image to Tkinter PhotoImage with high quality"""
        if cv2_image is None:
            return None
            
        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL Image and then to PhotoImage
        from PIL import Image, ImageTk
        pil_image = Image.fromarray(rgb_image)
        photo = ImageTk.PhotoImage(pil_image)
        
        return photo
    
    def update_video_frames(self):
        """Update both video frames with high quality"""
        if not self.is_playing:
            return
            
        try:
            # Update 1m video
            if self.cap_1m and self.cap_1m.isOpened():
                ret1, frame1 = self.cap_1m.read()
                if ret1:
                    resized_frame1 = self.resize_frame(frame1)
                    if resized_frame1 is not None:
                        photo1 = self.cv2_to_tkinter(resized_frame1)
                        if photo1:
                            self.video_label_1m.configure(image=photo1)
                            self.video_label_1m.image = photo1
                else:
                    # End of video - loop back
                    self.cap_1m.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.current_frame = 0
            
            # Update 7m video
            if self.cap_7m and self.cap_7m.isOpened():
                ret2, frame2 = self.cap_7m.read()
                if ret2:
                    resized_frame2 = self.resize_frame(frame2)
                    if resized_frame2 is not None:
                        photo2 = self.cv2_to_tkinter(resized_frame2)
                        if photo2:
                            self.video_label_7m.configure(image=photo2)
                            self.video_label_7m.image = photo2
                else:
                    # End of video - loop back
                    self.cap_7m.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            # Update frame counter and slider
            self.current_frame += 1
            self.frame_var.set(self.current_frame)
            self.update_frame_info()
            
            # Update CSI plots synchronized with video
            self.update_csi_plots()
            
            # Schedule next frame update
            if self.is_playing:
                self.root.after(33, self.update_video_frames)  # ~30 FPS
                
        except Exception as e:
            print(f"Error updating frames: {e}")
    
    def toggle_play(self):
        """Toggle play/pause"""
        if self.is_playing:
            self.is_playing = False
            self.play_button.config(text="Play")
        else:
            self.is_playing = True
            self.play_button.config(text="Pause")
            self.update_video_frames()
    
    def stop_video(self):
        """Stop video playback"""
        self.is_playing = False
        self.play_button.config(text="Play")
        self.current_frame = 0
        
        # Reset videos to beginning
        if self.cap_1m and self.cap_1m.isOpened():
            self.cap_1m.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if self.cap_7m and self.cap_7m.isOpened():
            self.cap_7m.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
        self.frame_var.set(0)
        self.update_frame_info()
        
        # Reset CSI plots
        self.update_csi_plots()
    
    def seek_frame(self, value):
        """Seek to specific frame"""
        frame_num = int(float(value))
        self.current_frame = frame_num
        
        # Set both videos to the same frame
        if self.cap_1m and self.cap_1m.isOpened():
            self.cap_1m.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        if self.cap_7m and self.cap_7m.isOpened():
            self.cap_7m.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            
        self.update_frame_info()
        
        # Update CSI plots when seeking
        self.update_csi_plots()
        
        # Update frames if not playing
        if not self.is_playing:
            self.update_video_frames_once()
    
    def update_video_frames_once(self):
        """Update video frames once (for seeking) with high quality"""
        try:
            # Update 1m video
            if self.cap_1m and self.cap_1m.isOpened():
                ret1, frame1 = self.cap_1m.read()
                if ret1:
                    resized_frame1 = self.resize_frame(frame1)
                    if resized_frame1 is not None:
                        photo1 = self.cv2_to_tkinter(resized_frame1)
                        if photo1:
                            self.video_label_1m.configure(image=photo1)
                            self.video_label_1m.image = photo1
            
            # Update 7m video
            if self.cap_7m and self.cap_7m.isOpened():
                ret2, frame2 = self.cap_7m.read()
                if ret2:
                    resized_frame2 = self.resize_frame(frame2)
                    if resized_frame2 is not None:
                        photo2 = self.cv2_to_tkinter(resized_frame2)
                        if photo2:
                            self.video_label_7m.configure(image=photo2)
                            self.video_label_7m.image = photo2
                            
        except Exception as e:
            print(f"Error updating single frame: {e}")
    
    def run(self):
        """Start the application"""
        self.load_videos()
        # Initialize CSI plots
        self.update_csi_plots()
        self.root.mainloop()
    
    def __del__(self):
        """Cleanup resources"""
        if self.cap_1m:
            self.cap_1m.release()
        if self.cap_7m:
            self.cap_7m.release()

def main():
    # Video file paths
    video_1m_path = "outputs/image_1_sequence.mp4"
    video_7m_path = "outputs/image_7_sequence.mp4"
    
    # Create and run visualizer
    print("Starting CSI Video Visualizer with 3 CSI modes...")
    print("Modes: RSSI, Raw CSI, Preprocessed CSI")
    print("Synchronization: 25 packets/second with video")
    
    visualizer = VideoCSIVisualizer(video_1m_path, video_7m_path)
    visualizer.run()

if __name__ == "__main__":
    main()
