#!/usr/bin/env python3
"""
Adafruit PCA9685 Servo Test Script for Raspberry Pi 5
Tests multiple PCA9685 boards with all servo channels by moving them in a square pattern
using the same limits as eye-sights.py (extreme positions for left/right and up/down).

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
from adafruit_pca9685 import PCA9685
from consts import consts

# I2C addresses for multiple boards
BOARD_ADDRESSES = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]  # 8 boards total


def main():
    print("Initializing multiple PCA9685 servo boards...")
    
    try:
        # Initialize I2C bus
        i2c = busio.I2C(board.SCL, board.SDA)
        
        # Initialize multiple PCA9685 boards
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
        print(f"Setting all servos to midpoint (PWM {consts.midpoint})...")
        
        # Set all channels on all boards to midpoint
        for board_num, pca in enumerate(boards):
            for channel in range(16):
                pca.channels[channel].duty_cycle = pwm_to_duty_cycle(consts.midpoint)
                motion_type = "Up/Down" if channel % 2 == 0 else "Left/Right"
                print(f"Board {board_num+1}, Channel {channel} ({motion_type}): PWM {consts.midpoint}")
        
        print("\nStarting square movement test...")
        print("Moving all servos in square pattern: Left/Up -> Left/Down -> Right/Down -> Right/Up")
        print("Press Ctrl+C to stop\n")
        
        # Square movement positions
        square_positions = [
            ("Left/Up", consts.midpoint - consts.eyeRightExtreme, consts.midpoint + consts.eyeUpExtreme),
            ("Left/Down", consts.midpoint - consts.eyeRightExtreme, consts.midpoint - consts.eyeDownExtreme),
            ("Right/Down", consts.midpoint + consts.eyeLeftExtreme, consts.midpoint - consts.eyeDownExtreme),
            ("Right/Up", consts.midpoint + consts.eyeLeftExtreme, consts.midpoint + consts.eyeUpExtreme)
        ]
        
        position_index = 0
        
        # Main test loop
        while True:
            # Get current square position
            position_name, left_right_pwm, up_down_pwm = square_positions[position_index]
            
            print(f"Moving to {position_name}: Left/Right={left_right_pwm}, Up/Down={up_down_pwm}")
            
            # Set all channels on all boards to the square position
            for board_num, pca in enumerate(boards):
                for channel in range(16):
                    if channel % 2 == 0:  # Even channels: Up/Down
                        pca.channels[channel].duty_cycle = pwm_to_duty_cycle(up_down_pwm)
                    else:  # Odd channels: Left/Right
                        pca.channels[channel].duty_cycle = pwm_to_duty_cycle(left_right_pwm)
            
            # Move to next position in square
            position_index = (position_index + 1) % 4
            
            # Wait 2 seconds before next movement
            time.sleep(2)
            
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