# Eye Wall

This is the python code for the eye wall.

## Hardware

- A Raspberry PI 5
- Adafruit PCA9685 16-Channel Servo Driver

## External Documentation

How to hook up and use the servo drivers: https://learn.adafruit.com/16-channel-pwm-servo-driver?view=all

## Instructions

1. Simply copy over the python files (or clone this repo).
2. Run `python3 -m venv .venv` to create the venv environment
3. `source .venv/bin/activate` to activate the environment
4. `pip3 install -r requirements.txt` to install dependencies
5. `python3 <file>.py` to run

Make sure to hook up the servos. All even pins are Left/Right and odd pins are Up/Down.
