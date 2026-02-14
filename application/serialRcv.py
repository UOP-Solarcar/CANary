import serial
import os

if (os.name == "posix"): # sets the serial port
    PORT = "/dev/tty.usbmodem21101"
elif (os.name == "nt"):
    PORT = "COM3"

BAUD = 115200          # rate of transmission in bps

STX = 0x0A             # start of serial frame
ETX = 0x0A            # end of serial frame

ser = serial.Serial(PORT, BAUD, timeout=1)

def read_frame(ser):
    # Wait for start byte
    while True:
        b = ser.read(1)
        if not b:
            return None
        if b[0] == STX:
            break

    # Collect payload until ETX
    payload = bytearray()
    while True:
        b = ser.read(1)
        if not b:
            return None
        if b[0] == ETX:
            return bytes(payload)
        payload.append(b[0])

def serialRcv():
    while True:
        frame = read_frame(ser)
        if frame is not None:
            #print("Received frame:", frame.decode(encoding='utf-8'))
            None
        else:
            print("No data in frame")

if __name__ == "__main__":
    serialRcv()