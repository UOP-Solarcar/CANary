"""
csv_to_db.py  —  Import a legacy flat CSV into the BMS SQLite database.

The CSV was produced by the old serialRcv.py and has one row per packet
cycle with all six message types concatenated into a single wide row.
Because several column names repeat (e.g. "checksum" appears six times,
"BMS_high_temp" vs "cell_high_temp" differ from DB names), we parse by
column position rather than by name.

Usage:
    python csv_to_db.py <path/to/file.csv> [--db path/to/data.db]

The script creates a new session entry for each imported CSV file so the
data sits cleanly alongside any live-captured sessions.
"""

import argparse
import csv
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH_DEFAULT = "data.db"

# ---------------------------------------------------------------------------
# Column position map
#
# CSV header (with duplicates resolved by position):
# 0  BASIC  1  pack_current  2  pack_inst_voltage  3  pack_soc  4  relay_state  5  checksum(basic)
# 6  BMS_TEMP  7  pack_dcl  8  pack_ccl  9  BMS_high_temp  10  BMS_low_temp  11  checksum(bms)
# 12 STRINGS  13 high_cell_voltage  14 high_cell_voltage_id  15 low_cell_voltage  16 low_cell_voltage_id  17 checksum(strings)
# 18 BATTERY_TEMP  19 cell_high_temp  20 high_thermistor_id  21 cell_low_temp  22 low_thermistor_id  23 avg_temp  24 internal_temp  25 checksum(battery)
# 26 HEALTH  27 pack_health  28 adaptive_total_capacity  29 input_supply_voltage  30 checksum(health)
# 31 CELL  32 cell_id  33 instant_voltage  34 internal_resistance  35 open_voltage  36 checksum(cell)
# 37 timestamp
# ---------------------------------------------------------------------------

COL = {
    # basic
    "pack_current":           1,
    "pack_inst_voltage":      2,
    "pack_soc":               3,
    "relay_state":            4,
    "checksum_basic":         5,
    # bms_temp
    "pack_dcl":               7,
    "pack_ccl":               8,
    "bms_high_temp":          9,
    "bms_low_temp":          10,
    "checksum_bms":          11,
    # strings
    "high_cell_voltage":     13,
    "high_cell_voltage_id":  14,
    "low_cell_voltage":      15,
    "low_cell_voltage_id":   16,
    "checksum_strings":      17,
    # battery_temp
    "cell_high_temp":        19,
    "high_thermistor_id":    20,
    "cell_low_temp":         21,
    "low_thermistor_id":     22,
    "avg_temp":              23,
    "internal_temp":         24,
    "checksum_battery":      25,
    # health
    "pack_health":           27,
    "adaptive_total_capacity": 28,
    "input_supply_voltage":  29,
    "checksum_health":       30,
    # cell
    "cell_id":               32,
    "instant_voltage":       33,
    "internal_resistance":   34,
    "open_voltage":          35,
    "checksum_cell":         36,
    # shared
    "timestamp":             37,
}


# ---------------------------------------------------------------------------
# Database helpers (mirrors serialRcv.py so the schema is identical)
# ---------------------------------------------------------------------------

def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT NOT NULL
        );
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


def start_session(conn: sqlite3.Connection, label: str) -> int:
    cur = conn.execute(
        "INSERT INTO sessions (started_at) VALUES (?)",
        (label,)
    )
    conn.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Row parser
# ---------------------------------------------------------------------------

def parse_row(row: list[str]) -> dict:
    """
    Extract and cast every field from a positional CSV row.
    Returns a dict keyed by logical field name.
    Raises ValueError if the row is too short or a cast fails.
    """
    if len(row) < 38:
        raise ValueError(f"Row has only {len(row)} columns, expected 38")

    def f(key):
        return float(row[COL[key]])

    def i(key):
        return int(float(row[COL[key]]))   # int(float(...)) handles "3.0" → 3

    return {
        # basic
        "pack_current":           f("pack_current"),
        "pack_inst_voltage":      f("pack_inst_voltage"),
        "pack_soc":               f("pack_soc"),
        "relay_state":            i("relay_state"),
        "checksum_basic":         i("checksum_basic"),
        # bms_temp
        "pack_dcl":               i("pack_dcl"),
        "pack_ccl":               i("pack_ccl"),
        "bms_high_temp":          i("bms_high_temp"),
        "bms_low_temp":           i("bms_low_temp"),
        "checksum_bms":           i("checksum_bms"),
        # strings
        "high_cell_voltage":      f("high_cell_voltage"),
        "high_cell_voltage_id":   i("high_cell_voltage_id"),
        "low_cell_voltage":       f("low_cell_voltage"),
        "low_cell_voltage_id":    i("low_cell_voltage_id"),
        "checksum_strings":       i("checksum_strings"),
        # battery_temp
        "cell_high_temp":         i("cell_high_temp"),
        "high_thermistor_id":     i("high_thermistor_id"),
        "cell_low_temp":          i("cell_low_temp"),
        "low_thermistor_id":      i("low_thermistor_id"),
        "avg_temp":               i("avg_temp"),
        "internal_temp":          i("internal_temp"),
        "checksum_battery":       i("checksum_battery"),
        # health
        "pack_health":            i("pack_health"),
        "adaptive_total_capacity": i("adaptive_total_capacity"),
        "input_supply_voltage":   f("input_supply_voltage"),
        "checksum_health":        i("checksum_health"),
        # cell
        "cell_id":                i("cell_id"),
        "instant_voltage":        f("instant_voltage"),
        "internal_resistance":    i("internal_resistance"),
        "open_voltage":           f("open_voltage"),
        "checksum_cell":          i("checksum_cell"),
        # shared
        "timestamp":              row[COL["timestamp"]].strip(),
    }


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------

def import_csv(csv_path: str, db_path: str) -> None:
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        sys.exit(1)

    conn = init_db(db_path)

    # Use the CSV filename + current time as the session label so it's
    # distinguishable from live-captured sessions in the session selector.
    session_label = f"{csv_file.name}  (imported {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
    session_id = start_session(conn, session_label)
    print(f"Created session {session_id}: {session_label}")

    inserted = 0
    skipped  = 0

    with open(csv_file, newline="") as fh:
        reader = csv.reader(fh)
        next(reader)  # skip header

        for line_num, raw_row in enumerate(reader, start=2):
            try:
                d = parse_row(raw_row)
            except (ValueError, IndexError) as exc:
                print(f"  Line {line_num}: skipped — {exc}")
                skipped += 1
                continue

            ts = d["timestamp"]

            with conn:
                conn.execute(
                    "INSERT INTO basic "
                    "(session_id, received_at, pack_current, pack_inst_voltage, pack_soc, relay_state, checksum) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session_id, ts, d["pack_current"], d["pack_inst_voltage"],
                     d["pack_soc"], d["relay_state"], d["checksum_basic"])
                )
                conn.execute(
                    "INSERT INTO bms_temp "
                    "(session_id, received_at, pack_dcl, pack_ccl, high_temp, low_temp, checksum) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session_id, ts, d["pack_dcl"], d["pack_ccl"],
                     d["bms_high_temp"], d["bms_low_temp"], d["checksum_bms"])
                )
                conn.execute(
                    "INSERT INTO strings "
                    "(session_id, received_at, high_cell_voltage, high_cell_voltage_id, low_cell_voltage, low_cell_voltage_id, checksum) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session_id, ts, d["high_cell_voltage"], d["high_cell_voltage_id"],
                     d["low_cell_voltage"], d["low_cell_voltage_id"], d["checksum_strings"])
                )
                conn.execute(
                    "INSERT INTO battery_temp "
                    "(session_id, received_at, high_temp, high_thermistor_id, low_temp, low_thermistor_id, avg_temp, internal_temp, checksum) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (session_id, ts, d["cell_high_temp"], d["high_thermistor_id"],
                     d["cell_low_temp"], d["low_thermistor_id"],
                     d["avg_temp"], d["internal_temp"], d["checksum_battery"])
                )
                conn.execute(
                    "INSERT INTO health "
                    "(session_id, received_at, pack_health, adaptive_total_capacity, input_supply_voltage, checksum) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, ts, d["pack_health"], d["adaptive_total_capacity"],
                     d["input_supply_voltage"], d["checksum_health"])
                )
                conn.execute(
                    "INSERT INTO cell "
                    "(session_id, received_at, cell_id, instant_voltage, internal_resistance, open_voltage, checksum) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session_id, ts, d["cell_id"], d["instant_voltage"],
                     d["internal_resistance"], d["open_voltage"], d["checksum_cell"])
                )

            inserted += 1

    conn.close()
    print(f"Done. {inserted} rows imported, {skipped} skipped.")
    print(f"Database: {Path(db_path).resolve()}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import a legacy BMS CSV file into the SQLite database."
    )
    parser.add_argument("csv", help="Path to the CSV file to import")
    parser.add_argument(
        "--db",
        default=DB_PATH_DEFAULT,
        help=f"Path to the SQLite database (default: {DB_PATH_DEFAULT})",
    )
    args = parser.parse_args()
    import_csv(args.csv, args.db)
