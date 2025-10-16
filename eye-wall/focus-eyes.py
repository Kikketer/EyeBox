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
import time
import threading
import busio
import numpy as np
import random
import math
import lgpio
from adafruit_pca9685 import PCA9685
from consts import consts

# GPIO pin for the toggle switch (BCM numbering)
TOGGLE_SWITCH_PIN = 17  # GPIO17, physical pin 11

# GPIO handle
gpio_handle = None

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
MAX_DEPTH_MM = 600

class EyeController:
    def __init__(self, debug=False):
        self.boards = []
        self.eye_zones = {}  # Maps eye_id (board.eye) to zone ('left', 'right', 'center')
        self.debug = debug
        self.last_command_time = 0  # For enforcing delay between commands
        self.last_kinect_update = 0  # Timestamp of last Kinect update
        self.last_depth_data = (None, None, None, None)  # (depth, x, y, depth_frame)
        self.last_move_time = time.time()  # Track when we last moved the eyes
        self.random_move_interval = 2.0
        self.gpio_available = self.setup_gpio()
        self.initialize_eyes()
        self.just_lost_sight = False
        
        # Initialize random movement parameters
        self.last_h_pos = consts.midpoint
        self.last_v_pos = consts.midpoint
        self.min_distance = 0.3  # Minimum 30% distance from previous position for random moves
        
    def setup_gpio(self):
        """Set up GPIO for the toggle switch using lgpio"""
        try:
            # Open the GPIO device
            global gpio_handle
            gpio_handle = lgpio.gpiochip_open(0)
            
            # Set the pin as input with pull-up
            lgpio.gpio_claim_input(gpio_handle, TOGGLE_SWITCH_PIN, lgpio.SET_PULL_UP)
            
            print(f"Toggle switch set up on GPIO{TOGGLE_SWITCH_PIN} using lgpio")
            return True
            
        except Exception as e:
            print(f"Error setting up GPIO: {e}")
            print("\n" + "="*60)
            print("ERROR: Failed to initialize GPIO. Make sure:")
            print("1. You're running with sudo")
            print("2. You have the lgpio library installed (pip install lgpio)")
            print("3. Your user is in the 'gpio' group (run: sudo usermod -a -G gpio $USER)")
            print("4. You may need to reboot after adding to the gpio group")
            print("="*60 + "\n")
            return False
            
    def is_switch_on(self):
        """Check if the toggle switch is in the ON position"""
        global gpio_handle
        try:
            if gpio_handle is not None:
                # Read the pin state (0 = ON/LOW, 1 = OFF/HIGH due to pull-up)
                state = lgpio.gpio_read(gpio_handle, TOGGLE_SWITCH_PIN)
                # Switch is ON when the pin reads LOW (connected to GND when ON)
                return state == 0
            return True  # Default to ON if GPIO not available
        except Exception as e:
            print(f"Error reading GPIO: {e}")
            return True  # Default to ON on error

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
    
    def calculate_random_position(self):
        """Calculate a random position that's at least 30% different from current position"""
        while True:
            # Generate random position within bounds
            new_h_pos = random.randint(
                consts.midpoint - consts.eyeRightExtreme,
                consts.midpoint + consts.eyeLeftExtreme
            )
            new_v_pos = random.randint(
                consts.midpoint - consts.eyeDownExtreme,
                consts.midpoint + consts.eyeUpExtreme
            )
            
            # Calculate distance from last position (normalized to 0-1 range)
            h_range = consts.eyeLeftExtreme + consts.eyeRightExtreme
            v_range = consts.eyeUpExtreme + consts.eyeDownExtreme
            
            h_dist = abs(new_h_pos - self.last_h_pos) / h_range if h_range > 0 else 0
            v_dist = abs(new_v_pos - self.last_v_pos) / v_range if v_range > 0 else 0
            
            # Use Euclidean distance in 2D space
            distance = math.sqrt(h_dist**2 + v_dist**2) / math.sqrt(2)  # Normalize to 0-1
            
            # If distance is sufficient, return the new position
            if distance >= self.min_distance:
                return new_h_pos, new_v_pos

    def _shutdown_servo(self, pca, h_channel, v_channel):
        """Helper function to shut down a single servo after delay"""
        pca.channels[h_channel].duty_cycle = 0
        pca.channels[v_channel].duty_cycle = 0
        
    def lost_sight(self):
        """Perform a 'lost sight' animation where eyes look around"""
        if not self.boards:
            return
            
        # Center all eyes
        print("Lost sight - centering eyes...")
        self.move_all_eyes(consts.midpoint, consts.midpoint)
        time.sleep(0.5)  # Wait at center
        
        # Look left
        print("Looking left...")
        left_pos = consts.midpoint - consts.eyeLeftExtreme
        self.move_all_eyes(left_pos, consts.midpoint)
        time.sleep(0.3)  # Brief pause at left
        
        # Look right
        print("Looking right...")
        right_pos = consts.midpoint + consts.eyeRightExtreme
        self.move_all_eyes(right_pos, consts.midpoint)
        time.sleep(0.3)  # Brief pause at right
        
        # Return to center
        print("Returning to center...")
        self.move_all_eyes(consts.midpoint, consts.midpoint)
        time.sleep(0.5) # hold... so sad
        
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
        
        # Wait for switch to be turned on if GPIO is available
        if self.gpio_available:
            print("\nWaiting for toggle switch to be turned ON...")
            while not self.is_switch_on():
                time.sleep(0.1)
        else:
            print("Running in simulation mode (no GPIO access). Eye movements will run automatically.")
        
        try:
            while True:
                current_time = time.time()
                time_since_last_move = current_time - self.last_move_time
                
                # Check if switch is on (only if GPIO is available)
                if self.gpio_available and not self.is_switch_on():
                    print("Switch turned OFF. Waiting for switch to be turned back ON...")
                    while not self.is_switch_on():
                        time.sleep(0.1)
                    print("Switch turned ON. Resuming eye tracking...")
                    self.last_move_time = time.time()  # Reset the timer when turning back on
                    continue
                
                # Read from Kinect
                depth, x, y, depth_frame = self.read_kinect_data()
                
                if depth is not None and x is not None and y is not None:
                    # Update last Kinect data and movement time
                    self.last_depth_data = (depth, x, y, depth_frame)
                    self.last_kinect_update = current_time
                    x_pct = (x / KINECT_WIDTH)
                    y_pct = 1 - (y / KINECT_HEIGHT)
                    
                    print(f"\rTracking: X={x:3d} ({x_pct:.2f}), Y={y:3d} ({y_pct:.2f}), Depth={depth:4d}mm")
                    
                    # Calculate eye positions based on Kinect input
                    x_pos = ((consts.eyeLeftExtreme + consts.eyeRightExtreme) * x_pct) + (consts.midpoint - consts.eyeLeftExtreme)
                    y_pos = ((consts.eyeDownExtreme + consts.eyeUpExtreme) * y_pct) + (consts.midpoint - consts.eyeDownExtreme)
                    
                    # Update last positions for random movement reference
                    self.last_h_pos = x_pos
                    self.last_v_pos = y_pos
                    
                    self.move_all_eyes(x_pos, y_pos)
                    self.last_move_time = current_time
                    # Set to true more like "was just viewing stuff"
                    self.just_lost_sight = True
                    
                # If no Kinect input for the random move interval, do random movements
                elif time_since_last_move > self.random_move_interval:
                    # set a new random interval for next movement
                    self.random_move_interval = random.uniform(0.5, 1.2)

                    # Reenable this later, the timing isn't right with kids getting candy
                    # if self.just_lost_sight:
                    #     self.lost_sight()
                    #     self.just_lost_sight = False
                    #     self.last_move_time = time.time()  # Reset the move time after lost_sight
                    #     continue

                    if self.debug:
                        print("\rNo Kinect input - random movement", end='', flush=True)
                    
                    # Get a new random position
                    x_pos, y_pos = self.calculate_random_position()
                    
                    # Update last positions
                    self.last_h_pos = x_pos
                    self.last_v_pos = y_pos
                    
                    if self.debug:
                        print(f"\rRandom move to: H={x_pos}, V={y_pos}", end='', flush=True)
                    
                    self.move_all_eyes(x_pos, y_pos)
                    self.last_move_time = current_time  # Update the move time
                    
                # Small delay to prevent excessive CPU usage
                # Reduced from 20ms to 5ms for faster reaction time
                time.sleep(0.005)  # ~200 updates per second
                
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