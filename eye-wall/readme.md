# Eye Wall

This is the python code for the eye wall.

## Hardware

- A Raspberry PI 5
- Adafruit PCA9685 16-Channel Servo Driver (piles of them)
- Servos and the EyeBox model
- Xbox 360 Kinect v1

## External Documentation

How to hook up and use the servo drivers: https://learn.adafruit.com/16-channel-pwm-servo-driver?view=all

Simply attach the Kinect via USB (make sure to have that extra power as well).

## Instructions

1. Simply copy over the python files (or clone this repo).
2. Run `python3 -m venv .venv` to create the venv environment
3. `source .venv/bin/activate` to activate the environment
4. `pip3 install -r requirements.txt` to install dependencies
5. `python3 <file>.py` to run

Make sure to hook up the servos. All even pins are Left/Right and odd pins are Up/Down.

## Typical Eye Wall Runs:

Run `synced-eyes.py` to have the eyes all look similar directions at the same time. This is a nice simple file for just having the eyes be random but kind of scary since they look at the same thing at the same time. Useful for when you don't have the kinect attached.

Run `focus-eyes.py` when you have a kinect attached, this will have the eyes focus on the closest object.
