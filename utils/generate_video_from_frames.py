import cv2
import os
import glob
import numpy as np
from pathlib import Path

def generate_video_from_frames(frames_folder, output_video_path, fps=25, codec='mp4v'):
    """
    Generate video from frame images in a folder
    
    Args:
        frames_folder (str): Path to folder containing frame images
        output_video_path (str): Path for output video file
        fps (int): Frames per second for output video
        codec (str): Video codec to use ('mp4v', 'XVID', etc.)
    """
    
    # Get all jpg files in the folder and sort them
    frame_pattern = os.path.join(frames_folder, "*.jpg")
    frame_files = glob.glob(frame_pattern)
    frame_files.sort()  # Sort to ensure correct order
    
    if not frame_files:
        print(f"No .jpg files found in {frames_folder}")
        return False
    
    print(f"Found {len(frame_files)} frame files")
    print(f"First frame: {os.path.basename(frame_files[0])}")
    print(f"Last frame: {os.path.basename(frame_files[-1])}")
    
    # Read the first frame to get dimensions
    first_frame = cv2.imread(frame_files[0])
    if first_frame is None:
        print(f"Error reading first frame: {frame_files[0]}")
        return False
    
    height, width, channels = first_frame.shape
    print(f"Frame dimensions: {width}x{height}")
    
    # Define the codec and create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*codec)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_video_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Initialize video writer
    out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        print(f"Error: Could not open video writer with codec {codec}")
        return False
    
    print(f"Creating video: {output_video_path}")
    print(f"Settings: {fps} FPS, {codec} codec")
    
    # Process each frame
    frame_count = 0
    for i, frame_path in enumerate(frame_files):
        # Read frame
        frame = cv2.imread(frame_path)
        
        if frame is None:
            print(f"Warning: Could not read frame {frame_path}")
            continue
        
        # Ensure frame has the same dimensions as first frame
        if frame.shape[:2] != (height, width):
            frame = cv2.resize(frame, (width, height))
        
        # Write frame to video
        out.write(frame)
        frame_count += 1
        
        # Progress indicator
        if (i + 1) % 100 == 0:
            print(f"Processed {i + 1}/{len(frame_files)} frames")
    
    # Release everything
    out.release()
    cv2.destroyAllWindows()
    
    print(f"Video generation complete!")
    print(f"Generated video: {output_video_path}")
    print(f"Total frames written: {frame_count}")
    print(f"Video duration: {frame_count / fps:.2f} seconds")
    
    return True

def generate_videos_for_all_sequences(base_path, output_dir, fps=3.33):
    """
    Generate videos for all image sequences in dataset
    
    Args:
        base_path (str): Path to dataset_100%/train/images
        output_dir (str): Directory to save generated videos
        fps (int): Frames per second for output videos
    """
    
    if not os.path.exists(base_path):
        print(f"Error: Base path does not exist: {base_path}")
        return
    
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    # Find all image_* folders
    image_folders = [d for d in os.listdir(base_path) 
                    if os.path.isdir(os.path.join(base_path, d)) and d.startswith('image_')]
    image_folders.sort()
    
    if not image_folders:
        print(f"No image_* folders found in {base_path}")
        return
    
    print(f"Found {len(image_folders)} image sequences: {image_folders}")
    
    # Generate video for each sequence
    for folder_name in image_folders:
        print(f"\n--- Processing {folder_name} ---")
        
        frames_folder = os.path.join(base_path, folder_name)
        output_video_path = os.path.join(output_dir, f"{folder_name}_video.mp4")
        
        success = generate_video_from_frames(frames_folder, output_video_path, fps)
        
        if success:
            print(f"✓ Successfully created video for {folder_name}")
        else:
            print(f"✗ Failed to create video for {folder_name}")

def main():
    """Main function with different usage options"""
    
    # Base paths
    base_dataset_path = "/Users/macos/Downloads/Multi-CSI-Frame-App/data_counting/data_input/image_input"
    
    print("CSI Frame to Video Converter")
    print("=" * 50)
    
    # Option 1: Generate video for single sequence (image_0)
    print("\nOption 1: Generate video for image_7 sequence")
    image_0_path = os.path.join(base_dataset_path, "image_7")
    output_video_single = "/Users/macos/Downloads/Multi-CSI-Frame-App/outputs/image_7_sequence.mp4"
    
    if os.path.exists(image_0_path):
        print(f"Processing frames from: {image_0_path}")
        success = generate_video_from_frames(image_0_path, output_video_single, fps=25)
        
        if success:
            print(f"✓ Single sequence video created: {output_video_single}")
        else:
            print("✗ Failed to create single sequence video")
    else:
        print(f"Warning: {image_0_path} does not exist")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()