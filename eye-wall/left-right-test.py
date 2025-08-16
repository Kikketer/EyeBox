#!/usr/bin/env python3
"""
Left-Right Movement Test for EyeBox - Tests only horizontal movement
Cycles all servos between left and right positions to validate cord connections.

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

# Left and right positions for horizontal movement testing (from eye-sights.py)
MIDPOINT = 352
EYE_RIGHT_EXTREME = 80  # Right goes negative from midpoint
EYE_LEFT_EXTREME = 50   # Left goes positive from midpoint

LEFT_POSITION = MIDPOINT + EYE_LEFT_EXTREME   # 352 + 50 = 402 (leftmost)
RIGHT_POSITION = MIDPOINT - EYE_RIGHT_EXTREME # 352 - 80 = 272 (rightmost)
CENTER_POSITION = MIDPOINT # 352 (center position)

def pwm_to_duty_cycle(pwm_value):
    """
    Convert PWM value to duty cycle for PCA9685
    PCA9685 uses 16-bit resolution (0-65535)
    """
    return int((pwm_value / 4095.0) * 65535)

def test_left_right_movement(boards):
    """Test left-right movement for odd pins only (left/right channels)"""
    print("Starting left-right movement test...")
    print("Testing ONLY odd pins (1,3,5,7,9,11,13,15) - Left/Right channels")
    print("Watch left/right servos - they should move left, then right, then center")
    print("-" * 60)
    
    # Only test odd channels (left/right movement channels)
    left_right_channels = [1, 3, 5, 7, 9, 11, 13, 15]
    
    positions = [
        (LEFT_POSITION, "LEFT"),
        (RIGHT_POSITION, "RIGHT"), 
        (CENTER_POSITION, "CENTER")
    ]
    
    for position, direction in positions:
        print(f"\nMoving left/right servos to {direction} position ({position})")
        
        for board_num, pca in enumerate(boards):
            print(f"  Board {board_num+1}:")
            for channel in left_right_channels:
                try:
                    pca.channels[channel].duty_cycle = pwm_to_duty_cycle(position)
                    print(f"    Channel {channel:2d} (L/R): PWM {position} ✓")
                except Exception as e:
                    print(f"    Channel {channel:2d} (L/R): Error - {e} ✗")
        
        # During CENTER phase, also set even channels (up/down) to center for alignment check
        if direction == "CENTER":
            print(f"  Also centering even channels (U/D) for alignment verification:")
            even_channels = [0, 2, 4, 6, 8, 10, 12, 14]
            for board_num, pca in enumerate(boards):
                print(f"  Board {board_num+1} (U/D channels):")
                for channel in even_channels:
                    try:
                        pca.channels[channel].duty_cycle = pwm_to_duty_cycle(CENTER_POSITION)
                        print(f"    Channel {channel:2d} (U/D): PWM {CENTER_POSITION} ✓")
                    except Exception as e:
                        print(f"    Channel {channel:2d} (U/D): Error - {e} ✗")
        
        print(f"All servos moved to {direction} - Hold for 2 seconds")
        time.sleep(2)
    
    print("\nSingle movement cycle complete!")

def main():
    print("EyeBox Left-Right Movement Test")
    print("Testing horizontal movement to validate cord connections")
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
        print("Press Ctrl+C to stop the test at any time")
        print("-" * 60)
        
        # Continuous left-right testing
        cycle_count = 0
        try:
            while True:
                cycle_count += 1
                print(f"\n=== Test Cycle {cycle_count} ===")
                test_left_right_movement(boards)
                
                print("\nWaiting 3 seconds before next cycle...")
                time.sleep(3)
                
        except KeyboardInterrupt:
            print(f"\nLeft-right test stopped by user after {cycle_count} cycles")
            
    except KeyboardInterrupt:
        print("\nLeft-right test stopped by user")
    except Exception as e:
        print(f"Error during left-right test: {e}")
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
        print("Left-right test script terminated.")

if __name__ == "__main__":
    main()