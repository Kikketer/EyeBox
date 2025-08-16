#!/usr/bin/env python3
"""
Servo Calibration Script for EyeBox - Centers all servos at position 322
Sets all servos across all 8 PCA9685 boards to position 322 for calibration validation.

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
import board
import busio
from adafruit_pca9685 import PCA9685

# I2C addresses for all 8 boards
BOARD_ADDRESSES = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]

# Calibration position (per calculations of 499 max and 125 min, it should be 312)
# There's some goof in the plastic piece that will not let us attach it true center, so we offset:
CALIBRATION_POSITION = 352

def pwm_to_duty_cycle(pwm_value):
    """
    Convert PWM value to duty cycle for PCA9685
    PCA9685 uses 16-bit resolution (0-65535)
    """
    return int((pwm_value / 4095.0) * 65535)

def main():
    print(f"EyeBox Servo Calibration - Setting all servos to position {CALIBRATION_POSITION}")
    print("=" * 60)
    
    try:
        # Initialize I2C bus
        i2c = busio.I2C(board.SCL, board.SDA)
        
        # Initialize all PCA9685 boards
        boards = []
        for i, address in enumerate(BOARD_ADDRESSES):
            try:
                pca = PCA9685(i2c, address=address)
                pca.frequency = 50  # Standard servo frequency (50Hz)
                boards.append(pca)
                print(f"✓ Board {i+1} (0x{address:02X}) initialized successfully")
            except Exception as e:
                print(f"✗ Warning: Could not initialize board at address 0x{address:02X}: {e}")
        
        if not boards:
            print("\nError: No PCA9685 boards found! Check wiring and addresses.")
            return
        
        print(f"\nFound {len(boards)} PCA9685 board(s)")
        print(f"Setting all servos to calibration position: {CALIBRATION_POSITION}")
        print("-" * 60)
        
        # Set all channels on all boards to calibration position
        total_servos = 0
        for board_num, pca in enumerate(boards):
            print(f"\nBoard {board_num+1} (0x{BOARD_ADDRESSES[board_num]:02X}):")
            for channel in range(16):
                try:
                    pca.channels[channel].duty_cycle = pwm_to_duty_cycle(CALIBRATION_POSITION)
                    print(f"  Channel {channel:2d}: PWM {CALIBRATION_POSITION} ✓")
                    total_servos += 1
                    time.sleep(0.05)  # Small delay to prevent overwhelming the boards
                except Exception as e:
                    print(f"  Channel {channel:2d}: Error - {e} ✗")
        
        print("-" * 60)
        print(f"Calibration complete! Set {total_servos} servos to position {CALIBRATION_POSITION}")
        print("\nAll servos should now be at their calibration position.")
        print("Verify alignment and press Ctrl+C when done.")
        
        # Keep the script running to maintain servo positions
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nCalibration session ended by user")
            
    except KeyboardInterrupt:
        print("\nCalibration stopped by user")
    except Exception as e:
        print(f"Error during calibration: {e}")
    finally:
        # Clean shutdown - turn off all servos
        try:
            print("\nShutting down servos...")
            for board_num, pca in enumerate(boards):
                for channel in range(16):
                    pca.channels[channel].duty_cycle = 0
                pca.deinit()
                print(f"Board {board_num+1} shutdown complete")
        except:
            pass
        print("Calibration script terminated.")

if __name__ == "__main__":
    main()