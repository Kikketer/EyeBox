#!/usr/bin/env python3
"""
Adafruit PCA9685 Servo Test Script for Raspberry Pi 5
Tests multiple PCA9685 boards with all servo channels by setting them to midpoint (185) 
then randomly moving them between PWM values 150-200 every 3 seconds.

Hardware Setup:
- Board 1: Default address 0x40 (no jumpers)
- Board 2: Address 0x41 (A0 jumper soldered)
"""

import time
import random
import board
import busio
from adafruit_pca9685 import PCA9685

# I2C addresses for multiple boards
BOARD_ADDRESSES = [0x40, 0x41]  # Add more addresses as needed (0x42, 0x43, etc.)

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
        print("Setting all servos to midpoint (PWM 185)...")
        
        # Set all channels on all boards to midpoint (185)
        for board_num, pca in enumerate(boards):
            for channel in range(16):
                pca.channels[channel].duty_cycle = pwm_to_duty_cycle(185)
                print(f"Board {board_num+1}, Channel {channel}: PWM 185")
        
        print("\nStarting random movement test...")
        print("Press Ctrl+C to stop\n")
        
        # Main test loop
        while True:
            # Wait 3 seconds
            time.sleep(3)
            
            # Generate random PWM value between 150 and 200
            random_pwm = random.randint(150, 200)
            
            print(f"Setting all servos on all boards to PWM {random_pwm}")
            
            # Set all channels on all boards to the random PWM value
            for board_num, pca in enumerate(boards):
                for channel in range(16):
                    pca.channels[channel].duty_cycle = pwm_to_duty_cycle(random_pwm)
            
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