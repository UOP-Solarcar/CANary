#!/usr/bin/env python3
"""
Convert CAN frame text format to binary data for serial port simulation.
Output format matches standard CAN frame structure.
"""

import struct
import sys

def parse_can_line(line):
    """Parse a line like: 0x6B0 D8 03 B6 4E 4B 00 03 A1"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    parts = line.split()
    if len(parts) < 2:
        return None
    
    # Parse CAN ID
    can_id_str = parts[0]
    if can_id_str.startswith('0x') or can_id_str.startswith('0X'):
        can_id = int(can_id_str, 16)
    else:
        return None
    
    # Parse data bytes
    data_bytes = []
    for i in range(1, min(9, len(parts))):  # Max 8 data bytes
        try:
            byte_val = int(parts[i], 16)
            data_bytes.append(byte_val)
        except ValueError:
            break
    
    # Pad to 8 bytes if needed
    while len(data_bytes) < 8:
        data_bytes.append(0)
    
    return can_id, data_bytes[:8]

def create_can_frame_binary(can_id, data_bytes):
    """
    Create binary CAN frame.
    Format: [CAN_ID (4 bytes, little-endian)] [DLC (1 byte)] [DATA (8 bytes)]
    """
    dlc = len([b for b in data_bytes if b != 0 or data_bytes.index(b) < 8])
    dlc = 8  # Always use 8 for consistency
    
    # Pack as: 4-byte CAN ID (little-endian), 1-byte DLC, 8 data bytes
    frame = struct.pack('<I', can_id) + struct.pack('B', dlc) + bytes(data_bytes)
    return frame

def main():
    input_file = 'can_test_data.txt'
    output_file = 'can_frames.bin'
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    frames = []
    with open(input_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            result = parse_can_line(line)
            if result:
                can_id, data_bytes = result
                frame = create_can_frame_binary(can_id, data_bytes)
                frames.append(frame)
                print(f"Frame {len(frames):3d}: ID=0x{can_id:08X} Data={' '.join(f'{b:02X}' for b in data_bytes)}")
    
    # Write all frames to binary file
    with open(output_file, 'wb') as f:
        for frame in frames:
            f.write(frame)
    
    print(f"\nGenerated {len(frames)} frames")
    print(f"Output written to: {output_file}")
    print(f"Total size: {len(frames) * 13} bytes ({len(frames)} frames × 13 bytes/frame)")

if __name__ == '__main__':
    main()
