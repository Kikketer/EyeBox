#!/usr/bin/env python3
"""
Eye Movement Control Script for Raspberry Pi 5
Controls eye movements using multiple PCA9685 boards with servo channels split by function:
- Even pins (0,2,4,6,8,10,12,14): Up/Down eye movements
- Odd pins (1,3,5,7,9,11,13,15): Left/Right eye movements

Hardware Setup:
- Board 1: Default address 0x40 (no jumpers)
- Board 2: Address 0x41 (A0 jumper soldered)
- Board 3: Address 0x42 (A1 jumper soldered)
- Board 4: Address 0x43 (A0 + A1 jumpers soldered)
- Board 5: Address 0x44 (A2 jumper soldered)
- Board 6: Address 0x45 (A0 + A2 jumpers soldered)
- Board 7: Address 0x46 (A1 + A2 jumpers soldered)
- Board 8: Address 0x47 (A0 + A1 + A2 jumpers soldered)
"""

import time
import random
import board
import busio
import threading
from adafruit_pca9685 import PCA9685
from consts import consts

# I2C addresses for multiple boards
BOARD_ADDRESSES = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]  # 8 boards total

# Global variables for eye control
boards = []
running = True


class EyeScheduler:
    """
    Manages completely random eye movements with individual timing per eye
    Uses timing discovered in i2c-timing-test.py for optimal I2C communication
    """
    def __init__(self):
        self.eye_schedule = {}  # {(board_num, eye_num): next_move_time}
        self.last_command_time = 0  # Track timing for 10ms delays
        self.min_interval = 0.2   # Minimum 200ms between movements per eyes
        self.max_interval = 3.0   # Maximum 3000ms between movements per eye
        
    def schedule_eye_movement(self, board_num, eye_num, initial=False):
        """Schedule the next movement for an eye with random timing"""
        if initial:
            # Stagger initial movements randomly over first 5 seconds
            delay = random.uniform(0, 5.0)
        else:
            # Random interval between min and max for ongoing movements
            delay = random.uniform(self.min_interval, self.max_interval)
        
        next_move = time.time() + delay
        self.eye_schedule[(board_num, eye_num)] = next_move
        
    def move_ready_eyes(self):
        """Move all eyes that are ready to move with 10ms delays between commands"""
        current_time = time.time()
        eyes_to_move = []
        
        for (board_num, eye_num), move_time in self.eye_schedule.items():
            if current_time >= move_time:
                eyes_to_move.append((board_num, eye_num))
        
        for board_num, eye_num in eyes_to_move:
            self.move_single_eye_with_timing(board_num, eye_num)
            self.schedule_eye_movement(board_num, eye_num)  # Schedule next movement
            
    def move_single_eye_with_timing(self, board_num, eye_num):
        """Move a single eye to random positions with 10ms delays between servo commands"""
        try:
            up_down_channel = eye_num * 2
            left_right_channel = eye_num * 2 + 1
            
            # Generate random PWM values for this eye
            up_down_pwm = random.randint(consts.midpoint - consts.eyeDownExtreme, consts.midpoint + consts.eyeUpExtreme)
            left_right_pwm = random.randint(consts.midpoint - consts.eyeRightExtreme, consts.midpoint + consts.eyeLeftExtreme)
            
            # Ensure 10ms delay since last command
            current_time = time.time()
            time_since_last = current_time - self.last_command_time
            if time_since_last < 0.01:  # 10ms = 0.01 seconds
                time.sleep(0.01 - time_since_last)
            
            # Set up/down servo position
            boards[board_num].channels[up_down_channel].duty_cycle = pwm_to_duty_cycle(up_down_pwm)
            self.last_command_time = time.time()
            
            # 10ms delay between servo commands
            time.sleep(0.01)
            
            # Set left/right servo position
            boards[board_num].channels[left_right_channel].duty_cycle = pwm_to_duty_cycle(left_right_pwm)
            self.last_command_time = time.time()
            
        except Exception as e:
            print(f"Error moving eye {eye_num} on board {board_num+1}: {e}")

def eye_movement_worker(scheduler):
    """
    Single worker thread that handles all eye movements
    Optimized for fast movement with minimal delay
    """
    global running
    
    while running:
        scheduler.move_ready_eyes()
        time.sleep(0.005)  # Check every 5ms for maximum responsiveness

def main():
    print("Initializing multiple PCA9685 servo boards...")
    
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
        print("Setting all servos to midpoint (PWM 185)...")
        
        # Set all channels on all boards to midpoint (185)
        for board_num, pca in enumerate(boards):
            for channel in range(16):
                pca.channels[channel].duty_cycle = pwm_to_duty_cycle(185)
                motion_type = "Up/Down" if channel % 2 == 0 else "Left/Right"
                print(f"Board {board_num+1}, Channel {channel} ({motion_type}): PWM 185")
        
        print("\nStarting completely random eye movement system...")
        print("Using 10ms I2C delays with individual random timing per eye (200ms-3s intervals)")
        print(f"Managing {len(boards) * 8} eyes with completely independent random movement")
        print("Press Ctrl+C to stop\n")
        
        # Create eye scheduler and initialize all eyes
        scheduler = EyeScheduler()
        
        # Schedule initial movements for all eyes with random staggering
        for board_num in range(len(boards)):
            for eye_num in range(8):  # 8 eyes per board
                scheduler.schedule_eye_movement(board_num, eye_num, initial=True)
                up_down_channel = eye_num * 2
                left_right_channel = eye_num * 2 + 1
                print(f"Scheduled eye {eye_num} on board {board_num+1} (channels {up_down_channel}/{left_right_channel}) with random timing")
        
        # Start single worker thread for all eye movements
        worker_thread = threading.Thread(
            target=eye_movement_worker,
            args=(scheduler,),
            daemon=True
        )
        worker_thread.start()
        print(f"\nStarted single worker thread managing {len(boards) * 8} eyes")
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping all eye movements...")
            global running
            running = False
            
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
        except:
            pass

def pwm_to_duty_cycle(pwm_value):
    """
    Convert PWM value to duty cycle for PCA9685
    PCA9685 uses 16-bit resolution (0-65535)
    Standard servo PWM range is typically 1-2ms pulse width
    """
    # Map PWM value to duty cycle
    # Assuming PWM values 150-200 correspond to servo positions
    # This maps to approximately 1-2ms pulse width at 50Hz
    return int((pwm_value / 4095.0) * 65535)

if __name__ == "__main__":
    main()