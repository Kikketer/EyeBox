#!/usr/bin/env python3
"""
Left-Right and Up-Down Movement Test for EyeBox
Tests boards by cycling servos through left-right movements, then up-down movements
to validate cord connections.

Usage:
    python3 direction-test-slow.py [board_number]
    
Examples:
    python3 direction-test-slow.py        # Test ALL detected boards sequentially
    python3 direction-test-slow.py 1      # Test board 1 only
    python3 direction-test-slow.py 3      # Test board 3 only

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
import argparse
import sys
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
    print("Testing: CENTER -> UP -> DOWN -> LEFT -> RIGHT -> CENTER")
    print("-" * 50)
    
    # Center both servos before starting the directional test
    try:
        pca.channels[up_down_channel].duty_cycle = pwm_to_duty_cycle(CENTER_POSITION)
        print(f"  Board {board_num}, Channel {up_down_channel:2d} (U/D): PWM {CENTER_POSITION} ✓ (center)")
    except Exception as e:
        print(f"  Board {board_num}, Channel {up_down_channel:2d} (U/D): Error - {e} ✗ (center)")
    try:
        pca.channels[left_right_channel].duty_cycle = pwm_to_duty_cycle(CENTER_POSITION)
        print(f"  Board {board_num}, Channel {left_right_channel:2d} (L/R): PWM {CENTER_POSITION} ✓ (center)")
    except Exception as e:
        print(f"  Board {board_num}, Channel {left_right_channel:2d} (L/R): Error - {e} ✗ (center)")
    print(f"Board {board_num} Box {box_number} centered - Hold for 1.0 seconds")
    time.sleep(1.0)

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

def test_single_board(pca, board_num):
    """Test all servo boxes on a single board"""
    print(f"Starting sequential box testing for Board {board_num}...")
    print("Each box consists of one up/down servo (even channel) + one left/right servo (odd channel)")
    print("Box pairs: (0,1), (2,3), (4,5), (6,7), (8,9), (10,11), (12,13), (14,15)")
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
    
    print(f"\n{'='*20} TESTING BOARD {board_num} {'='*20}")
    
    # Test all boxes on this board
    for box_num, (up_down_channel, left_right_channel) in enumerate(servo_boxes, 1):
        test_single_servo_box(pca, board_num, box_num, up_down_channel, left_right_channel)
        
        # Wait between boxes (but not after the last box)
        if box_num < len(servo_boxes):
            print(f"\nWaiting 2 seconds before next box on Board {board_num}...")
            time.sleep(2)

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

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="EyeBox Left-Right and Up-Down Movement Test. Provide a board number to test only that board, or leave empty to test all boards sequentially.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Board numbering (1-indexed):
  Board 1: Address 0x40 (no jumpers)
  Board 2: Address 0x41 (A0 jumper soldered)  
  Board 3: Address 0x42 (A1 jumper soldered)
  Board 4: Address 0x43 (A0 + A1 jumpers soldered)
  Board 5: Address 0x44 (A2 jumper soldered)
  Board 6: Address 0x45 (A0 + A2 jumpers soldered)
  Board 7: Address 0x46 (A1 + A2 jumpers soldered)
  Board 8: Address 0x47 (A0 + A1 + A2 jumpers soldered)

Examples:
  python3 direction-test-slow.py        # Test ALL detected boards sequentially
  python3 direction-test-slow.py 1      # Test board 1 only
  python3 direction-test-slow.py 3      # Test board 3 only
        """
    )
    
    parser.add_argument(
        'board_number',
        type=int,
        nargs='?',
        default=None,
        help='Board number to test (1-8). Leave empty to test all boards sequentially.'
    )
    
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_arguments()
    board_number = args.board_number
    
    print("EyeBox Left-Right and Up-Down Movement Test")
    
    # Prepare containers for one or many boards
    pca_instances = []
    pca = None
    try:
        # Initialize I2C bus
        i2c = busio.I2C(board.SCL, board.SDA)
        
        if board_number is not None:
            # Validate board number
            if board_number < 1 or board_number > 8:
                print(f"Error: Board number must be between 1 and 8, got {board_number}")
                sys.exit(1)
            
            # Single-board mode
            board_address = BOARD_ADDRESSES[board_number - 1]
            print(f"Testing Board {board_number} (Address: 0x{board_address:02X})")
            print("Testing horizontal and vertical movement to validate cord connections")
            print("=" * 60)
            
            # Initialize the specified PCA9685 board
            try:
                pca = PCA9685(i2c, address=board_address)
                pca.frequency = 50  # Standard servo frequency (50Hz)
                print(f"✓ Board {board_number} (0x{board_address:02X}) initialized successfully")
                pca_instances.append(pca)
            except Exception as e:
                print(f"✗ Error: Could not initialize board {board_number} at address 0x{board_address:02X}: {e}")
                print("Check wiring and address configuration.")
                return
            
            print("Press Ctrl+C to stop the test at any time")
            print("-" * 60)
            
            # Test the specified board
            try:
                test_single_board(pca, board_number)
                print(f"\nBoard {board_number} test complete!")
            except KeyboardInterrupt:
                print(f"\nMovement test stopped by user")
        else:
            # All-boards mode: attempt to initialize all boards, keep the ones that succeed
            print("No board number provided; attempting to initialize ALL boards and test sequentially...")
            print("Testing horizontal and vertical movement to validate cord connections")
            print("=" * 60)
            
            for idx, addr in enumerate(BOARD_ADDRESSES, start=1):
                try:
                    p = PCA9685(i2c, address=addr)
                    p.frequency = 50
                    pca_instances.append(p)
                    print(f"✓ Board {idx} (0x{addr:02X}) initialized successfully")
                except Exception as e:
                    print(f"✗ Skipping Board {idx} (0x{addr:02X}): {e}")
            
            if not pca_instances:
                print("No boards could be initialized. Check wiring and address configuration.")
                return
            
            print("Press Ctrl+C to stop the test at any time")
            print("-" * 60)
            
            # Run the sequential test across all initialized boards
            try:
                test_all_boxes_sequentially(pca_instances)
                print("\nAll-board sequential test complete!")
            except KeyboardInterrupt:
                print("\nMovement test stopped by user")
        
    except KeyboardInterrupt:
        print("\nMovement test stopped by user")
    except Exception as e:
        print(f"Error during movement test: {e}")
    finally:
        # Clean shutdown - turn off all servos
        try:
            if pca_instances:
                print("\nShutting down servos...")
                for idx, p in enumerate(pca_instances, start=1):
                    try:
                        for channel in range(16):
                            p.channels[channel].duty_cycle = 0
                        p.deinit()
                        print(f"Board {idx} shutdown complete")
                    except Exception:
                        pass
        except:
            pass
        print("Movement test script terminated.")

if __name__ == "__main__":
    main()