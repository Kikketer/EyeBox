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

# I2C addresses for multiple boards
BOARD_ADDRESSES = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]  # 8 boards total

# Global variables for eye control
boards = []
running = True

class EyeScheduler:
    """
    Manages eye movements with scheduled timing instead of individual threads
    """
    def __init__(self):
        self.eye_schedule = {}  # {(board_num, eye_num): next_move_time}
        
    def schedule_eye_movement(self, board_num, eye_num):
        """Schedule the next movement for an eye"""
        next_move = time.time() + random.uniform(1.0, 5.0)
        self.eye_schedule[(board_num, eye_num)] = next_move
        
    def move_ready_eyes(self):
        """Move all eyes that are ready to move"""
        current_time = time.time()
        eyes_to_move = []
        
        for (board_num, eye_num), move_time in self.eye_schedule.items():
            if current_time >= move_time:
                eyes_to_move.append((board_num, eye_num))
        
        for board_num, eye_num in eyes_to_move:
            self.move_single_eye(board_num, eye_num)
            self.schedule_eye_movement(board_num, eye_num)  # Schedule next movement
            
    def move_single_eye(self, board_num, eye_num):
        """Move a single eye to random positions"""
        try:
            up_down_channel = eye_num * 2
            left_right_channel = eye_num * 2 + 1
            
            # Generate random PWM values for this eye
            up_down_pwm = random.randint(150, 200)
            left_right_pwm = random.randint(150, 200)
            
            # Set the servo positions for this eye
            boards[board_num].channels[up_down_channel].duty_cycle = pwm_to_duty_cycle(up_down_pwm)
            boards[board_num].channels[left_right_channel].duty_cycle = pwm_to_duty_cycle(left_right_pwm)
            
            print(f"Board {board_num+1}, Eye {eye_num}: Up/Down={up_down_pwm}, Left/Right={left_right_pwm}")
            
        except Exception as e:
            print(f"Error moving eye {eye_num} on board {board_num+1}: {e}")

def eye_movement_worker(scheduler):
    """
    Single worker thread that handles all eye movements
    """
    global running
    
    while running:
        scheduler.move_ready_eyes()
        time.sleep(0.1)  # Check every 100ms for responsive movement

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
        
        print("\nStarting optimized eye movement system...")
        print("Using single-thread scheduler for all 64 eyes with independent timing")
        print("Press Ctrl+C to stop\n")
        
        # Create eye scheduler and initialize all eyes
        scheduler = EyeScheduler()
        
        # Schedule initial movements for all eyes
        for board_num in range(len(boards)):
            for eye_num in range(8):  # 8 eyes per board
                scheduler.schedule_eye_movement(board_num, eye_num)
                up_down_channel = eye_num * 2
                left_right_channel = eye_num * 2 + 1
                print(f"Scheduled eye {eye_num} on board {board_num+1} (channels {up_down_channel}/{left_right_channel})")
        
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