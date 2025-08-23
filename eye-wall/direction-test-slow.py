#!/usr/bin/env python3
"""
Left-Right and Up-Down Movement Test for EyeBox
Cycles servos through left-right movements, then up-down movements to validate cord connections.

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
from consts import consts

# I2C addresses for all 8 boards
BOARD_ADDRESSES = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]

# Positions for horizontal and vertical movement testing
LEFT_POSITION = consts.midpoint + consts.eyeLeftExtreme   # leftmost
RIGHT_POSITION = consts.midpoint - consts.eyeRightExtreme # rightmost
UP_POSITION = consts.midpoint + consts.eyeUpExtreme       # upmost
DOWN_POSITION = consts.midpoint - consts.eyeDownExtreme   # downmost
CENTER_POSITION = consts.midpoint # center position

def pwm_to_duty_cycle(pwm_value):
    """
    Convert PWM value to duty cycle for PCA9685
    PCA9685 uses 16-bit resolution (0-65535)
    """
    return int((pwm_value / 4095.0) * 65535)

def test_single_servo_box(pca, board_num, box_number, up_down_channel, left_right_channel):
    """Test one servo box (pair) on a specific board through full up/down/left/right cycle"""
    print(f"\n=== Testing Board {board_num} Box {box_number} ===")
    print(f"Up/Down Channel: {up_down_channel}, Left/Right Channel: {left_right_channel}")
    print("Testing: UP -> DOWN -> LEFT -> RIGHT -> CENTER")
    print("-" * 50)
    
    # Test sequence: UP, DOWN, LEFT, RIGHT, CENTER
    test_sequence = [
        (UP_POSITION, "UP", up_down_channel, "U/D"),
        (DOWN_POSITION, "DOWN", up_down_channel, "U/D"),
        (LEFT_POSITION, "LEFT", left_right_channel, "L/R"),
        (RIGHT_POSITION, "RIGHT", left_right_channel, "L/R"),
        (CENTER_POSITION, "CENTER", up_down_channel, "U/D"),
        (CENTER_POSITION, "CENTER", left_right_channel, "L/R")
    ]
    
    for position, direction, channel, axis in test_sequence:
        print(f"\nMoving Board {board_num} Box {box_number} {axis} servo to {direction} position ({position})")
        
        try:
            pca.channels[channel].duty_cycle = pwm_to_duty_cycle(position)
            print(f"  Board {board_num}, Channel {channel:2d} ({axis}): PWM {position} ✓")
        except Exception as e:
            print(f"  Board {board_num}, Channel {channel:2d} ({axis}): Error - {e} ✗")
        
        print(f"Board {board_num} Box {box_number} moved to {direction} - Hold for 1.5 seconds")
        time.sleep(1.5)
    
    print(f"\nBoard {board_num} Box {box_number} test cycle complete!")

def test_all_boxes_sequentially(boards):
    """Test all servo boxes one at a time - one box per board at a time"""
    print("Starting sequential box testing...")
    print("Each box consists of one up/down servo (even channel) + one left/right servo (odd channel)")
    print("Box pairs: (0,1), (2,3), (4,5), (6,7), (8,9), (10,11), (12,13), (14,15)")
    print("Testing order: Board 1 all boxes, then Board 2 all boxes, etc.")
    print("=" * 70)
    
    # Define all servo boxes (even channel for up/down, odd channel for left/right)
    servo_boxes = [
        (0, 1),   # Box 1: channels 0 (U/D) and 1 (L/R)
        (2, 3),   # Box 2: channels 2 (U/D) and 3 (L/R)
        (4, 5),   # Box 3: channels 4 (U/D) and 5 (L/R)
        (6, 7),   # Box 4: channels 6 (U/D) and 7 (L/R)
        (8, 9),   # Box 5: channels 8 (U/D) and 9 (L/R)
        (10, 11), # Box 6: channels 10 (U/D) and 11 (L/R)
        (12, 13), # Box 7: channels 12 (U/D) and 13 (L/R)
        (14, 15)  # Box 8: channels 14 (U/D) and 15 (L/R)
    ]
    
    # Test each board completely before moving to the next board
    for board_num, pca in enumerate(boards, 1):
        print(f"\n{'='*20} TESTING BOARD {board_num} {'='*20}")
        
        # Test all boxes on this board
        for box_num, (up_down_channel, left_right_channel) in enumerate(servo_boxes, 1):
            test_single_servo_box(pca, board_num, box_num, up_down_channel, left_right_channel)
            
            # Wait between boxes (but not after the last box on the board)
            if box_num < len(servo_boxes):
                print(f"\nWaiting 2 seconds before next box on Board {board_num}...")
                time.sleep(2)
        
        # Wait between boards (but not after the last board)
        if board_num < len(boards):
            print(f"\nCompleted Board {board_num}. Waiting 3 seconds before Board {board_num + 1}...")
            time.sleep(3)

def main():
    print("EyeBox Left-Right and Up-Down Movement Test")
    print("Testing horizontal and vertical movement to validate cord connections")
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
        
        # Cycle all boards and boxes once:
        try:
            # Test all boxes sequentially (one at a time)
            test_all_boxes_sequentially(boards)
            
            print("\nWaiting 3 seconds before next cycle...")
            time.sleep(3)
                
        except KeyboardInterrupt:
            print(f"\nMovement test stopped by user")
            
    except KeyboardInterrupt:
        print("\nMovement test stopped by user")
    except Exception as e:
        print(f"Error during movement test: {e}")
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
        print("Movement test script terminated.")

if __name__ == "__main__":
    main()