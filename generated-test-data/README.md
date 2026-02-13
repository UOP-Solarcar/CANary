# CAN Bus Test Data Generator

## Overview
This package generates realistic CAN frame data for testing BMS (Battery Management System) and Motor Controller parsing functions.

## Files Included

1. **can_test_data.txt** - Human-readable CAN frame data in hex format
2. **can_frames.bin** - Binary CAN frame data ready for serial port simulation
3. **convert_to_binary.py** - Conversion script

## Data Format

### Binary Frame Structure
Each CAN frame in the binary file is 13 bytes:
```
[CAN_ID: 4 bytes, little-endian] [DLC: 1 byte] [DATA: 8 bytes]
```

Example:
```
B0 06 00 00 | 08 | D8 03 B6 4E 4B 00 03 A1
└─CAN ID──┘   DLC  └────────DATA────────┘
  0x6B0        8    8 data bytes
```

### Message Types Included

#### BMS Messages (IDs: 0x6B0-0x6B4)
- **0x6B0**: Pack current, voltage, SOC, relay state
- **0x6B1**: Discharge/charge limits, temperatures
- **0x6B2**: Cell voltage high/low values and IDs
- **0x6B3**: Temperature readings from thermistors
- **0x6B4**: Pack health, capacity, supply voltage

#### Cell Voltage Messages (ID: 0x36)
- Individual cell voltages (24 cells in the pack)
- Internal resistance measurements
- Open circuit voltages

#### Motor Controller Messages (IDs: 0x8000xxxx)
Four motor controllers (IDs 0x01-0x04), each sending:
- **Status 1 (0x80000900)**: RPM, current, duty cycle
- **Status 2 (0x80000E00)**: Amp-hours used/charged
- **Status 3 (0x80000F00)**: Watt-hours used/charged
- **Status 4 (0x80001000)**: Temperatures, input current, PID position
- **Status 5 (0x80001B00)**: Tachometer, input voltage
- **Status 6 (0x80003A00)**: ADC values, PPM

## Simulation Scenario

The data simulates a mid-race scenario:
- **SOC**: Starting at 75%, gradually decreasing
- **Load**: ~40A discharge, moderate acceleration
- **Temperature**: Rising from 30°C to ~45°C
- **Motor RPMs**: ~3600-3900 RPM (variable across 4 motors)
- **Pack Voltage**: ~95-96V (24S configuration)
- **Cell Voltages**: 3.98-4.05V per cell

## Usage Examples

### Reading Binary Data in C++
```cpp
#include <fstream>
#include <linux/can.h>

std::ifstream file("can_frames.bin", std::ios::binary);
while (file) {
    can_frame frame;
    uint8_t dlc;
    
    file.read((char*)&frame.can_id, 4);
    file.read((char*)&dlc, 1);
    file.read((char*)frame.data, 8);
    
    if (file) {
        frame.can_dlc = dlc;
        parse_frame(frame);  // Your parsing function
    }
}
```

### Simulating Serial Reception
```cpp
// Stream data byte-by-byte to simulate serial input
std::ifstream file("can_frames.bin", std::ios::binary);
char byte;
while (file.get(byte)) {
    serial_buffer.push(byte);
    // Process when frame complete (13 bytes)
    if (serial_buffer.size() >= 13) {
        process_can_frame(serial_buffer);
    }
}
```

### Converting Custom Data
```bash
# Edit can_test_data.txt with your own frames
# Then regenerate binary:
python3 convert_to_binary.py can_test_data.txt output.bin
```

## Data Characteristics

### BMS Pack (24S12P Samsung INR21700-50S)
- Nominal voltage: 86.4V (3.6V × 24)
- Capacity: 60Ah (5A × 12P)
- Cell voltage range: 3.0V - 4.2V
- Operating temp: -20°C to 60°C

### Motor Controllers (4x)
- Extended CAN IDs with bit 31 set (0x80000000)
- Controller IDs: 0x01, 0x02, 0x03, 0x04
- Status messages at different intervals

## Frame Timing
The data includes multiple cycles of status updates:
1. Initial state (frames 1-53)
2. Second cycle with increasing load (frames 54-70)
3. Third cycle with higher temperatures (frames 71-88)
4. Final state updates (frames 89-97)

Total: 97 frames (1,261 bytes)

## Checksums
Each BMS message includes a checksum in the last byte. The test data uses realistic but arbitrary checksum values. For production use, implement proper checksum calculation based on your BMS protocol.

## Notes
- All multi-byte integers use big-endian byte order (network byte order)
- Motor controller messages use extended CAN IDs (29-bit)
- BMS messages use standard CAN IDs (11-bit)
- The parse_frame function expects frames with byte-swapped integers
