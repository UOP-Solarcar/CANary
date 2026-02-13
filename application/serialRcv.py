import serial

PORT = "COM3"          # Serial port
BAUD = 115200          # rate of transmission in bps

STX = 0x02             # start of serial frame
ETX = 0x03             # end of serial frame

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
            print("Received frame:", frame)