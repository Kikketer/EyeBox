/*************************************************** 
  This is an example for our Adafruit 16-channel PWM & Servo driver
  Servo test - this will drive 8 servos, one after the other on the
  first 8 pins of the PCA9685

  Pick one up today in the adafruit shop!
  ------> http://www.adafruit.com/products/815
  
  These drivers use I2C to communicate, 2 pins are required to  
  interface.

  Adafruit invests time and resources providing this open source code, 
  please support Adafruit and open-source hardware by purchasing 
  products from Adafruit!

  Written by Limor Fried/Ladyada for Adafruit Industries.  
  BSD license, all text above must be included in any redistribution
 ****************************************************/

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// called this way, it uses the default address 0x40
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();
// you can also call it with a different address you want
//Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x41);
// you can also call it with a different address and I2C interface
//Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40, Wire);

// Depending on your servo make, the pulse width min and max may vary, you 
// want these to be as small/large as possible without hitting the hard stop
// for max range. You'll have to tweak them as necessary to match the servos you
// have!
// Blue servos are 125 to 499 (could go lower but I found it to be a good 180 degree at this limit)
// Bulk blue servos are: 
#define SERVOMIN  125 // This is the 'minimum' pulse length count (out of 4096)
#define SERVOMAX  499 // This is the 'maximum' pulse length count (out of 4096)
#define SERVO_FREQ 50 // Analog servos run at ~50 Hz updates

const int midpoint=((SERVOMAX - SERVOMIN) / 2) + SERVOMIN + 20;

const uint8_t ledPin = 13;

// Left is positive, right is negative
const uint8_t leftRightExtreme = 70;
const uint8_t eyeRightExtreme = 80; // Right goes negative
const uint8_t eyeLeftExtreme = 50;
const uint8_t eyeDownExtreme = 50; // Down is negative
const uint8_t eyeUpExtreme = 30;

void setup() {
  Serial.begin(9600);
  // pinMode(xPinIn, INPUT);
  // pinMode(yPinIn, INPUT);

  pwm.begin();
  pwm.setOscillatorFrequency(27000000);
  pwm.setPWMFreq(SERVO_FREQ);  // Analog servos run at ~50 Hz updates

  // Setup random using an unused analog-in due to electrical noise
  randomSeed(analogRead(A5));

  pinMode(ledPin, OUTPUT);

  delay(1);
}

void loop() {
  // Just to center the drives (pins 0-3):
  for (int currentPin = 0; currentPin <= 3; currentPin++) {
    pwm.setPWM(currentPin, 0, midpoint);
  }
  // Note you'll want to attach the bar only after waiting like 10 seconds on pin 0 (LED on)

  // Left extreme test (pins 4-7):
  // for (int currentPin = 4; currentPin <= 7; currentPin++) {
  //   pwm.setPWM(currentPin, 0, SERVOMIN);
  // }
  // Left eye test (pins 8-11):
  for (int currentPin = 8; currentPin <= 11; currentPin++) {
    pwm.setPWM(currentPin, 0, midpoint - eyeRightExtreme);
  }
  // Show the light to say that we are at the start of this loop
  digitalWrite(ledPin, HIGH);
  delay(5000);
  digitalWrite(ledPin, LOW);

  // Up eye test (pins 12-15):
  for (int currentPin = 12; currentPin <= 15; currentPin++) {
    pwm.setPWM(currentPin, 0, midpoint - eyeDownExtreme);
  }
  delay(5000);

  // Right extreme test (pins 4-7):
  // for (int currentPin = 4; currentPin <= 7; currentPin++) {
  //   pwm.setPWM(currentPin, 0, SERVOMAX);
  // }
  // Right eye test (pins 8-11):
  for (int currentPin = 8; currentPin <= 11; currentPin++) {
    pwm.setPWM(currentPin, 0, midpoint + eyeLeftExtreme);
  }
  delay(5000);

  // Up eye test (pins 12-15):
  for (int currentPin = 12; currentPin <= 15; currentPin++) {
    pwm.setPWM(currentPin, 0, midpoint + eyeUpExtreme);
  }
  delay(5000);
}
