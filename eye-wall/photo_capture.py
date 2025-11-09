#!/usr/bin/env python3
"""
Standalone Photo Button Test Script
Tests button press detection and photo capture independently from the eye tracking system.
Uploads captured photos to server via HTTP POST.
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

# HTTP requests for uploading
try:
    import requests
except ImportError:
    print("Error: requests not found. Install with: pip install requests")
    sys.exit(1)

# GPIO pin for photo capture button (BCM numbering)
GOOD_PHOTO_BUTTON_PIN = 27  # GPIO27, physical pin 13
BAD_PHOTO_BUTTON_PIN = 22  # GPIO22, physical pin 15

# GPIO pins for LED outputs (BCM numbering)
GOOD_LED_PIN = 18     # GPIO18, physical pin 12
BAD_LED_PIN = 23      # GPIO23, physical pin 16

# Photo settings
UPLOAD_URL = "http://192.168.8.226:8000/upload"
DEBOUNCE_TIME = 3.0  # Seconds between photos to prevent multiple captures


class PhotoButtonTester:
    def __init__(self):
        self.gpio_handle = None
        self.camera1 = None
        # self.camera2 = None
        self.current_frame1 = None
        # self.current_frame2 = None
        self.last_photo_time = 0.0
        self.photo_count = 0
        
        # LED control state
        self.good_led_on = False
        self.bad_led_on = False
        self.led_off_time = 0.0
        self.led_delay = 6.0  # 6 seconds
        
        # Setup
        self.setup_gpio()
        self.setup_cameras()
    
    def setup_gpio(self):
        """Initialize GPIO for button reading"""
        try:
            # Open the GPIO device
            self.gpio_handle = lgpio.gpiochip_open(0)
            
            # Set photo button as input with pull-up resistor
            lgpio.gpio_claim_input(self.gpio_handle, GOOD_PHOTO_BUTTON_PIN, lgpio.SET_PULL_UP)
            lgpio.gpio_claim_input(self.gpio_handle, BAD_PHOTO_BUTTON_PIN, lgpio.SET_PULL_UP)
            
            # Set LED pins as outputs
            lgpio.gpio_claim_output(self.gpio_handle, GOOD_LED_PIN)
            lgpio.gpio_claim_output(self.gpio_handle, BAD_LED_PIN)
            
            print(f"✓ GPIO initialized: Button on GPIO{GOOD_PHOTO_BUTTON_PIN} (physical pin 13)")
            print(f"✓ GPIO initialized: Button on GPIO{BAD_PHOTO_BUTTON_PIN} (physical pin 15)")
            print(f"✓ GPIO initialized: Good LED on GPIO{GOOD_LED_PIN} (physical pin 12)")
            print(f"✓ GPIO initialized: Bad LED on GPIO{BAD_LED_PIN} (physical pin 16)")
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
        
        # # Initialize Camera 2
        # try:
        #     self.camera2 = cv2.VideoCapture(1)
            
        #     if not self.camera2.isOpened():
        #         print("✗ Error: Could not open camera 2 at /dev/video1")
        #         sys.exit(1)
            
        #     # Set camera resolution
        #     self.camera2.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        #     self.camera2.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
        #     # Test frame capture
        #     ret, frame = self.camera2.read()
        #     if not ret or frame is None:
        #         print("✗ Error: Camera 2 opened but cannot read frames")
        #         sys.exit(1)
            
        #     print(f"✓ Camera 2 initialized: {int(self.camera2.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.camera2.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            
        # except Exception as e:
        #     print(f"✗ Error initializing camera 2: {e}")
        #     sys.exit(1)
    
    def is_good_button_pressed(self):
        """Check if photo button is pressed (active-low with pull-up)"""
        try:
            if self.gpio_handle is not None:
                good_state = lgpio.gpio_read(self.gpio_handle, GOOD_PHOTO_BUTTON_PIN)
                # Button is pressed when pin reads LOW (0)
                return good_state == 0
            return False
        except Exception as e:
            print(f"Error reading button: {e}")
            return False

    def is_bad_button_pressed(self):
        """Check if photo button is pressed (active-low with pull-up)"""
        try:
            if self.gpio_handle is not None:
                bad_state = lgpio.gpio_read(self.gpio_handle, BAD_PHOTO_BUTTON_PIN)
                # Button is pressed when pin reads LOW (0)
                return bad_state == 0
            return False
        except Exception as e:
            print(f"Error reading button: {e}")
            return False
    
    def set_led(self, led_pin, state, led_name):
        """Turn LED on (True) or off (False)"""
        try:
            if self.gpio_handle is not None:
                lgpio.gpio_write(self.gpio_handle, led_pin, 1 if state else 0)
                if led_name == "good":
                    self.good_led_on = state
                elif led_name == "bad":
                    self.bad_led_on = state
                print(f"✓ {led_name.capitalize()} LED {'ON' if state else 'OFF'} (3.3V, ~2mA)")
        except Exception as e:
            print(f"Error setting {led_name} LED: {e}")
    
    def update_led_control(self, current_time):
        """Handle LED control logic with 6-second delay"""
        # Check if either button is pressed
        good_button_pressed = self.is_good_button_pressed()
        bad_button_pressed = self.is_bad_button_pressed()
        
        # If either button is pressed and LEDs are currently on, turn both off
        if (good_button_pressed or bad_button_pressed) and (self.good_led_on or self.bad_led_on):
            print("Button pressed - turning both LEDs OFF")
            self.set_led(GOOD_LED_PIN, False, "good")
            self.set_led(BAD_LED_PIN, False, "bad")
            self.led_off_time = current_time
        
        # Check if 6 seconds have passed since LEDs were turned off
        if (not self.good_led_on or not self.bad_led_on) and self.led_off_time > 0:
            if current_time - self.led_off_time >= self.led_delay:
                print("6 seconds elapsed - turning both LEDs back ON")
                self.set_led(GOOD_LED_PIN, True, "good")
                self.set_led(BAD_LED_PIN, True, "bad")
                self.led_off_time = 0.0

    def take_photo(self, button_type: str):
        """Capture and upload photos from both cameras"""
        success_count = 0
        
        # Generate timestamp for this capture session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # # Upload from Camera 1
        try:
            if self.current_frame1 is not None:
                filename1 = f"eyebox_cam1_{timestamp}.jpg"
                # Encode image to JPEG format
                _, img_encoded = cv2.imencode('.jpg', self.current_frame1)
                # Upload to server
                files = {'photo': (filename1, img_encoded.tobytes(), 'image/jpeg')}
                # If it's a good photo use ?type=complimentary if it's bad use ?type=insult
                if button_type == 'good':
                    response = requests.post(UPLOAD_URL + '?type=complimentary', files=files, timeout=5)
                elif button_type == 'bad':
                    response = requests.post(UPLOAD_URL + '?type=insult', files=files, timeout=5)
                if response.status_code == 200:
                    print(f"✓ Camera 1 uploaded: {filename1}")
                    success_count += 1
                else:
                    print(f"✗ Camera 1 upload failed: HTTP {response.status_code}")
            else:
                print("✗ No frame available from camera 1")
        except Exception as e:
            print(f"✗ Error uploading camera 1: {e}")
        
        # # Upload from Camera 2
        # try:
        #     if self.current_frame2 is not None:
        #         filename2 = f"eyebox_cam2_{timestamp}.jpg"
        #         # Encode image to JPEG format
        #         _, img_encoded = cv2.imencode('.jpg', self.current_frame2)
        #         # Upload to server
        #         files = {'photo': (filename2, img_encoded.tobytes(), 'image/jpeg')}
        #         response = requests.post(UPLOAD_URL, files=files, timeout=5)
        #         if response.status_code == 200:
        #             print(f"✓ Camera 2 uploaded: {filename2}")
        #             success_count += 1
        #         else:
        #             print(f"✗ Camera 2 upload failed: HTTP {response.status_code}")
        #     else:
        #         print("✗ No frame available from camera 2")
        # except Exception as e:
        #     print(f"✗ Error uploading camera 2: {e}")
        
        if success_count > 0:
            self.photo_count += 1
            print(f"✓ Photo set #{self.photo_count} complete ({success_count}/2 cameras)")
            return True
        else:
            print("✗ Failed to upload any photos")
            return False
    
    def run(self):
        """Main loop to monitor button and capture photos"""
        print("\n" + "="*60)
        print("Photo Button Test - Ready!")
        print("="*60)
        print("Press the button to capture photos.")
        print("Press Ctrl+C to exit.\n")
        
        # Initialize LEDs to ON state
        print("Initializing LEDs...")
        self.set_led(GOOD_LED_PIN, True, "good")
        self.set_led(BAD_LED_PIN, True, "bad")
        print("LEDs ready - Both LEDs ON initially")
        
        try:
            good_button_was_pressed = False
            bad_button_was_pressed = False
            
            while True:
                current_time = time.time()
                
                # Continuously read from both cameras to keep buffers fresh
                # This ensures we always have the latest frames available
                ret1, self.current_frame1 = self.camera1.read()
                if not ret1:
                    print("✗ Warning: Failed to read frame from camera 1")
                
                # ret2, self.current_frame2 = self.camera2.read()
                # if not ret2:
                #     print("✗ Warning: Failed to read frame from camera 2")
                
                good_button_is_pressed = self.is_good_button_pressed()
                bad_button_is_pressed = self.is_bad_button_pressed()
                
                # Detect button press (edge detection)
                if (good_button_is_pressed or bad_button_is_pressed) and not (good_button_was_pressed or bad_button_was_pressed):
                    # Button just pressed
                    print("→ Button pressed detected!")
                    
                    # Check debounce
                    time_since_last = current_time - self.last_photo_time
                    if time_since_last > DEBOUNCE_TIME:
                        if good_button_is_pressed:
                            print("✓ Good button pressed")
                            self.take_photo('good')
                        elif bad_button_is_pressed:
                            print("✓ Bad button pressed")
                            self.take_photo('bad')
                        self.last_photo_time = current_time
                    else:
                        print(f"  ⏳ Debounced (wait {DEBOUNCE_TIME - time_since_last:.1f}s)")
                
                good_button_was_pressed = good_button_is_pressed
                bad_button_was_pressed = bad_button_is_pressed
                
                # Handle LED control
                self.update_led_control(current_time)
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)  # 100Hz polling
                
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        print("\nCleaning up...")
        
        # Turn off LEDs
        if self.gpio_handle is not None:
            try:
                lgpio.gpio_write(self.gpio_handle, GOOD_LED_PIN, 0)
                lgpio.gpio_write(self.gpio_handle, BAD_LED_PIN, 0)
                print("✓ LEDs turned off")
            except Exception:
                pass
        
        # Release cameras
        if self.camera1 is not None:
            self.camera1.release()
            print("✓ Camera 1 released")
        
        # if self.camera2 is not None:
        #     self.camera2.release()
        #     print("✓ Camera 2 released")
        
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
