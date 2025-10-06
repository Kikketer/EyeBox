#!/usr/bin/env python3
"""
Basic Eye Control for EyeBox
Controls eye movements based on horizontal position from Kinect.
All eyes move together based on X position of the closest point.
"""

import time
import math
import sys
import argparse
import board
import threading
import busio
import numpy as np
from adafruit_pca9685 import PCA9685
from consts import consts

# Kinect imports
try:
    import freenect
except ImportError:
    print("Error: freenect (libfreenect Python bindings) not found.")
    print("Install libfreenect and its Python bindings. For example:")
    print("  sudo apt-get install libfreenect0.5 libfreenect-dev")
    print("  pip3 install freenect")
    sys.exit(1)

# Eye zone definitions (board.eye format)
# TODO Use zones, the kinect doesn't detect all that close so the entire wall looking
# in the same direction doesn't actually look all that bad
# LEFT_ZONE = [1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 6.1, 6.2, 6.3, 6.4, 
#              6.5, 6.6, 6.7, 6.8, 7.4, 7.2, 7.3, 6.5, 9.6, 9.5, 9.3, 5.7]
# RIGHT_ZONE = [3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 2.1, 2.2, 2.3, 2.4, 
#               2.5, 2.6, 2.7, 2.8, 4.6, 8.1, 8.2, 8.4, 8.6, 4.5, 4.2, 5.6, 
#               8.7, 5.3, 5.2, 8.8, 8.5]

# Kinect frame dimensions (from depth-check.py)
KINECT_WIDTH = 640
KINECT_HEIGHT = 480

MIN_DEPTH_MM = 400
MAX_DEPTH_MM = 900

class EyeController:
    def __init__(self, debug=False):
        self.boards = []
        self.eye_zones = {}  # Maps eye_id (board.eye) to zone ('left', 'right', 'center')
        self.debug = debug
        self.last_command_time = 0  # For enforcing delay between commands
        self.last_depth_data = (None, None, None, None)  # (depth, x, y, depth_frame)
        self.initialize_eyes()
        
    def initialize_eyes(self):
        """Initialize PCA9685 controllers and eye zone mapping"""
        # Initialize I2C bus
        i2c = busio.I2C(board.SCL, board.SDA)
        
        # Initialize PCA9685 boards (from synced-eyes.py)
        BOARD_ADDRESSES = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48]
        for i, address in enumerate(BOARD_ADDRESSES):
            try:
                pca = PCA9685(i2c, address=address)
                pca.frequency = 50  # Standard servo frequency (50Hz)
                self.boards.append(pca)
                print(f"Initialized board {i+1} at 0x{address:02X}")
            except Exception as e:
                print(f"Warning: Could not initialize board at 0x{address:02X}: {e}")
        
        # Create eye zone mapping
        for eye_id in LEFT_ZONE:
            self.eye_zones[eye_id] = 'left'
        for eye_id in RIGHT_ZONE:
            self.eye_zones[eye_id] = 'right'
        
        # Center zone includes all eyes not in left or right zones
        for board_num in range(1, 10):  # Boards 1-9
            for eye_num in range(1, 9):  # 8 eyes per board
                eye_id = float(f"{board_num}.{eye_num}")
                if eye_id not in self.eye_zones:
                    self.eye_zones[eye_id] = 'center'
        
        print(f"Initialized {len(self.eye_zones)} eyes in zones: "
              f"Left={len(LEFT_ZONE)}, Right={len(RIGHT_ZONE)}, "
              f"Center={len(self.eye_zones) - len(LEFT_ZONE) - len(RIGHT_ZONE)}")
    
    def get_depth_mm_supported(self):
        """Return True if freenect exposes millimeters depth format."""
        return hasattr(freenect, "DEPTH_MM")

    def read_kinect_data(self):
        """Read a single depth frame and find closest point within valid range."""
        try:
            # Read depth frame
            if self.get_depth_mm_supported():
                fmt = freenect.DEPTH_MM
                depth, _ts = freenect.sync_get_depth(format=fmt)
                depth = depth.astype(np.uint16, copy=False)
            else:
                # Fallback to raw 11-bit values
                depth, _ts = freenect.sync_get_depth(format=freenect.DEPTH_11BIT)
                depth = depth.astype(np.uint16, copy=False)
            
            # Create a mask for valid depth values within our range
            valid_mask = (depth >= MIN_DEPTH_MM) & (depth <= MAX_DEPTH_MM)
            
            # If no valid points found, return None
            if not np.any(valid_mask):
                return None, None, None, (depth if self.debug else None)
                
            # Find the closest valid point
            min_depth = np.min(depth[valid_mask])
            y, x = np.where((depth == min_depth) & valid_mask)
            
            # Return the first point if found
            if len(y) > 0 and len(x) > 0:
                # Calculate the center of mass of all points at min_depth for smoother tracking
                points = np.argwhere((depth == min_depth) & valid_mask)
                if len(points) > 0:
                    center = np.mean(points, axis=0).astype(int)
                    return int(min_depth), center[1], center[0], (depth if self.debug else None)
                
        except Exception as e:
            print(f"Error reading from Kinect: {e}")
            
        return None, None, None, None
    
    def _enforce_delay(self):
        """Ensure at least 5ms between commands to prevent signal conflicts"""
        current_time = time.time()
        time_since_last = current_time - self.last_command_time
        if time_since_last < 0.005:  # 5ms = 0.005 seconds
            time.sleep(0.005 - time_since_last)
        self.last_command_time = time.time()

    def _shutdown_servo(self, pca, h_channel, v_channel):
        """Helper function to shut down a single servo after delay"""
        pca.channels[h_channel].duty_cycle = 0
        pca.channels[v_channel].duty_cycle = 0
        
    def move_all_eyes(self, x, y):
        """Move all eyes to the same position with proper timing"""
        if not self.boards:
            return

        print(f"Moving all eyes to position: H={x}, V={y}")
        
        # Move all eyes to the new position
        for board_num, pca in enumerate(self.boards):
            for eye_num in range(8):  # 8 eyes per board
                up_down_channel = eye_num * 2
                left_right_channel = eye_num * 2 + 1
                
                # Set up/down position with 10ms delay
                self._enforce_delay()
                pca.channels[up_down_channel].duty_cycle = pwm_to_duty_cycle(y)
                
                # Set left/right position with 10ms delay
                self._enforce_delay()
                pca.channels[left_right_channel].duty_cycle = pwm_to_duty_cycle(x)
                
                # Schedule servo shutdown after 50ms without blocking
                threading.Timer(0.05, self._shutdown_servo, 
                              args=(pca, left_right_channel, up_down_channel)).start()

    def run(self):
        """Main tracking loop"""
        print("Starting eye tracking. Press Ctrl+C to exit.")
        
        try:
            while True:
                current_time = time.time()
                
                depth, x, y, depth_frame = self.read_kinect_data()
                if depth is not None and x is not None and y is not None:
                    self.last_depth_data = (depth, x, y, depth_frame)
                
                if depth is not None and x is not None and y is not None:
                    if self.debug and depth_frame is not None:
                        # Clear screen and move cursor to top-left
                        print("\033[H\033[J", end='')
                        # Debug: Print focus point info
                        x_pct = (x / KINECT_WIDTH)
                        y_pct = 1 - (y / KINECT_HEIGHT)
                        print(f"\rFocus: X={x:3d} ({x_pct}), Y={y:3d} ({y_pct}), Depth={depth:4d}mm")
                    
                    # Track positions for debug output
                    positions = {'left': None, 'center': None, 'right': None}
                    
                    # Percentage of the movement applied to min/max of the eyes
                    x_pos = ((consts.eyeLeftExtreme + consts.eyeRightExtreme) * x_pct) + (consts.midpoint - consts.eyeLeftExtreme)
                    y_pos = ((consts.eyeDownExtreme + consts.eyeUpExtreme) * y_pct) + (consts.midpoint - consts.eyeDownExtreme)
                    
                    print(f"\rMove eyes: {x_pos}, {y_pos}", end='', flush=True)
                    self.move_all_eyes(x_pos, y_pos)
                                    
                # Small delay to prevent excessive CPU usage and control update rate
                time.sleep(0.02)  # ~50 updates per second for smooth eye movements
                
        except KeyboardInterrupt:
            print("\nStopping eye tracking...")
        finally:
            # Clean up Kinect
            try:
                freenect.sync_stop()
            except Exception:
                pass
            print("Cleanup complete.")

def pwm_to_duty_cycle(pwm_value):
    """
    Convert PWM value to duty cycle for PCA9685
    PCA9685 uses 16-bit resolution (0-65535)
    Standard servo PWM range is typically 1-2ms pulse width
    """
    # Map PWM value (0-4095) to duty cycle (0-65535)
    # This is a simple linear mapping, adjust as needed for your servos
    return int(pwm_value * 16)  # 4096 * 16 = 65536

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Basic eye tracking with Kinect')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()
    
    controller = EyeController(debug=args.debug)
    controller.run()