import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk
import threading
import time

class RSSIVisualizer2D:
    def __init__(self):
        self.root = tk.Tk()
        # Animation control
        self.is_playing = False
        self.current_frame = 0
        self.animation_thread = None
        
        # Load data
        self.load_data()
        
        # Setup GUI
        self.setup_gui()
        
    def load_data(self):
        """Load RSSI data từ CSV files"""
        
        try:
            # Load 1 person data (csi_1.csv)
            df_1person = pd.read_csv('data_input/csi_input/csi_1.csv')
            self.data_1person = []
            
            for idx, row in df_1person.iterrows():
                try:
                    # Lấy giá trị RSSI
                    rssi_value = row['rssi']
                    
                    # Tạo DataFrame 2D: timestep và RSSI value
                    frame_data = pd.DataFrame({
                        'timestep': [idx],
                        'rssi': [rssi_value]
                    })
                    self.data_1person.append(frame_data)
                except:
                    continue
            
            # Load 7 people data (csi_7.csv)
            df_7people = pd.read_csv('data_input/csi_input/csi_7.csv')
            self.data_7people = []
            
            for idx, row in df_7people.iterrows():
                try:
                    # Lấy giá trị RSSI
                    rssi_value = row['rssi']
                    
                    # Tạo DataFrame 2D: timestep và RSSI value
                    frame_data = pd.DataFrame({
                        'timestep': [idx],
                        'rssi': [rssi_value]
                    })
                    self.data_7people.append(frame_data)
                except:
                    continue
            
            # Tạo dữ liệu tổng hợp cho hiển thị
            self.create_cumulative_data()
                
        except Exception as e:
            # Tạo dummy data
            self.create_dummy_data()
    
    def create_cumulative_data(self):
        """Tạo dữ liệu tổng hợp để hiển thị theo thời gian"""
        # Tạo arrays để lưu tất cả RSSI values theo thời gian
        self.rssi_1person_all = []
        self.rssi_7people_all = []
        
        # Thu thập tất cả RSSI values
        for frame_data in self.data_1person:
            if len(frame_data) > 0:
                self.rssi_1person_all.append(frame_data['rssi'].iloc[0])
        
        for frame_data in self.data_7people:
            if len(frame_data) > 0:
                self.rssi_7people_all.append(frame_data['rssi'].iloc[0])
    
    def create_dummy_data(self):
        """Tạo dummy RSSI data cho demo"""
        
        self.data_1person = []
        self.data_7people = []
        
        for i in range(100):
            # 1 person: RSSI pattern ít biến động
            rssi_1p = -60 + np.random.normal(0, 3)  # RSSI around -60 dBm
            
            df_1p = pd.DataFrame({
                'timestep': [i],
                'rssi': [rssi_1p]
            })
            self.data_1person.append(df_1p)
            
            # 7 people: RSSI pattern biến động nhiều hơn
            rssi_7p = -70 + np.random.normal(0, 8)  # RSSI around -70 dBm, more variation
            
            df_7p = pd.DataFrame({
                'timestep': [i],
                'rssi': [rssi_7p]
            })
            self.data_7people.append(df_7p)
        
        self.create_cumulative_data()
    
    def setup_gui(self):
        """Setup GUI cho RSSI visualization"""
        
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        # Controls
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        self.start_btn = tk.Button(control_frame, text="▶ Start", bg="lightgreen", 
                                  font=("Arial", 12, "bold"), command=self.start_animation)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(control_frame, text="⏸ Stop", bg="lightcoral", 
                                 font=("Arial", 12, "bold"), command=self.stop_animation)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.reset_btn = tk.Button(control_frame, text="Reset", bg="lightblue", 
                                  font=("Arial", 12, "bold"), command=self.reset_animation)
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        
        # Status
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(side=tk.RIGHT, padx=20)
        
        # Create figure - 2 plots side by side
        self.fig = plt.figure(figsize=(16, 8))
        self.fig.patch.set_facecolor('white')
        
        # 2 subplots
        self.ax1 = plt.subplot(1, 2, 1)  # 1 person
        self.ax2 = plt.subplot(1, 2, 2)  # 7 people
        
        # Embed in tkinter
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initial plot
        self.update_plots()
    
    def export_current_data(self):
        """Export dữ liệu RSSI hiện tại ra CSV"""
        try:
            # Export cumulative RSSI data up to current frame
            if self.current_frame > 0:
                # 1 person data
                timesteps_1p = list(range(self.current_frame + 1))
                rssi_values_1p = self.rssi_1person_all[:self.current_frame + 1]
                
                df_1p = pd.DataFrame({
                    'timestep': timesteps_1p,
                    'rssi': rssi_values_1p
                })
                
                filename_1p = f'rssi_frame_{self.current_frame}_1person.csv'
                df_1p.to_csv(filename_1p, index=False)
                
                # 7 people data
                timesteps_7p = list(range(self.current_frame + 1))
                rssi_values_7p = self.rssi_7people_all[:self.current_frame + 1]
                
                df_7p = pd.DataFrame({
                    'timestep': timesteps_7p,
                    'rssi': rssi_values_7p
                })
                
                filename_7p = f'rssi_frame_{self.current_frame}_7people.csv'
                df_7p.to_csv(filename_7p, index=False)
                
        except Exception as e:
            pass
    
    def update_plots(self):
        """Update plots với dữ liệu RSSI 2D"""
        try:
            # Clear plots
            self.ax1.clear()
            self.ax2.clear()
            
            # Check data availability
            if (self.current_frame >= len(self.data_1person) or 
                self.current_frame >= len(self.data_7people)):
                return
            
            # Get cumulative data up to current frame
            current_timesteps = list(range(self.current_frame + 1))
            
            if len(self.rssi_1person_all) > self.current_frame:
                current_rssi_1p = self.rssi_1person_all[:self.current_frame + 1]
            else:
                current_rssi_1p = []
                
            if len(self.rssi_7people_all) > self.current_frame:
                current_rssi_7p = self.rssi_7people_all[:self.current_frame + 1]
            else:
                current_rssi_7p = []
            
            # Plot 1: 1 Person - Timestep vs RSSI
            if len(current_rssi_1p) > 0:
                self.ax1.plot(current_timesteps[:len(current_rssi_1p)], current_rssi_1p, 
                             'b-', linewidth=2, marker='o', markersize=4)
                self.ax1.set_xlabel('Timestep')
                self.ax1.set_ylabel('RSSI (dBm)')
                self.ax1.grid(True, alpha=0.3)
                self.ax1.set_ylim(-90, -60)  # Narrower range for better visibility
            
            # Plot 2: 7 People - Timestep vs RSSI
            if len(current_rssi_7p) > 0:
                self.ax2.plot(current_timesteps[:len(current_rssi_7p)], current_rssi_7p, 
                             'r-', linewidth=2, marker='o', markersize=4)
                self.ax2.set_xlabel('Timestep')
                self.ax2.set_ylabel('RSSI (dBm)')
                self.ax2.grid(True, alpha=0.3)
                self.ax2.set_ylim(-90, -60)  # Narrower range for better visibility
            
            # Adjust layout and refresh
            plt.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def animation_loop(self):
        """Animation loop cho RSSI visualization"""
        while self.is_playing:
            try:
                max_frames = min(len(self.data_1person), len(self.data_7people))
                if max_frames > 0:
                    self.current_frame = (self.current_frame + 1) % max_frames
                    
                    # Update plots in main thread
                    self.root.after(0, self.update_plots)
                    
                    # 25 fps = 1/25 = 0.04 seconds
                    time.sleep(0.04)
                else:
                    self.is_playing = False
                    break
                    
            except Exception as e:
                self.is_playing = False
                break
    
    def start_animation(self):
        """Start animation"""
        if not self.is_playing:
            self.is_playing = True
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            
            self.animation_thread = threading.Thread(target=self.animation_loop)
            self.animation_thread.daemon = True
            self.animation_thread.start()
    
    def stop_animation(self):
        """Stop animation"""
        if self.is_playing:
            self.is_playing = False
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
    
    def reset_animation(self):
        """Reset animation"""
        was_playing = self.is_playing
        if self.is_playing:
            self.stop_animation()
        
        self.current_frame = 0
        self.update_plots()
        
        if was_playing:
            self.start_animation()
    
    def run(self):
        """Run the RSSI visualizer"""
        self.root.mainloop()

def main():
    """Main function"""    
    try:
        visualizer = RSSIVisualizer2D()
        visualizer.run()
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
