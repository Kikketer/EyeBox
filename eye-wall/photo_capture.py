#!/usr/bin/env python3
"""
Standalone Photo Button Test Script
Tests button press detection and photo capture independently from the eye tracking system.
"""

import os
import sys
import time
from datetime import datetime

# GPIO imports
try:
    import lgpio
except ImportError:
    print("Error: lgpio not found. Install with: pip install lgpio")
    sys.exit(1)

# OpenCV imports
try:
    import cv2
except ImportError:
    print("Error: opencv-python not found. Install with: pip install opencv-python")
    sys.exit(1)

# GPIO pin for photo capture button (BCM numbering)
PHOTO_BUTTON_PIN = 27  # GPIO27, physical pin 13

# Photo settings
PHOTO_DIR = os.path.join(os.getcwd(), "photos")
DEBOUNCE_TIME = 1.0  # Seconds between photos to prevent multiple captures


class PhotoButtonTester:
    def __init__(self):
        self.gpio_handle = None
        self.camera1 = None
        self.camera2 = None
        self.current_frame1 = None
        self.current_frame2 = None
        self.last_photo_time = 0.0
        self.photo_count = 0
        
        # Setup
        self.setup_photo_directory()
        self.setup_gpio()
        self.setup_cameras()
    
    def setup_photo_directory(self):
        """Create photos directory if it doesn't exist"""
        try:
            os.makedirs(PHOTO_DIR, exist_ok=True)
            print(f"✓ Photo directory ready: {PHOTO_DIR}")
        except Exception as e:
            print(f"✗ Error creating photo directory: {e}")
            sys.exit(1)
    
    def setup_gpio(self):
        """Initialize GPIO for button reading"""
        try:
            # Open the GPIO device
            self.gpio_handle = lgpio.gpiochip_open(0)
            
            # Set photo button as input with pull-up resistor
            lgpio.gpio_claim_input(self.gpio_handle, PHOTO_BUTTON_PIN, lgpio.SET_PULL_UP)
            
            print(f"✓ GPIO initialized: Button on GPIO{PHOTO_BUTTON_PIN} (physical pin 13)")
            return True
            
        except Exception as e:
            print(f"✗ Error setting up GPIO: {e}")
            print("\nTroubleshooting:")
            print("1. Run with sudo: sudo python3 test-photo-button.py")
            print("2. Install lgpio: pip install lgpio")
            print("3. Add user to gpio group: sudo usermod -a -G gpio $USER")
            print("4. Reboot after adding to gpio group")
            sys.exit(1)
    
    def setup_cameras(self):
        """Initialize both USB webcams"""
        # Initialize Camera 1
        try:
            self.camera1 = cv2.VideoCapture(0)
            
            if not self.camera1.isOpened():
                print("✗ Error: Could not open camera 1 at /dev/video0")
                sys.exit(1)
            
            # Set camera resolution
            self.camera1.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.camera1.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
            # Test frame capture
            ret, frame = self.camera1.read()
            if not ret or frame is None:
                print("✗ Error: Camera 1 opened but cannot read frames")
                sys.exit(1)
            
            print(f"✓ Camera 1 initialized: {int(self.camera1.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.camera1.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            
        except Exception as e:
            print(f"✗ Error initializing camera 1: {e}")
            sys.exit(1)
        
        # Initialize Camera 2
        try:
            self.camera2 = cv2.VideoCapture(1)
            
            if not self.camera2.isOpened():
                print("✗ Error: Could not open camera 2 at /dev/video1")
                sys.exit(1)
            
            # Set camera resolution
            self.camera2.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.camera2.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
            # Test frame capture
            ret, frame = self.camera2.read()
            if not ret or frame is None:
                print("✗ Error: Camera 2 opened but cannot read frames")
                sys.exit(1)
            
            print(f"✓ Camera 2 initialized: {int(self.camera2.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.camera2.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            
        except Exception as e:
            print(f"✗ Error initializing camera 2: {e}")
            sys.exit(1)
    
    def is_button_pressed(self):
        """Check if photo button is pressed (active-low with pull-up)"""
        try:
            if self.gpio_handle is not None:
                state = lgpio.gpio_read(self.gpio_handle, PHOTO_BUTTON_PIN)
                # Button is pressed when pin reads LOW (0)
                return state == 0
            return False
        except Exception as e:
            print(f"Error reading button: {e}")
            return False
    
    def take_photo(self):
        """Capture and save photos from both cameras"""
        success_count = 0
        
        # Generate timestamp for this capture session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save from Camera 1
        try:
            if self.current_frame1 is not None:
                filename1 = f"eyebox_cam1_{timestamp}.jpg"
                filepath1 = os.path.join(PHOTO_DIR, filename1)
                cv2.imwrite(filepath1, self.current_frame1)
                print(f"✓ Camera 1 saved: {filename1}")
                success_count += 1
            else:
                print("✗ No frame available from camera 1")
        except Exception as e:
            print(f"✗ Error saving camera 1: {e}")
        
        # Save from Camera 2
        try:
            if self.current_frame2 is not None:
                filename2 = f"eyebox_cam2_{timestamp}.jpg"
                filepath2 = os.path.join(PHOTO_DIR, filename2)
                cv2.imwrite(filepath2, self.current_frame2)
                print(f"✓ Camera 2 saved: {filename2}")
                success_count += 1
            else:
                print("✗ No frame available from camera 2")
        except Exception as e:
            print(f"✗ Error saving camera 2: {e}")
        
        if success_count > 0:
            self.photo_count += 1
            print(f"✓ Photo set #{self.photo_count} complete ({success_count}/2 cameras)")
            return True
        else:
            print("✗ Failed to save any photos")
            return False
    
    def run(self):
        """Main loop to monitor button and capture photos"""
        print("\n" + "="*60)
        print("Photo Button Test - Ready!")
        print("="*60)
        print("Press the button to capture photos.")
        print("Press Ctrl+C to exit.\n")
        
        try:
            button_was_pressed = False
            
            while True:
                current_time = time.time()
                
                # Continuously read from both cameras to keep buffers fresh
                # This ensures we always have the latest frames available
                ret1, self.current_frame1 = self.camera1.read()
                if not ret1:
                    print("✗ Warning: Failed to read frame from camera 1")
                
                ret2, self.current_frame2 = self.camera2.read()
                if not ret2:
                    print("✗ Warning: Failed to read frame from camera 2")
                
                button_is_pressed = self.is_button_pressed()
                
                # Detect button press (edge detection)
                if button_is_pressed and not button_was_pressed:
                    # Button just pressed
                    print("→ Button pressed detected!")
                    
                    # Check debounce
                    time_since_last = current_time - self.last_photo_time
                    if time_since_last > DEBOUNCE_TIME:
                        self.take_photo()
                        self.last_photo_time = current_time
                    else:
                        print(f"  ⏳ Debounced (wait {DEBOUNCE_TIME - time_since_last:.1f}s)")
                
                button_was_pressed = button_is_pressed
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)  # 100Hz polling
                
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        print("\nCleaning up...")
        
        # Release cameras
        if self.camera1 is not None:
            self.camera1.release()
            print("✓ Camera 1 released")
        
        if self.camera2 is not None:
            self.camera2.release()
            print("✓ Camera 2 released")
        
        # Close GPIO
        if self.gpio_handle is not None:
            try:
                lgpio.gpiochip_close(self.gpio_handle)
                print("✓ GPIO closed")
            except Exception:
                pass
        
        print(f"\nTotal photo sets captured: {self.photo_count}")
        print("Done!")


if __name__ == "__main__":
    tester = PhotoButtonTester()
    tester.run()
