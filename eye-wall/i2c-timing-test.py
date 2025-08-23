#!/usr/bin/env python3
"""
I2C Timing Diagnostic Script for EyeBox
Tests different timing strategies to identify optimal I2C communication patterns
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from consts import consts

# I2C addresses for all 8 boards
BOARD_ADDRESSES = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]

def pwm_to_duty_cycle(pwm_value):
    """Convert PWM value to duty cycle for PCA9685"""
    return int((pwm_value / 4095.0) * 65535)

def test_sequential_with_delays(boards, delay_ms=10):
    """Test sequential servo commands with configurable delays"""
    print(f"\n=== Sequential Test (delay: {delay_ms}ms) ===")
    
    start_time = time.time()
    commands_sent = 0
    errors = 0
    
    for board_num, pca in enumerate(boards):
        for channel in range(16):
            try:
                pca.channels[channel].duty_cycle = pwm_to_duty_cycle(consts.midpoint)
                commands_sent += 1
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
            except Exception as e:
                print(f"Error: Board {board_num+1}, Channel {channel}: {e}")
                errors += 1
    
    duration = time.time() - start_time
    print(f"Commands: {commands_sent}, Errors: {errors}, Time: {duration:.2f}s")
    return errors == 0

def test_board_batching(boards, inter_board_delay_ms=50):
    """Test sending all commands to one board before moving to next"""
    print(f"\n=== Board Batching Test (inter-board delay: {inter_board_delay_ms}ms) ===")
    
    start_time = time.time()
    commands_sent = 0
    errors = 0
    
    for board_num, pca in enumerate(boards):
        print(f"  Configuring Board {board_num+1}...")
        for channel in range(16):
            try:
                pca.channels[channel].duty_cycle = pwm_to_duty_cycle(consts.midpoint)
                commands_sent += 1
                time.sleep(0.005)  # 5ms between channels on same board
            except Exception as e:
                print(f"Error: Board {board_num+1}, Channel {channel}: {e}")
                errors += 1
        
        if inter_board_delay_ms > 0:
            time.sleep(inter_board_delay_ms / 1000.0)
    
    duration = time.time() - start_time
    print(f"Commands: {commands_sent}, Errors: {errors}, Time: {duration:.2f}s")
    return errors == 0

def test_eye_pair_batching(boards):
    """Test sending both channels for each eye together"""
    print(f"\n=== Eye Pair Batching Test ===")
    
    start_time = time.time()
    commands_sent = 0
    errors = 0
    
    for board_num, pca in enumerate(boards):
        print(f"  Configuring Board {board_num+1} eyes...")
        for eye_num in range(8):  # 8 eyes per board
            up_down_channel = eye_num * 2
            left_right_channel = eye_num * 2 + 1
            
            try:
                # Set both channels for this eye
                pca.channels[up_down_channel].duty_cycle = pwm_to_duty_cycle(consts.midpoint)
                time.sleep(0.005)
                pca.channels[left_right_channel].duty_cycle = pwm_to_duty_cycle(consts.midpoint)
                commands_sent += 2
                time.sleep(0.01)  # 10ms between eyes
            except Exception as e:
                print(f"Error: Board {board_num+1}, Eye {eye_num}: {e}")
                errors += 1
        
        time.sleep(0.05)  # 50ms between boards
    
    duration = time.time() - start_time
    print(f"Commands: {commands_sent}, Errors: {errors}, Time: {duration:.2f}s")
    return errors == 0

def main():
    print("EyeBox I2C Timing Diagnostic")
    print("Testing different I2C communication strategies")
    print("=" * 60)
    
    try:
        # Initialize I2C bus
        i2c = busio.I2C(board.SCL, board.SDA)
        
        # Initialize all PCA9685 boards
        boards = []
        for i, address in enumerate(BOARD_ADDRESSES):
            try:
                pca = PCA9685(i2c, address=address)
                pca.frequency = 50
                boards.append(pca)
                print(f"✓ Board {i+1} (0x{address:02X}) initialized")
            except Exception as e:
                print(f"✗ Board at 0x{address:02X} failed: {e}")
        
        if not boards:
            print("No boards found!")
            return
        
        print(f"\nTesting with {len(boards)} board(s), {len(boards) * 16} total channels")
        
        # Test different timing strategies
        strategies = [
            ("No delays", lambda: test_sequential_with_delays(boards, 0)),
            ("5ms delays", lambda: test_sequential_with_delays(boards, 5)),
            ("10ms delays", lambda: test_sequential_with_delays(boards, 10)),
            ("Board batching", lambda: test_board_batching(boards, 50)),
            ("Eye pair batching", lambda: test_eye_pair_batching(boards)),
        ]
        
        results = {}
        for strategy_name, test_func in strategies:
            print(f"\n{'='*20} {strategy_name} {'='*20}")
            success = test_func()
            results[strategy_name] = success
            time.sleep(1)  # Rest between tests
        
        # Summary
        print(f"\n{'='*60}")
        print("TIMING TEST RESULTS:")
        print(f"{'='*60}")
        for strategy, success in results.items():
            status = "✓ SUCCESS" if success else "✗ FAILED"
            print(f"{strategy:20} : {status}")
        
        print(f"\nRecommendation:")
        successful_strategies = [name for name, success in results.items() if success]
        if successful_strategies:
            print(f"Use: {successful_strategies[0]}")
        else:
            print("Consider reducing number of simultaneous servos or checking power supply")
            
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean shutdown
        try:
            for board_num, pca in enumerate(boards):
                for channel in range(16):
                    pca.channels[channel].duty_cycle = 0
                pca.deinit()
        except:
            pass

if __name__ == "__main__":
    main()
