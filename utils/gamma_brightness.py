#!/usr/bin/env python3
"""
Gamma Correction Tool for dataset_100%
======================================

This script converts all images in dataset_100% folder using Gamma Correction
to simulate low-light environments following the paper methodology:

Formula: Adjusted_Value = (Pixel_Value / 255)^(1/gamma) × 255

Gamma values used:
- gamma = 0.05 (creates extremely dark images, simulating very low-light conditions)
- gamma = 0.5 (creates moderately dark images)

Maintains original folder structure and creates new datasets:
- dataset_gamma_0.05 (for extremely dark environment)
- dataset_gamma_0.5 (for moderately dark environment)

Author: AI Assistant
Date: September 14, 2025
"""

import os
import shutil
from pathlib import Path
import numpy as np
import time

# Try to import optional libraries
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Note: tqdm not installed. Progress bar will not be available.")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

if not HAS_CV2 and not HAS_PIL:
    print("ERROR: Neither OpenCV nor PIL is available. Please install one of them:")
    print("  pip install opencv-python")
    print("  or")
    print("  pip install Pillow")
    exit(1)

class GammaConverter:
    def __init__(self, source_folder, target_gamma_levels=None):
        """
        Initialize gamma correction converter
        
        Args:
            source_folder (str): Path to source dataset folder
            target_gamma_levels (dict): Dict of {suffix: gamma_value}
        """
        self.source_folder = Path(source_folder)
        self.target_gamma_levels = target_gamma_levels or {
            'gamma_0.05': 0.05,  # Extremely dark (simulates very low-light environment)
            'gamma_0.5': 0.5     # Moderately dark
        }
        
        # Supported image extensions
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        
        print("="*80)
        print("GAMMA CORRECTION TOOL FOR DATASET_100%")
        print("="*80)
        print(f"Source folder: {self.source_folder}")
        print(f"Target gamma levels: {self.target_gamma_levels}")
        print("Formula: Adjusted_Value = (Pixel_Value / 255)^(1/gamma) × 255")
        
    def check_folder_structure(self):
        """Check and analyze the folder structure"""
        print(f"\n" + "="*60)
        print("FOLDER STRUCTURE ANALYSIS")
        print("="*60)
        
        if not self.source_folder.exists():
            print(f"❌ Source folder does not exist: {self.source_folder}")
            return False
            
        # Analyze structure
        structure = {}
        total_images = 0
        
        for root, dirs, files in os.walk(self.source_folder):
            root_path = Path(root)
            relative_path = root_path.relative_to(self.source_folder)
            
            # Count image files
            image_files = [f for f in files if Path(f).suffix.lower() in self.image_extensions]
            
            if image_files:
                structure[str(relative_path)] = {
                    'image_count': len(image_files),
                    'other_files': [f for f in files if Path(f).suffix.lower() not in self.image_extensions],
                    'subdirs': dirs
                }
                total_images += len(image_files)
        
        print(f"� Found folder structure:")
        for path, info in structure.items():
            print(f"  📂 {path}/")
            print(f"    🖼️  Images: {info['image_count']}")
            if info['other_files']:
                print(f"    📄 Other files: {', '.join(info['other_files'])}")
            if info['subdirs']:
                print(f"    📁 Subdirs: {', '.join(info['subdirs'])}")
        
        print(f"\n📊 SUMMARY:")
        print(f"  Total images found: {total_images:,}")
        print(f"  Total conversions needed: {total_images * len(self.target_gamma_levels):,}")
        
        return total_images > 0
    
    def create_target_folders(self):
        """Create target folder structure"""
        print(f"\n" + "="*60)
        print("CREATING TARGET FOLDER STRUCTURE")
        print("="*60)
        
        base_path = self.source_folder.parent
        self.target_folders = {}
        
        for suffix, gamma in self.target_gamma_levels.items():
            target_name = f"dataset_{suffix}"
            target_path = base_path / target_name
            self.target_folders[suffix] = target_path
            
            # Create target folder if it doesn't exist
            if target_path.exists():
                print(f"⚠️  Target folder exists: {target_path}")
                response = input(f"Delete and recreate? (y/N): ").strip().lower()
                if response in ['y', 'yes']:
                    shutil.rmtree(target_path)
                    print(f"🗑️  Deleted existing folder: {target_path}")
                else:
                    print(f"⏭️  Skipping recreation of: {target_path}")
                    continue
            
            # Copy folder structure
            print(f"📁 Creating folder structure: {target_path}")
            shutil.copytree(self.source_folder, target_path, 
                          ignore=shutil.ignore_patterns('*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.tif'))
            
            print(f"✅ Created: {target_path}")
        
        return True
    
    def apply_gamma_correction(self, image_path, gamma_value, method='auto'):
        """
        Apply gamma correction to image using the paper's formula:
        Adjusted_Value = (Pixel_Value / 255)^(1/gamma) × 255
        
        Args:
            image_path (Path): Path to source image
            gamma_value (float): Gamma value for correction
            method (str): 'auto', 'opencv', or 'pil'
            
        Returns:
            numpy.ndarray: Gamma corrected image
        """
        try:
            # Auto-select method based on available libraries
            if method == 'auto':
                method = 'opencv' if HAS_CV2 else 'pil'
            
            if method == 'opencv' and HAS_CV2:
                # Use OpenCV for faster processing
                img = cv2.imread(str(image_path))
                if img is None:
                    raise ValueError(f"Could not load image: {image_path}")
                
                # Apply gamma correction: (pixel/255)^(1/gamma) * 255
                # Build lookup table for efficiency
                inv_gamma = 1.0 / gamma_value
                table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
                
                # Apply gamma correction using lookup table
                corrected = cv2.LUT(img, table)
                return corrected
            
            elif method == 'pil' and HAS_PIL:
                # Use PIL as alternative
                img = Image.open(image_path)
                img_array = np.array(img)
                
                # Apply gamma correction
                inv_gamma = 1.0 / gamma_value
                corrected = np.power(img_array / 255.0, inv_gamma) * 255.0
                corrected = np.clip(corrected, 0, 255).astype(np.uint8)
                return corrected
            
            else:
                raise ValueError(f"Method {method} not available or library not installed")
            
        except Exception as e:
            print(f"❌ Error processing {image_path}: {e}")
            return None
    
    def apply_brightness(self, image_path, brightness_factor, method='opencv'):
        """
        Apply brightness adjustment to image
        
        Args:
            image_path (Path): Path to source image
            brightness_factor (float): Brightness multiplication factor
            method (str): 'opencv' only
            
        Returns:
            numpy.ndarray: Adjusted image
        """
        try:
            # Use OpenCV for processing
            img = cv2.imread(str(image_path))
            if img is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Apply brightness by multiplying pixel values
            adjusted = img.astype(np.float32) * brightness_factor
            adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)
            return adjusted
            
        except Exception as e:
            print(f"❌ Error processing {image_path}: {e}")
            return None
    
    def process_images(self):
        """Process all images with gamma correction"""
        print(f"\n" + "="*60)
        print("GAMMA CORRECTION PROCESSING")
        print("="*60)
        
        # Collect all image files
        all_images = []
        for root, dirs, files in os.walk(self.source_folder):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in self.image_extensions:
                    all_images.append(file_path)
        
        total_conversions = len(all_images) * len(self.target_gamma_levels)
        print(f"📊 Processing {len(all_images)} images × {len(self.target_gamma_levels)} gamma levels = {total_conversions} conversions")
        
        # Progress tracking
        completed = 0
        errors = 0
        start_time = time.time()
        
        # Progress bar for overall progress (if tqdm available)
        if HAS_TQDM:
            progress_bar = tqdm(total=total_conversions, desc="Applying gamma correction", unit="img")
        else:
            progress_bar = None
            print("🔄 Processing images (no progress bar available)...")
        
        try:
            for i, image_path in enumerate(all_images):
                # Get relative path for maintaining structure
                relative_path = image_path.relative_to(self.source_folder)
                
                for suffix, gamma_value in self.target_gamma_levels.items():
                    target_folder = self.target_folders[suffix]
                    target_path = target_folder / relative_path
                    
                    # Ensure target directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Process image with gamma correction
                    corrected_image = self.apply_gamma_correction(image_path, gamma_value)
                    
                    if corrected_image is not None:
                        # Save corrected image
                        success = cv2.imwrite(str(target_path), corrected_image)
                        if success:
                            completed += 1
                        else:
                            print(f"❌ Failed to save: {target_path}")
                            errors += 1
                    else:
                        errors += 1
                    
                    # Update progress
                    if progress_bar:
                        progress_bar.update(1)
                        progress_bar.set_postfix({
                            'Completed': completed,
                            'Errors': errors,
                            'Current': f"γ={gamma_value}"
                        })
                    else:
                        # Simple progress without tqdm
                        current_progress = completed + errors
                        if current_progress % 100 == 0 or current_progress == total_conversions:
                            percentage = (current_progress / total_conversions) * 100
                            print(f"📈 Progress: {current_progress}/{total_conversions} ({percentage:.1f}%) - Completed: {completed}, Errors: {errors}")
        
        finally:
            if progress_bar:
                progress_bar.close()
        
        # Final statistics
        elapsed_time = time.time() - start_time
        print(f"\n" + "="*60)
        print("GAMMA CORRECTION COMPLETED")
        print("="*60)
        print(f"✅ Successfully processed: {completed:,} images")
        print(f"❌ Errors encountered: {errors:,} images")
        print(f"⏱️  Total time: {elapsed_time:.2f} seconds")
        print(f"🚀 Average speed: {completed/elapsed_time:.1f} images/second")
        
        return completed, errors
    
    def verify_results(self):
        """Verify the gamma correction results"""
        print(f"\n" + "="*60)
        print("VERIFICATION OF RESULTS")
        print("="*60)
        
        for suffix, target_folder in self.target_folders.items():
            if not target_folder.exists():
                print(f"❌ Target folder missing: {target_folder}")
                continue
            
            # Count images in target folder
            target_images = []
            for root, dirs, files in os.walk(target_folder):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix.lower() in self.image_extensions:
                        target_images.append(file_path)
            
            gamma_value = self.target_gamma_levels[suffix]
            print(f"📁 {suffix} (γ={gamma_value}):")
            print(f"  📂 Folder: {target_folder}")
            print(f"  🖼️  Images: {len(target_images):,}")
            
            # Sample verification - check a few images
            if target_images:
                sample_size = min(3, len(target_images))
                print(f"  🔍 Sample verification ({sample_size} images):")
                
                for i, img_path in enumerate(target_images[:sample_size]):
                    try:
                        img = cv2.imread(str(img_path))
                        if img is not None:
                            mean_brightness = np.mean(img)
                            print(f"    {i+1}. {img_path.name}: avg brightness = {mean_brightness:.1f}")
                        else:
                            print(f"    {i+1}. {img_path.name}: ❌ Could not load")
                    except Exception as e:
                        print(f"    {i+1}. {img_path.name}: ❌ Error: {e}")
        
        print(f"\n✅ Verification completed!")
    
    def run_conversion(self):
        """Run the complete gamma correction process"""
        print(f"🚀 Starting gamma correction process...")
        
        # Step 1: Check folder structure
        if not self.check_folder_structure():
            print("❌ Folder structure check failed. Exiting.")
            return False
        
        # Step 2: Create target folders
        if not self.create_target_folders():
            print("❌ Failed to create target folders. Exiting.")
            return False
        
        # Step 3: Process images
        completed, errors = self.process_images()
        
        # Step 4: Verify results
        self.verify_results()
        
        # Final summary
        print(f"\n" + "="*80)
        print("GAMMA CORRECTION SUMMARY")
        print("="*80)
        print(f"📂 Source: {self.source_folder}")
        
        for suffix, gamma in self.target_gamma_levels.items():
            target_folder = self.target_folders[suffix]
            print(f"📂 Target ({suffix}): {target_folder}")
        
        print(f"✅ Total conversions: {completed:,}")
        print(f"❌ Total errors: {errors:,}")
        
        if errors == 0:
            print(f"🎉 All gamma corrections completed successfully!")
        else:
            print(f"⚠️  {errors} errors occurred during conversion.")
        
        return errors == 0


def main():
    """Main function to run the gamma correction"""
    # Configuration
    source_folder = "/Users/macos/Downloads/Multi-CSI-Frame-App/dataset_100%"
    gamma_levels = {
        'gamma_0.05': 0.05,   # Extremely dark (simulates very low-light environment)
        'gamma_0.5': 0.5      # Moderately dark
    }
    
    # Create converter instance
    converter = GammaConverter(source_folder, gamma_levels)
    
    # Run conversion
    success = converter.run_conversion()
    
    if success:
        print(f"\n🎯 Gamma correction completed successfully!")
        print(f"📁 Check the following folders for results:")
        for suffix in gamma_levels.keys():
            target_name = f"dataset_{suffix}"
            target_path = Path(source_folder).parent / target_name
            print(f"   • {target_path}")
        
        print(f"\n📋 GAMMA CORRECTION DETAILS:")
        print(f"Formula used: Adjusted_Value = (Pixel_Value / 255)^(1/gamma) × 255")
        for suffix, gamma in gamma_levels.items():
            inv_gamma = 1.0 / gamma
            print(f"   • {suffix}: gamma={gamma}, invGamma={inv_gamma:.2f}")
            if gamma == 0.05:
                print(f"     → Simulates extremely low-light conditions")
            elif gamma == 0.5:
                print(f"     → Simulates moderately low-light conditions")
    else:
        print(f"\n💥 Gamma correction completed with errors. Please check the output above.")


if __name__ == "__main__":
    main()