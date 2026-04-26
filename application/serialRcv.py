import serial
import os
from enum import Enum
from datetime import datetime
import serial.tools.list_ports

for port in serial.tools.list_ports.comports():
    #This only works for adafruit feather 32u4 boards, if hardware is swapped id must change
    if port.hwid.__contains__("PID=239A:800C"):
        PORT = port.device

BAUD = 115200

class MESSAGE_ID(Enum):
    BASIC = 0x6B0
    BMS_TEMP = 0x6B1
    STRINGS = 0x6B2
    BATTERY_TEMP = 0x6B3
    HEALTH = 0x6B4
    CELL = 0x36

    def __len__(self):
        count = 0
        for _ in MESSAGE_ID:
            count += 1
        return count


ser = serial.Serial(PORT, BAUD, timeout=1)

def read_frame(ser):
    VALID_IDS = {m.value for m in MESSAGE_ID}
    
    # Wait for 4 byte Message ID
    buffer = bytearray()
    while True:
        b = ser.read(1)
        if not b:
            return None
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
    return (buffer, payload)

def naturalizeData(msg_id, data):
    msg_id_value = int.from_bytes(msg_id[2:], byteorder = 'big')
    ID = MESSAGE_ID(msg_id_value)
    ID = ID.name

    if ID == 'BASIC':
        pack_current = float(0.1 * int.from_bytes(data[0:2], signed=True, byteorder='big'))  # signed int, have to specify so method performs two's comp to decode
        pack_inst_voltage = round(float(0.1 * int.from_bytes(data[2:4], signed=False, byteorder='big')), 5)
        pack_soc = float(int.from_bytes(data[4:5], signed=False, byteorder='big'))
        relay_state = int.from_bytes(data[5:7], signed=False, byteorder='big')
        checksum = int.from_bytes(data[7:], signed=False, byteorder='big')
        return ['BASIC', pack_current, pack_inst_voltage, pack_soc, relay_state, checksum]
    elif ID == 'BMS_TEMP':
        pack_dcl = int.from_bytes(data[0:2], signed=False, byteorder='big')
        pack_ccl = int.from_bytes(data[2:4], signed=False, byteorder='big')
        high_temp = int.from_bytes(data[4:5], signed=False, byteorder='big')
        low_temp = int.from_bytes(data[5:6], signed=False, byteorder='big')
        checksum = int.from_bytes(data[6:], signed=False, byteorder='big')
        return ['BMS_TEMP', pack_dcl, pack_ccl, high_temp, low_temp, checksum]
    elif ID == 'STRINGS':
        high_cell_voltage = round(float(0.0001 * int.from_bytes(data[0:2], signed=False, byteorder='big')), 5)
        high_cell_voltage_id = int.from_bytes(data[2:3], signed=False, byteorder='big')
        low_cell_voltage = round(float(0.0001 * int.from_bytes(data[3:5], signed=False, byteorder='big')), 5)
        low_cell_voltage_id = int.from_bytes(data[5:6], signed=False, byteorder='big')
        checksum = int.from_bytes(data[6:], signed=False, byteorder='big')
        return ['STRINGS', high_cell_voltage, high_cell_voltage_id, low_cell_voltage, low_cell_voltage_id, checksum]
    elif ID == 'BATTERY_TEMP':
        high_temp = int.from_bytes(data[0:1], signed=False, byteorder='big')
        high_thermistor_id = int.from_bytes(data[1:2], signed=False, byteorder='big')
        low_temp = int.from_bytes(data[2:3], signed=False, byteorder='big')
        low_thermistor_id = int.from_bytes(data[3:4], signed=False, byteorder='big')
        avg_temp = int.from_bytes(data[4:5], signed=False, byteorder='big')
        internal_temp = int.from_bytes(data[5:6], signed=False, byteorder='big')
        checksum = int.from_bytes(data[6:], signed=False, byteorder='big')
        return ['BATTERY_TEMP', high_temp, high_thermistor_id, low_temp, low_thermistor_id, avg_temp, internal_temp, checksum]
    elif ID == 'HEALTH':
        pack_health = int.from_bytes(data[0:1], signed=False, byteorder='big')
        adaptive_total_capacity = int.from_bytes(data[1:3], signed=False, byteorder='big')
        input_supply_voltage = round(float(0.1 * int.from_bytes(data[3:5], signed=False, byteorder='big')), 5)
        checksum = int.from_bytes(data[5:], signed=False, byteorder='big')
        return ['HEALTH', pack_health, adaptive_total_capacity, input_supply_voltage, checksum]
    elif ID == 'CELL':
        cell_id = int.from_bytes(data[0:1], signed=False, byteorder='big')
        instant_voltage = round(float(0.0001 * int.from_bytes(data[1:3], signed=False, byteorder='big')), 5)
        internal_resistance = int.from_bytes(data[3:5], signed=False, byteorder='big')
        open_voltage = round(float (0.0001 * int.from_bytes(data[5:7], signed=False, byteorder='big')), 5)
        checksum = int.from_bytes(data[7:], signed=False, byteorder='big')
        return ['CELL', cell_id, instant_voltage, internal_resistance, open_voltage, checksum]
    print("ERROR TRANSLATING DATA")
    return

def serialRcv():
    f = open('data.csv', 'w')
    f.write("BASIC,pack_current,pack_inst_voltage,pack_soc,relay_state,checksum," \
           "BMS_TEMP,pack_dcl,pack_ccl,BMS_high_temp,BMS_low_temp,checksum," \
           "STRINGS,high_cell_voltage,high_cell_voltage_id,low_cell_voltage,low_cell_voltage_id,checksum," \
           "BATTERY_TEMP,cell_high_temp,high_thermistor_id,cell_low_temp,low_thermistor_id,avg_temp,internal_temp,checksum," \
           "HEALTH,pack_health,adaptive_total_capacity,input_supply_voltage,checksum," \
           "CELL,cell_id,instant_voltage,internal_resistance,open_voltage,checksum,timestamp\n")
    f.close()
    
    
    count = 0
    while True:
        frame = read_frame(ser)
        if frame:
            print("Received frame --> MSG_ID: ", frame[0][2:].hex(), ": ", frame[1].hex())
            print(frame[1])
            actual_data = naturalizeData(frame[0], frame[1])
            f = open('data.csv', 'a')
            f.write(actual_data[0] + ',')
            for data in actual_data[1:]:
                f.write(str(data) + ',')
            count = count + 1
            if (count == len(MESSAGE_ID)):
                f.write(str(datetime.now())+ '\n')
                count = 0
            f.close()
        else:
            print("No data in frame")

if __name__ == "__main__":
    serialRcv()