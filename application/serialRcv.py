import serial
import sqlite3
import os
from enum import Enum
from datetime import datetime
import serial.tools.list_ports

for port in serial.tools.list_ports.comports():
    # This only works for adafruit feather 32u4 boards, if hardware is swapped id must change
    if port.hwid.__contains__("PID=239A:800C"):
        PORT = port.device

BAUD = 115200
DB_PATH = 'bms_data.db'


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


# Database setup
def init_db(db_path: str) -> sqlite3.Connection:
    """
    Open (or create) the SQLite database, enable WAL mode for better
    concurrent write performance, and ensure all tables exist.
    Returns the connection.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")  # safer + faster for frequent inserts
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        -- One row per logging session (each time the script is run)
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT NOT NULL
        );

        -- Raw frames: every packet received, before decoding
        -- Useful for post-hoc debugging of decoding bugs
        CREATE TABLE IF NOT EXISTS raw_frames (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL REFERENCES sessions(id),
            received_at TEXT NOT NULL,
            msg_id_hex  TEXT NOT NULL,
            payload_hex TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS basic (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id          INTEGER NOT NULL REFERENCES sessions(id),
            received_at         TEXT NOT NULL,
            pack_current        REAL,
            pack_inst_voltage   REAL,
            pack_soc            REAL,
            relay_state         INTEGER,
            checksum            INTEGER
        );

        CREATE TABLE IF NOT EXISTS bms_temp (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL REFERENCES sessions(id),
            received_at TEXT NOT NULL,
            pack_dcl    INTEGER,
            pack_ccl    INTEGER,
            high_temp   INTEGER,
            low_temp    INTEGER,
            checksum    INTEGER
        );

        CREATE TABLE IF NOT EXISTS strings (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id            INTEGER NOT NULL REFERENCES sessions(id),
            received_at           TEXT NOT NULL,
            high_cell_voltage     REAL,
            high_cell_voltage_id  INTEGER,
            low_cell_voltage      REAL,
            low_cell_voltage_id   INTEGER,
            checksum              INTEGER
        );

        CREATE TABLE IF NOT EXISTS battery_temp (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id          INTEGER NOT NULL REFERENCES sessions(id),
            received_at         TEXT NOT NULL,
            high_temp           INTEGER,
            high_thermistor_id  INTEGER,
            low_temp            INTEGER,
            low_thermistor_id   INTEGER,
            avg_temp            INTEGER,
            internal_temp       INTEGER,
            checksum            INTEGER
        );

        CREATE TABLE IF NOT EXISTS health (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id                INTEGER NOT NULL REFERENCES sessions(id),
            received_at               TEXT NOT NULL,
            pack_health               INTEGER,
            adaptive_total_capacity   INTEGER,
            input_supply_voltage      REAL,
            checksum                  INTEGER
        );

        CREATE TABLE IF NOT EXISTS cell (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id          INTEGER NOT NULL REFERENCES sessions(id),
            received_at         TEXT NOT NULL,
            cell_id             INTEGER,
            instant_voltage     REAL,
            internal_resistance INTEGER,
            open_voltage        REAL,
            checksum            INTEGER
        );
    """)
    conn.commit()
    return conn


def start_session(conn: sqlite3.Connection) -> int:
    """Insert a new session row and return its id."""
    cur = conn.execute(
        "INSERT INTO sessions (started_at) VALUES (?)",
        (datetime.now().isoformat(),)
    )
    conn.commit()
    return cur.lastrowid



# Serial / framing
ser = serial.Serial(PORT, BAUD, timeout=1)

def read_frame(ser):
    VALID_IDS = {m.value for m in MESSAGE_ID}

    buffer = bytearray()
    while True:
        b = ser.read(1)
        if not b:
            return None
        buffer.append(b[0])

        if len(buffer) > 4:
            buffer.pop(0)

        if len(buffer) == 4:
            msg_id = int.from_bytes(buffer, byteorder='big')
            if msg_id in VALID_IDS:
                break

    payload = bytearray()
    for i in range(8):
        b = ser.read(1)
        if not b:
            return None
        payload.append(b[0])
    return (buffer, payload)

# Decoding
def naturalizeData(msg_id, data):
    msg_id_value = int.from_bytes(msg_id[2:], byteorder='big')
    ID = MESSAGE_ID(msg_id_value)
    ID = ID.name

    if ID == 'BASIC':
        pack_current = float(0.1 * int.from_bytes(data[0:2], signed=True, byteorder='big'))
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
        open_voltage = round(float(0.0001 * int.from_bytes(data[5:7], signed=False, byteorder='big')), 5)
        checksum = int.from_bytes(data[7:], signed=False, byteorder='big')
        return ['CELL', cell_id, instant_voltage, internal_resistance, open_voltage, checksum]

    print("ERROR TRANSLATING DATA")
    return None



# Database writes
def store_frame(conn: sqlite3.Connection, session_id: int, msg_id: bytearray,
                payload: bytearray, decoded: list, received_at: str):
    """
    Write the raw frame and the decoded values to their respective tables.
    Both inserts happen in the same transaction so they stay in sync.
    """
    with conn:  # conn as context manager: auto-commits or rolls back on exception
        conn.execute(
            "INSERT INTO raw_frames (session_id, received_at, msg_id_hex, payload_hex) "
            "VALUES (?, ?, ?, ?)",
            (session_id, received_at, msg_id[2:].hex(), payload.hex())
        )

        msg_type = decoded[0]

        if msg_type == 'BASIC':
            _, pack_current, pack_inst_voltage, pack_soc, relay_state, checksum = decoded
            conn.execute(
                "INSERT INTO basic "
                "(session_id, received_at, pack_current, pack_inst_voltage, pack_soc, relay_state, checksum) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, received_at, pack_current, pack_inst_voltage, pack_soc, relay_state, checksum)
            )
        elif msg_type == 'BMS_TEMP':
            _, pack_dcl, pack_ccl, high_temp, low_temp, checksum = decoded
            conn.execute(
                "INSERT INTO bms_temp "
                "(session_id, received_at, pack_dcl, pack_ccl, high_temp, low_temp, checksum) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, received_at, pack_dcl, pack_ccl, high_temp, low_temp, checksum)
            )
        elif msg_type == 'STRINGS':
            _, high_cell_voltage, high_cell_voltage_id, low_cell_voltage, low_cell_voltage_id, checksum = decoded
            conn.execute(
                "INSERT INTO strings "
                "(session_id, received_at, high_cell_voltage, high_cell_voltage_id, low_cell_voltage, low_cell_voltage_id, checksum) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, received_at, high_cell_voltage, high_cell_voltage_id, low_cell_voltage, low_cell_voltage_id, checksum)
            )
        elif msg_type == 'BATTERY_TEMP':
            _, high_temp, high_thermistor_id, low_temp, low_thermistor_id, avg_temp, internal_temp, checksum = decoded
            conn.execute(
                "INSERT INTO battery_temp "
                "(session_id, received_at, high_temp, high_thermistor_id, low_temp, low_thermistor_id, avg_temp, internal_temp, checksum) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, received_at, high_temp, high_thermistor_id, low_temp, low_thermistor_id, avg_temp, internal_temp, checksum)
            )
        elif msg_type == 'HEALTH':
            _, pack_health, adaptive_total_capacity, input_supply_voltage, checksum = decoded
            conn.execute(
                "INSERT INTO health "
                "(session_id, received_at, pack_health, adaptive_total_capacity, input_supply_voltage, checksum) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, received_at, pack_health, adaptive_total_capacity, input_supply_voltage, checksum)
            )
        elif msg_type == 'CELL':
            _, cell_id, instant_voltage, internal_resistance, open_voltage, checksum = decoded
            conn.execute(
                "INSERT INTO cell "
                "(session_id, received_at, cell_id, instant_voltage, internal_resistance, open_voltage, checksum) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, received_at, cell_id, instant_voltage, internal_resistance, open_voltage, checksum)
            )


# Main loop
def serialRcv():
    conn = init_db(DB_PATH)
    session_id = start_session(conn)
    print(f"Started session {session_id} → {DB_PATH}")

    while True:
        frame = read_frame(ser)
        if not frame:
            print("No data in frame")
            continue

        msg_id, payload = frame
        print(f"Received frame --> MSG_ID: {msg_id[2:].hex()} : {payload.hex()}")

        decoded = naturalizeData(msg_id, payload)
        if decoded is None:
            print("Failed to decode frame, skipping")
            continue

        received_at = datetime.now().isoformat()
        store_frame(conn, session_id, msg_id, payload, decoded, received_at)


if __name__ == "__main__":
    serialRcv()