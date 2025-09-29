"""
2D CSI Visualizer - Simple Timestep vs Values
Hiển thị biểu đồ 2D đơn giản:
- Cột 1: Timestep (0-127) 
- Cột 2: Giá trị CSI tương ứng
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk
import threading
import time
import ast

class CSIVisualizer2D:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CSI 2D Visualizer - Timestep vs Values")
        self.root.geometry("1200x800")
        
        # Animation control
        self.is_playing = False
        self.current_frame = 0
        self.animation_thread = None
        self.fps = 25  # Data processing speed: 25 frames per second
        self.frame_delay = 1.0 / self.fps  # Delay between data frames (0.04 seconds)
        self.display_counter = 0  # Counter for display updates
        self.display_interval = 25  # Display every 25 frames (1 second)
        self.last_frame_time = 0  # For precise timing
        
        # Load data
        self.load_data()
        
        # Setup GUI
        self.setup_gui()
        
    def load_data(self):
        """Load CSI data và chuyển thành format 2D: timestep (0-127) vs values"""
        
        try:
            # Load 1 person data (csi_1.csv)
            df_1person = pd.read_csv('/Users/macos/Downloads/Multi-CSI-Frame-App/dataset_100%/train/csi/csi_0.csv')
            self.data_1person = []
            
            for idx, row in df_1person.iterrows():
                try:
                    csi_data = ast.literal_eval(row['data'])
                    # Lấy 128 giá trị đầu
                    values = csi_data[:128]
                    # Tạo timestep từ 0-127
                    timesteps = list(range(len(values)))
                    
                    # Tạo DataFrame 2D: timestep và value
                    frame_data = pd.DataFrame({
                        'timestep': timesteps,
                        'value': values
                    })
                    self.data_1person.append(frame_data)
                except:
                    continue
            
            # Load 7 people data (csi_7.csv)
            df_7people = pd.read_csv('data_counting/dataset_final/train/csi/csi_7.csv')
            self.data_7people = []
            
            for idx, row in df_7people.iterrows():
                try:
                    csi_data = ast.literal_eval(row['data'])
                    # Lấy 128 giá trị đầu
                    values = csi_data[:128]
                    # Tạo timestep từ 0-127
                    timesteps = list(range(len(values)))
                    
                    # Tạo DataFrame 2D: timestep và value
                    frame_data = pd.DataFrame({
                        'timestep': timesteps,
                        'value': values
                    })
                    self.data_7people.append(frame_data)
                except:
                    continue
                    
            # Hiển thị sample data
            if len(self.data_1person) > 0:
                pass
            
        except Exception as e:
            # Create dummy 2D data for demo
            self.create_dummy_2d_data()
    
    def create_dummy_2d_data(self):
        """Tạo dummy data 2D cho demo"""
        
        self.data_1person = []
        self.data_7people = []
        
        for i in range(100):
            # 1 person: pattern đơn giản
            timesteps = list(range(128))
            values_1p = [np.sin(t * 0.1) * 10 + np.random.normal(0, 2) for t in timesteps]
            
            df_1p = pd.DataFrame({
                'timestep': timesteps,
                'value': values_1p
            })
            self.data_1person.append(df_1p)
            
            # 7 people: pattern phức tạp hơn
            values_7p = [np.sin(t * 0.2) * 20 + np.random.normal(0, 5) for t in timesteps]
            
            df_7p = pd.DataFrame({
                'timestep': timesteps,
                'value': values_7p
            })
            self.data_7people.append(df_7p)
    
    
    def setup_gui(self):
        """Setup GUI cho hiển thị 2D: timestep vs values"""
        
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        title_label = ttk.Label(title_frame, 
                               text="CSI 2D Visualization: Timestep (0-127) vs Values", 
                               font=("Arial", 16, "bold"))
        title_label.pack()
        
        # Controls
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        
        self.start_btn = tk.Button(control_frame, text="▶ Start", bg="lightgreen", 
                                  font=("Arial", 12, "bold"), command=self.start_animation)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(control_frame, text="⏸ Stop", bg="lightcoral", 
                                 font=("Arial", 12, "bold"), command=self.stop_animation)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.reset_btn = tk.Button(control_frame, text="🔄 Reset", bg="lightblue", 
                                  font=("Arial", 12, "bold"), command=self.reset_animation)
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        
        # Export button
        self.export_btn = tk.Button(control_frame, text="💾 Export Current", bg="lightyellow", 
                                   font=("Arial", 12, "bold"), command=self.export_current_data)
        self.export_btn.pack(side=tk.LEFT, padx=15)
        
        # Speed controls
        speed_frame = ttk.Frame(control_frame)
        speed_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(speed_frame, text="Speed (fps):", font=("Arial", 10)).pack(side=tk.LEFT)
        self.speed_var = tk.StringVar(value="25")
        self.speed_entry = ttk.Entry(speed_frame, textvariable=self.speed_var, width=5)
        self.speed_entry.pack(side=tk.LEFT, padx=5)
        self.speed_entry.bind('<Return>', self.update_speed)
        
        self.speed_btn = tk.Button(speed_frame, text="Set", bg="lightgray", 
                                  font=("Arial", 10), command=self.update_speed)
        self.speed_btn.pack(side=tk.LEFT, padx=2)
        
        # Status
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(side=tk.RIGHT, padx=20)
        
        self.frame_label = ttk.Label(status_frame, text="Frame: 0", font=("Arial", 12, "bold"))
        self.frame_label.pack(side=tk.LEFT, padx=10)
        
        # Create figure - 2 plots side by side for 2D visualization
        self.fig = plt.figure(figsize=(16, 8))
        self.fig.patch.set_facecolor('white')
        
        # 2 subplots for 2D visualization
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
        """Export dữ liệu frame hiện tại ra CSV"""
        try:
            if (self.current_frame < len(self.data_1person) and 
                self.current_frame < len(self.data_7people)):
                
                # Export 1 person data
                data_1p = self.data_1person[self.current_frame]
                filename_1p = f'frame_{self.current_frame}_1person_2d.csv'
                data_1p.to_csv(filename_1p, index=False)
                
                # Export 7 people data
                data_7p = self.data_7people[self.current_frame]
                filename_7p = f'frame_{self.current_frame}_7people_2d.csv'
                data_7p.to_csv(filename_7p, index=False)
                
        except Exception as e:
            pass
    
    def update_plots(self):
        """Update plots với dữ liệu 2D: timestep vs values"""
        try:
            # Clear plots
            self.ax1.clear()
            self.ax2.clear()
            
            # Check data availability
            if (self.current_frame >= len(self.data_1person) or 
                self.current_frame >= len(self.data_7people)):
                return
            
            # Get current frame data
            data_1p = self.data_1person[self.current_frame]
            data_7p = self.data_7people[self.current_frame]
            
            # Plot 1: 1 Person - Timestep vs Value
            self.ax1.plot(data_1p['timestep'], data_1p['value'], 'b-', linewidth=2, marker='o', markersize=3)
            self.ax1.set_title(f'1 Person - Frame {self.current_frame}\nTimestep (0-127) vs CSI Values', 
                              fontsize=12, fontweight='bold')
            self.ax1.set_xlabel('Timestep')
            self.ax1.set_ylabel('CSI Value')
            self.ax1.grid(True, alpha=0.3)
            self.ax1.set_xlim(0, 127)
            
            # Plot 2: 7 People - Timestep vs Value
            self.ax2.plot(data_7p['timestep'], data_7p['value'], 'r-', linewidth=2, marker='o', markersize=3)
            self.ax2.set_title(f'7 People - Frame {self.current_frame}\nTimestep (0-127) vs CSI Values', 
                              fontsize=12, fontweight='bold')
            self.ax2.set_xlabel('Timestep')
            self.ax2.set_ylabel('CSI Value')
            self.ax2.grid(True, alpha=0.3)
            self.ax2.set_xlim(0, 127)
            
            # Update frame label
            self.frame_label.config(text=f"Frame: {self.current_frame}")
            
            # Adjust layout and refresh
            plt.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def animation_loop(self):
        """Animation loop: 25 pkt/s data processing, display every 1 second"""
        self.last_frame_time = time.time()
        
        while self.is_playing:
            try:
                max_frames = min(len(self.data_1person), len(self.data_7people))
                if max_frames > 0:
                    # Calculate precise timing for 25 fps data processing
                    current_time = time.time()
                    elapsed = current_time - self.last_frame_time
                    
                    if elapsed >= self.frame_delay:
                        # Update data frame (25 fps)
                        self.current_frame = (self.current_frame + 1) % max_frames
                        self.display_counter += 1
                        
                        # Only update display every 25 frames (1 second)
                        if self.display_counter >= self.display_interval:
                            self.root.after(0, self.update_plots)
                            self.display_counter = 0  # Reset counter
                        
                        # Update timing for next frame
                        self.last_frame_time = current_time
                    
                    # Small sleep to prevent excessive CPU usage
                    time.sleep(0.001)  # 1ms sleep
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
    
    def update_speed(self, event=None):
        """Update animation speed"""
        try:
            new_fps = float(self.speed_var.get())
            if new_fps > 0 and new_fps <= 100:  # Limit to reasonable range
                self.fps = new_fps
                self.frame_delay = 1.0 / self.fps
            else:
                self.speed_var.set(str(self.fps))  # Reset to current value
        except ValueError:
            self.speed_var.set(str(self.fps))  # Reset to current value
    
    def reset_animation(self):
        """Reset animation"""
        was_playing = self.is_playing
        if self.is_playing:
            self.stop_animation()
        
        self.current_frame = 0
        self.update_plots()
        
        if was_playing:
            self.start_animation()
        
        print("🔄 Animation reset")
    
    def run(self):
        """Run the 2D CSI visualizer"""
        self.root.mainloop()

def main():
    """Main function"""    
    try:
        visualizer = CSIVisualizer2D()
        visualizer.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
