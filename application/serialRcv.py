import serial
import os
from enum import Enum 

if (os.name == "posix"): # sets the serial port
    PORT = "/dev/tty.usbmodem21101"
elif (os.name == "nt"):
    PORT = "COM3"

BAUD = 115200          # rate of transmission in bps

class MESSAGE_ID(Enum):
    BASIC = 0x6B0
    BMS_TEMP = 0x6B1
    STRINGS = 0x6B2
    BATTERY_TEMP = 0x6B3
    HEALTH = 0x6B4
    CELL = 0x36


ser = serial.Serial(PORT, BAUD, timeout=1)

def read_frame(ser):
    # Wait for start byte
    while True:
        b = ser.read(1)
        if not b:
            return None
        try:
            MESSAGE_ID(b)
            break
        except ValueError:
            pass    # suppress error output 

    # Collect 8 byte payload
    payload = bytearray()
    for i in range(8):
        b = ser.read(1)
        if not b:
            return None
        payload.append(b[0])
    return payload

def serialRcv():
    while True:
        frame = read_frame(ser)
        if frame:
            print("Received frame:", frame.decode(encoding='utf-8'))
        else:
            print("No data in frame")

if __name__ == "__main__":
    serialRcv()