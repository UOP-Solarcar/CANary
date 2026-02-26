import serial
import os
from enum import Enum 

if (os.name == "posix"): # sets the serial port
    PORT = "/dev/tty.usbmodem21101"
elif (os.name == "nt"):
    PORT = "COM3"

BAUD = 115200          # rate of transmission in bps

class MESSAGE_ID(Enum):
    BASIC = 0x6B0   # in Python Hex value is just another representation of integer. So can do operation on value as if it is integer
    BMS_TEMP = 0x6B1
    STRINGS = 0x6B2
    BATTERY_TEMP = 0x6B3
    HEALTH = 0x6B4
    CELL = 0x36


ser = serial.Serial(PORT, BAUD, timeout=1)

def read_frame(ser):
    VALID_IDS = {m.value for m in MESSAGE_ID}
    
    # Wait for 4 byte Message ID
    buffer = bytearray()
    while True:
        b = ser.read(1)
        if not b:
            return None
        '''
        append requires integer, so this converts byte to integer representation,
        and then converts it back into bytes object when appending
        '''
        buffer.append(b[0])

        # Keep only last 4 bytes (sliding window)
        if len(buffer) > 4:
            buffer.pop(0)
        
        if len(buffer) == 4:
            msg_id = int.from_bytes(buffer, byteorder='big')
            if msg_id in VALID_IDS:
                break

    # Collect 8 byte payload
    payload = bytearray()
    for i in range(8):
        b = ser.read(1)
        if not b:
            return None
        payload.append(b[0])
    return (hex(msg_id), payload)

def serialRcv():
    while True:
        frame = read_frame(ser)
        if frame:
            print("Received frame --> MSG_ID: ", frame[0], ": ", frame[1].hex())
            #print("Received frame:", frame.decode(encoding='utf-8'))
        else:
            print("No data in frame")

if __name__ == "__main__":
    serialRcv()