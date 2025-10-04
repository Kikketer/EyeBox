#!/usr/bin/env python3
"""
Focus Eye Control for EyeBox
Controls eye movements based on depth and position of closest object from Kinect.
Eyes in different zones will react differently to the tracked point.
"""

import time
import math
import sys
import argparse
import board
import busio
import lgpio
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
LEFT_ZONE = [1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 6.1, 6.2, 6.3, 6.4, 
             6.5, 6.6, 6.7, 6.8, 7.4, 7.2, 7.3, 6.5, 9.6, 9.5, 9.3, 5.7]
RIGHT_ZONE = [3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 2.1, 2.2, 2.3, 2.4, 
              2.5, 2.6, 2.7, 2.8, 4.6, 8.1, 8.2, 8.4, 8.6, 4.5, 4.2, 5.6, 
              8.7, 5.3, 5.2, 8.8, 8.5]

# Kinect frame dimensions (from depth-check.py)
KINECT_WIDTH = 640
KINECT_HEIGHT = 480

# Depth range (in mm)
MIN_DEPTH_MM = 500
MAX_DEPTH_MM = 5000

class EyeController:
    def __init__(self, debug=False):
        self.boards = []
        self.eye_zones = {}  # Maps eye_id (board.eye) to zone ('left', 'right', 'center')
        self.debug = debug
        self.initialize_eyes()
        self.initialize_kinect()
        
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

    def get_depth_map_ascii(self, depth, width=40, height=15):
        """Convert depth frame to ASCII art representation"""
        if depth is None:
            return "No depth data"
            
        # Downsample the depth frame
        h, w = depth.shape
        step_x = w // width
        step_y = h // height
        
        # Skip if frame is too small
        if step_x == 0 or step_y == 0:
            return "Frame too small"
            
        # Create downsampled grid
        grid = []
        for y in range(0, h - step_y, step_y):
            row = []
            for x in range(0, w - step_x, step_x):
                # Get the minimum depth in this cell
                cell = depth[y:y+step_y, x:x+step_x]
                valid_depths = cell[cell > 0]
                if len(valid_depths) > 0:
                    row.append(np.min(valid_depths))
                else:
                    row.append(0)
            if row:  # Only add non-empty rows
                grid.append(row)
        
        if not grid or not grid[0]:
            return "No valid depth data"
            
        # Convert to ASCII
        chars = ' .-+*#%@'  # From light to dark
        max_depth = max(max(row) for row in grid) if any(any(row) for row in grid) else 1
        
        ascii_art = []
        for row in grid:
            line = []
            for d in row:
                if d == 0:
                    line.append(' ')
                else:
                    # Map depth to character (darker = closer)
                    idx = min(int((d / max_depth) * (len(chars) - 1)), len(chars) - 1)
                    line.append(chars[idx])
            ascii_art.append(''.join(line))
            
        return '\n'.join(ascii_art)
    
    def read_kinect_data(self):
        """Read a single depth frame and find closest point."""
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
            
            # Find closest point
            valid_depths = depth[depth > 0]
            if len(valid_depths) == 0:
                return None, None, None, (depth if self.debug else None)
                
            min_depth = valid_depths.min()
            y, x = np.where(depth == min_depth)
            
            if len(y) > 0 and len(x) > 0:
                return int(min_depth), int(x[0]), int(y[0]), (depth if self.debug else None)
                
        except Exception as e:
            print(f"Error reading from Kinect: {e}")
            
        return None, None, None, None
    
    def map_to_eye_position(self, x, y, depth, zone):
        """Map Kinect coordinates to eye positions based on zone"""
        # Normalize coordinates to 0-1 range
        x_norm = x / KINECT_WIDTH  # 0=left, 1=right
        y_norm = y / KINECT_HEIGHT  # 0=top, 1=bottom
        
        # Normalize depth (closer objects have more extreme eye movements)
        depth_norm = 1.0 - min(max((depth - MIN_DEPTH_MM) / (MAX_DEPTH_MM - MIN_DEPTH_MM), 0), 1)
        
        # Calculate horizontal position based on zone
        if zone == 'left':
            # Left zone eyes look more extreme to the left when object is on the left
            h_pos = consts.midpoint - int(consts.eyeLeftExtreme * x_norm * depth_norm)
        elif zone == 'right':
            # Right zone eyes look more extreme to the right when object is on the right
            h_pos = consts.midpoint + int(consts.eyeRightExtreme * (1 - x_norm) * depth_norm)
        else:  # center zone
            # Center zone eyes follow the x position more directly
            h_pos = consts.midpoint + int((x_norm - 0.5) * 2 * 
                  (consts.eyeRightExtreme if x_norm > 0.5 else consts.eyeLeftExtreme) * depth_norm)
        
        # Vertical movement is the same for all zones
        v_pos = consts.midpoint + int((y_norm - 0.5) * 2 * 
               (consts.eyeDownExtreme if y_norm > 0.5 else consts.eyeUpExtreme) * depth_norm)
        
        # Ensure positions are within bounds
        h_pos = max(consts.midpoint - consts.eyeLeftExtreme, 
                   min(consts.midpoint + consts.eyeRightExtreme, h_pos))
        v_pos = max(consts.midpoint - consts.eyeUpExtreme, 
                   min(consts.midpoint + consts.eyeDownExtreme, v_pos))
        
        return h_pos, v_pos
    
    def move_eye(self, board_num, eye_num, h_pos, v_pos):
        """Move a single eye to the specified position"""
        if board_num < 1 or board_num > len(self.boards):
            return
            
        pca = self.boards[board_num - 1]
        up_down_channel = (eye_num - 1) * 2
        left_right_channel = (eye_num - 1) * 2 + 1
        
        # Set positions with a small delay to avoid overwhelming the I2C bus
        pca.channels[up_down_channel].duty_cycle = self.pwm_to_duty_cycle(v_pos)
        time.sleep(0.001)
        pca.channels[left_right_channel].duty_cycle = self.pwm_to_duty_cycle(h_pos)
    
    def pwm_to_duty_cycle(self, pwm_value):
        """Convert PWM value to duty cycle for PCA9685"""
        # PCA9685 uses 16-bit resolution (0-65535)
        # Standard servo PWM range is typically 1-2ms pulse width at 50Hz (20ms period)
        # 1ms = 0 degrees, 1.5ms = 90 degrees, 2ms = 180 degrees
        # 1ms = 0.05 * 65535 = 3276.8
        # 2ms = 0.10 * 65535 = 6553.5
        # So the range is approximately 3277-6553 for 0-180 degrees
        min_pulse = 3277
        max_pulse = 6553
        pulse_width = min_pulse + int((pwm_value / 180.0) * (max_pulse - min_pulse))
        return min(max(pulse_width, min_pulse), max_pulse)
    
    def run(self):
        """Main tracking loop"""
        print("Starting eye tracking. Press Ctrl+C to exit.")
        
        try:
            while True:
                depth, x, y, depth_frame = self.read_kinect_data()
                
                if depth is not None and x is not None and y is not None:
                    if self.debug and depth_frame is not None:
                        # Clear screen and move cursor to top-left
                        print("\033[H\033[J", end='')
                        # Debug: Print focus point info
                        x_pct = (x / KINECT_WIDTH) * 100
                        y_pct = (y / KINECT_HEIGHT) * 100
                        print(f"\rFocus: X={x:3d} ({x_pct:3.0f}%), Y={y:3d} ({y_pct:3.0f}%), Depth={depth:4d}mm", 
                              end='', flush=True)
                    
                    # Track positions for debug output
                    positions = {'left': None, 'center': None, 'right': None}
                    
                    # Update all eyes based on the tracked point
                    for eye_id, zone in self.eye_zones.items():
                        board_num = int(eye_id)
                        eye_num = int(round((eye_id - board_num) * 10))
                        
                        # Skip invalid eye numbers
                        if eye_num < 1 or eye_num > 8:
                            continue
                            
                        # Calculate eye position based on zone
                        h_pos, v_pos = self.map_to_eye_position(x, y, depth, zone)
                        
                        # Store position for debug output (just one per zone)
                        if positions[zone] is None:
                            positions[zone] = (h_pos, v_pos)
                        
                        # Move the eye
                        self.move_eye(board_num, eye_num, h_pos, v_pos)
                    
                    # Print zone positions for debug (one per zone)
                    debug_output = []
                    for zone in ['left', 'center', 'right']:
                        if positions[zone]:
                            h, v = positions[zone]
                            h_norm = (h - consts.midpoint) / consts.eyeLeftExtreme * 100 if h < consts.midpoint else \
                                    (h - consts.midpoint) / consts.eyeRightExtreme * 100
                            v_norm = (v - consts.midpoint) / consts.eyeUpExtreme * 100 if v < consts.midpoint else \
                                    (v - consts.midpoint) / consts.eyeDownExtreme * 100
                            debug_output.append(f"{zone[0].upper()}:H{h_norm:3.0f}% V{v_norm:3.0f}%")
                    
                    if self.debug and depth_frame is not None:
                        # Print the depth map
                        print("\nDepth Map (darker = closer):")
                        ascii_map = self.get_depth_map_ascii(depth_frame)
                        print(ascii_map)
                        
                        # Print the debug info on a new line
                        print(f"\nFocus: X={x:3d} ({x_pct:3.0f}%), Y={y:3d} ({y_pct:3.0f}%), Depth={depth:4d}mm")
                        print(" | " + " | ".join(debug_output), end='\n', flush=True)
                
                # Small delay to prevent excessive CPU usage and control update rate
                time.sleep(0.05)  # ~20 updates per second
                
        except KeyboardInterrupt:
            print("\nStopping eye tracking...")
        finally:
            # Clean up Kinect
            try:
                freenect.sync_stop()
            except Exception:
                pass
            print("Cleanup complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Eye tracking with Kinect')
    parser.add_argument('--debug', action='store_true', help='Enable debug output with ASCII depth map')
    args = parser.parse_args()
    
    controller = EyeController(debug=args.debug)
    if args.debug:
        print("Debug mode enabled. Showing detailed output and depth map.")
    controller.run()