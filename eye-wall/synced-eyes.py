#!/usr/bin/env python3
"""
Synced Eye Movement Control Script for Raspberry Pi 5
Controls all eyes to move in sync to random directions.
Eyes will move together to the same position at the same time.
"""

import time
import random
import math
import board
import busio
import threading
import lgpio
from adafruit_pca9685 import PCA9685
from consts import consts

# GPIO pin for the toggle switch (BCM numbering)
TOGGLE_SWITCH_PIN = 17  # GPIO17, physical pin 11

# GPIO handle
gpio_handle = None

# I2C addresses for multiple boards
BOARD_ADDRESSES = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48]  # 9 boards total

# Global variables
boards = []
running = True

class SyncedEyeController:
    def __init__(self):
        self.last_h_pos = consts.midpoint  # Start at center
        self.last_v_pos = consts.midpoint  # Start at center
        self.last_move_time = 0
        self.min_interval = 0.75  # Minimum 0.75 seconds between movements
        self.max_interval = 3  # Maximum 3 seconds between movements
        self.min_distance = 0.3  # Minimum 30% distance from previous position
        self.last_command_time = 0
        
    def calculate_next_position(self):
        """Calculate next position that's at least 30% different from current position"""
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
            
            h_dist = abs(new_h_pos - self.last_h_pos) / h_range
            v_dist = abs(new_v_pos - self.last_v_pos) / v_range
            
            # Use Euclidean distance in 2D space
            distance = math.sqrt(h_dist**2 + v_dist**2) / math.sqrt(2)  # Normalize to 0-1
            
            # If distance is sufficient, return the new position
            if distance >= self.min_distance:
                return new_h_pos, new_v_pos
    
    def move_all_eyes(self):
        """Move all eyes to the same position with proper timing"""
        if not boards:
            return
            
        # Calculate next position
        h_pos, v_pos = self.calculate_next_position()
        self.last_h_pos = h_pos
        self.last_v_pos = v_pos
        
        print(f"Moving all eyes to position: H={h_pos}, V={v_pos}")
        
        # Move all eyes to the new position
        for board_num, pca in enumerate(boards):
            for eye_num in range(8):  # 8 eyes per board
                up_down_channel = eye_num * 2
                left_right_channel = eye_num * 2 + 1
                
                # Set up/down position with 10ms delay
                self._enforce_delay()
                pca.channels[up_down_channel].duty_cycle = pwm_to_duty_cycle(v_pos)
                
                # Set left/right position with 10ms delay
                self._enforce_delay()
                pca.channels[left_right_channel].duty_cycle = pwm_to_duty_cycle(h_pos)
    
    def _enforce_delay(self):
        """Ensure at least 10ms between commands"""
        current_time = time.time()
        time_since_last = current_time - self.last_command_time
        if time_since_last < 0.005:  # 5ms = 0.005 seconds
            time.sleep(0.005 - time_since_last)
        self.last_command_time = time.time()
    
    def schedule_next_move(self):
        """Schedule the next eye movement with random delay"""
        delay = random.uniform(self.min_interval, self.max_interval)
        time.sleep(delay)
        return self.move_all_eyes()

def setup_gpio():
    """Set up GPIO for the toggle switch using lgpio"""
    global gpio_handle
    try:
        # Open the GPIO device
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

def is_switch_on():
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

def wait_for_switch_change():
    """Wait for the switch to change state"""
    current_state = is_switch_on()
    while is_switch_on() == current_state:
        time.sleep(0.1)

def main():
    print("Initializing Synced Eye Movement System...")
    
    # Setup GPIO and check if it was successful
    gpio_available = setup_gpio()
    if not gpio_available:
        print("Running in simulation mode (no GPIO access). Eye movements will run automatically.")
    else:
        # Wait for switch to be turned on if GPIO is available
        print("\nWaiting for toggle switch to be turned ON...")
        while not is_switch_on():
            time.sleep(0.1)
    
    try:
        # Initialize I2C bus
        i2c = busio.I2C(board.SCL, board.SDA)
        
        # Initialize multiple PCA9685 boards
        global boards
        boards = []
        for i, address in enumerate(BOARD_ADDRESSES):
            try:
                pca = PCA9685(i2c, address=address)
                pca.frequency = 50  # Standard servo frequency (50Hz)
                boards.append(pca)
                print(f"Board {i+1} (0x{address:02X}) initialized successfully!")
            except Exception as e:
                print(f"Warning: Could not initialize board at address 0x{address:02X}: {e}")
        
        if not boards:
            print("No PCA9685 boards found! Check wiring and addresses.")
            return
        
        print(f"\nFound {len(boards)} PCA9685 board(s)")
        print("Setting all servos to center position...")
        
        # Set all channels on all boards to midpoint with 10ms delay between each motor
        print("Centering all motors with 10ms delay between each...")
        for board_num, pca in enumerate(boards):
            for channel in range(16):
                pca.channels[channel].duty_cycle = pwm_to_duty_cycle(consts.midpoint)
                time.sleep(0.01)  # 10ms delay between each motor
        
        print("\nWaiting 2 seconds before starting synced eye movement...")
        time.sleep(2)  # 2 second delay before starting
        
        print("\nStarting synced eye movement system...")
        print(f"Moving all {len(boards) * 8} eyes in sync")
        print("Random movements every 2-5 seconds")
        print("Each move is at least 30% different from previous position")
        print("Press Ctrl+C to stop\n")
        
        # Create controller
        controller = SyncedEyeController()
        
        def power_down_servos():
            """Power down all servos by setting duty cycle to 0"""
            for board_num, pca in enumerate(boards):
                for channel in range(16):
                    pca.channels[channel].duty_cycle = 0  # 0% duty cycle powers off the servo
                    time.sleep(0.01)  # Small delay between each motor
        
        def center_servos():
            """Center all servos to their midpoint position"""
            print("Centering servos...")
            for board_num, pca in enumerate(boards):
                for channel in range(16):
                    pca.channels[channel].duty_cycle = pwm_to_duty_cycle(consts.midpoint)
                    time.sleep(0.01)  # 10ms delay between each motor
            time.sleep(2)  # Wait for servos to reach center
            power_down_servos()
            print("Servos centered and powered down")
        
        # Initial state
        global running
        was_on = is_switch_on()
        
        # Initial behavior based on switch state
        if was_on:
            print("\nStarting with switch ON. Centering servos...")
            center_servos()
            time.sleep(0.5)
        else:
            print("\nStarting with switch OFF. Waiting for switch to turn ON...")
            power_down_servos()
        
        # Main loop
        while running:
            try:
                switch_on = is_switch_on()
                
                if switch_on:
                    if not was_on:  # Just turned on
                        print("\nSwitch turned ON. Centering servos...")
                        center_servos()
                        time.sleep(0.5)
                        print("Starting random eye movements...")
                        was_on = True
                    
                    # Run one movement cycle
                    controller.move_all_eyes()
                    # Power down after movement
                    power_down_servos()
                    # Wait for next movement
                    time.sleep(random.uniform(controller.min_interval, controller.max_interval))
                    
                else:  # Switch is OFF
                    if was_on:  # Just turned off
                        print("\nSwitch turned OFF. Centering servos...")
                        center_servos()
                        print("Waiting for switch to be turned back ON...")
                        was_on = False
                    # Small delay to prevent high CPU usage
                    time.sleep(0.1)
                    
                    
            except KeyboardInterrupt:
                print("\nStopping all eye movements...")
                running = False
                break
            except Exception as e:
                print(f"Error during eye movement: {e}")
                time.sleep(1)  # Prevent tight loop on errors
        
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean shutdown - set all channels to 0 (off) on all boards
        try:
            print("Shutting down servos on all boards...")
            for board_num, pca in enumerate(boards):
                for channel in range(16):
                    pca.channels[channel].duty_cycle = 0
                pca.deinit()
                print(f"Board {board_num+1} shutdown complete")
            
            # Clean up GPIO if it was initialized
            global gpio_handle
            if gpio_handle is not None:
                print("Cleaning up GPIO...")
                try:
                    lgpio.gpiochip_close(gpio_handle)
                    gpio_handle = None
                except Exception as e:
                    print(f"Warning: Error cleaning up GPIO: {e}")
        except Exception as e:
            print(f"Error during shutdown: {e}")

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
    main()
