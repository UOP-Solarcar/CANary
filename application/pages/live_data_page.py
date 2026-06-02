from datetime import datetime
from pathlib import Path
import sqlite3
import streamlit as st
import altair as alt
import pandas as pd
import numpy as np

DB_PATH = str(Path(__file__).parent.parent / "data.db")

# Fault Thresholds
TRIP_I_HI_dA  =  100.0
TRIP_I_LO_dA  = -42.5
TRIP_V_HI_dV  =  95.0
TRIP_V_LO_dV  =  78.0
TRIP_T_HI_C   =  45
CELL_V_HI_ct  =  4.2000
CELL_V_LO_ct  =  2.5000

# SOC / OCV lookup table
_SOC_POINTS = np.array([
    0.00, 0.02, 0.05, 0.08, 0.10, 0.13, 0.15, 0.20, 0.25, 0.30,
    0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80,
    0.85, 0.88, 0.90, 0.93, 0.95, 0.97, 1.00
])
_OCV_POINTS = np.array([
    2.50, 2.92, 3.15, 3.35, 3.44, 3.51, 3.55, 3.60, 3.63, 3.66,
    3.68, 3.70, 3.71, 3.72, 3.73, 3.75, 3.77, 3.79, 3.82, 3.86,
    3.91, 3.96, 4.00, 4.06, 4.10, 4.15, 4.20
])
CELLS_IN_SERIES = 23
_PACK_OCV_POINTS = _OCV_POINTS * CELLS_IN_SERIES


# Database helpers
def get_conn() -> sqlite3.Connection:
    if not Path(DB_PATH).exists():
        st.error(f"Database not found: {DB_PATH}")
        st.stop()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def load_data(session_id: int | None = None) -> pd.DataFrame:
    """
    Query each message table independently and join on nearest timestamp
    using pandas merge_asof. This avoids a SQLite limitation where outer
    query column references (e.g. b.received_at) are not resolvable inside
    a correlated subquery's ORDER BY clause.
    """
    conn = get_conn()

    # Resolve session
    if session_id is None:
        row = conn.execute("SELECT MAX(id) FROM sessions").fetchone()
        if row is None or row[0] is None:
            conn.close()
            return pd.DataFrame()
        session_id = row[0]

    def query(table, cols):
        return pd.read_sql_query(
            f"SELECT received_at, {cols} FROM {table} "
            f"WHERE session_id = ? ORDER BY received_at ASC",
            conn, params=(session_id,)
        )

    basic   = query("basic",
                    "pack_current, pack_inst_voltage, pack_soc, relay_state")
    bms     = query("bms_temp",
                    "pack_dcl, pack_ccl, "
                    "high_temp AS BMS_high_temp, low_temp AS BMS_low_temp")
    strings = query("strings",
                    "high_cell_voltage, high_cell_voltage_id, "
                    "low_cell_voltage, low_cell_voltage_id")
    battery = query("battery_temp",
                    "high_temp AS cell_high_temp, high_thermistor_id, "
                    "low_temp AS cell_low_temp, low_thermistor_id, avg_temp, internal_temp")
    health  = query("health",
                    "pack_health, adaptive_total_capacity, input_supply_voltage")
    cell    = query("cell",
                    "cell_id, instant_voltage, internal_resistance, open_voltage")
    conn.close()

    if basic.empty:
        return pd.DataFrame()

    for df in [basic, bms, strings, battery, health, cell]:
        df["received_at"] = pd.to_datetime(df["received_at"])

    result = basic.rename(columns={"received_at": "timestamp"})
    for other in [bms, strings, battery, health, cell]:
        if other.empty:
            continue
        result = pd.merge_asof(
            result, other.sort_values("received_at"),
            left_on="timestamp", right_on="received_at",
            direction="nearest"
        )
        result = result.drop(columns=["received_at"])

    return result

def latest_received_at() -> datetime | None:
    """Return the most recent received_at timestamp across ALL tables."""
    conn = get_conn()
    tables = ["basic", "bms_temp", "strings", "battery_temp", "health", "cell"]
    union = " UNION ALL ".join(
        f"SELECT MAX(received_at) AS t FROM {tbl}" for tbl in tables
    )
    row = conn.execute(f"SELECT MAX(t) FROM ({union})").fetchone()
    conn.close()
    if row and row[0]:
        return datetime.fromisoformat(row[0])
    return None


def available_sessions() -> list[dict]:
    """Return all sessions as a list of dicts with keys id and started_at."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, started_at FROM sessions ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "started_at": r["started_at"]} for r in rows]


# SOC helpers 
def pack_voltage_to_soc(pack_voltage: float, clamp: bool = True) -> float:
    v_min = _PACK_OCV_POINTS[0]
    v_max = _PACK_OCV_POINTS[-1]
    if not clamp and not (v_min <= pack_voltage <= v_max):
        raise ValueError(
            f"pack_voltage {pack_voltage:.2f} V is outside valid range "
            f"[{v_min:.1f} V, {v_max:.1f} V]."
        )
    soc_fraction = np.interp(pack_voltage, _PACK_OCV_POINTS, _SOC_POINTS)
    return round(float(soc_fraction * 100), 2)


def cell_voltage_to_soc(cell_voltage: float, clamp: bool = True) -> float:
    return pack_voltage_to_soc(cell_voltage * CELLS_IN_SERIES, clamp=clamp)


# Data-transform helpers 
def soc_update_data() -> pd.DataFrame:
    df_raw = st.session_state.data
    df = df_raw[["timestamp", "pack_soc", "pack_inst_voltage", "pack_current"]].copy()
    df["watts"] = None
    for i in df.index:
        df.loc[i, "pack_soc"] = pack_voltage_to_soc(df.loc[i, "pack_inst_voltage"])
        df.loc[i, "watts"] = int(df.loc[i, "pack_inst_voltage"] * df.loc[i, "pack_current"])
    df = df.drop(columns=["pack_inst_voltage", "pack_current"])
    df.columns = ["timestamp", "pack_soc", "watts"]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["pack_soc"]  = pd.to_numeric(df["pack_soc"],  errors="coerce")
    df["watts"]     = pd.to_numeric(df["watts"],     errors="coerce")
    df = df.dropna().sort_values("timestamp").reset_index(drop=True)
    return df

def temp_update_data() -> pd.DataFrame:
    df_raw = st.session_state.data
    df = df_raw[["timestamp", "cell_high_temp", "cell_low_temp", "avg_temp"]].copy()
    df.columns = ["timestamp", "high_temp", "low_temp", "avg_temp"]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["high_temp"] = pd.to_numeric(df["high_temp"], errors="coerce")
    df["low_temp"]  = pd.to_numeric(df["low_temp"],  errors="coerce")
    df["avg_temp"]  = pd.to_numeric(df["avg_temp"],  errors="coerce")
    df = df.dropna().sort_values("timestamp").reset_index(drop=True)
    return df.melt(
        id_vars="timestamp",
        value_vars=["high_temp", "low_temp", "avg_temp"],
        var_name="series",
        value_name="temperature",
    )

def compute_battery_energy() -> int:
    df_wh = st.session_state.data.copy()
    df_wh["timestamp"] = pd.to_datetime(df_wh["timestamp"])
    df_wh = df_wh.sort_values("timestamp").reset_index(drop=True)
    df_wh["dt"] = df_wh["timestamp"].diff().dt.total_seconds()
    df_wh = df_wh.dropna(subset=["dt"])
    df_wh["power"] = -df_wh["pack_current"] * df_wh["pack_inst_voltage"]
    df_wh["energy_Wh"] = df_wh["power"] * df_wh["dt"] / 3600.0
    return int(df_wh["energy_Wh"].sum())

def fault_detection() -> pd.DataFrame:
    df = st.session_state.data.sort_values("timestamp", ascending=False).reset_index(drop=True)[:1000]
    fault_mask = (
        (df["BMS_high_temp"]     >= TRIP_T_HI_C)  |
        (df["pack_current"]       > TRIP_I_HI_dA)  |
        (df["pack_current"]       < TRIP_I_LO_dA)  |
        (df["pack_inst_voltage"]  > TRIP_V_HI_dV)  |
        (df["pack_inst_voltage"]  < TRIP_V_LO_dV)  |
        (df["high_cell_voltage"] >= CELL_V_HI_ct)  |
        (df["low_cell_voltage"]  <= CELL_V_LO_ct)
    )
    faults = df[fault_mask].copy()
    st.write("Faults (" + str(len(faults)) + ")")
    return faults

def describe_faults(row) -> str:
    messages = []
    if row["BMS_high_temp"] >= TRIP_T_HI_C:
        messages.append(f"Over-temp: {row['BMS_high_temp']} °C at {pd.to_datetime(row['timestamp']).strftime('%H:%M:%S')}\n")
    if row["pack_current"] > TRIP_I_HI_dA:
        messages.append(f"Over-current: {row['pack_current'] / 10:.1f} A at {pd.to_datetime(row['timestamp']).strftime('%H:%M:%S')}\n")
    if row["pack_current"] < TRIP_I_LO_dA:
        messages.append(f"Charge over-current: {row['pack_current'] / 10:.1f} A at {pd.to_datetime(row['timestamp']).strftime('%H:%M:%S')}\n")
    if row["pack_inst_voltage"] > TRIP_V_HI_dV:
        messages.append(f"Pack over-voltage: {row['pack_inst_voltage'] / 10:.1f} V at {pd.to_datetime(row['timestamp']).strftime('%H:%M:%S')}\n")
    if row["pack_inst_voltage"] < TRIP_V_LO_dV:
        messages.append(f"Pack under-voltage: {row['pack_inst_voltage'] / 10:.1f} V at {pd.to_datetime(row['timestamp']).strftime('%H:%M:%S')}\n")
    if row["high_cell_voltage"] >= CELL_V_HI_ct:
        messages.append(f"Cell over-voltage: {row['high_cell_voltage'] * 0.0001:.4f} V (cell {row['high_cell_voltage_id']:.0f}) at {pd.to_datetime(row['timestamp']).strftime('%H:%M:%S')}\n")
    if row["low_cell_voltage"] <= CELL_V_LO_ct:
        messages.append(f"Cell under-voltage: {row['low_cell_voltage'] * 0.0001:.4f} V (cell {row['low_cell_voltage_id']:.0f}) at {pd.to_datetime(row['timestamp']).strftime('%H:%M:%S')}\n")
    return " | ".join(messages) if messages else "No fault"

# Streamlit fragments
@st.fragment(run_every=1)
def new_time():
    st.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@st.fragment(run_every=5)
def soc_chart():
    df_soc = soc_update_data()
    if df_soc.empty:
        st.info("Waiting for SOC data...")
        return

    df_soc["soc_series"]   = "State of Charge"
    df_soc["watts_series"] = "Power"

    x_domain = [
        df_soc["timestamp"].iloc[-1] - pd.Timedelta(minutes=1),
        df_soc["timestamp"].iloc[-1],
    ]

    base = alt.Chart(df_soc).mark_line(strokeWidth=2).encode(
        x=alt.X("timestamp:T", title="Time",
                axis=alt.Axis(format="%H:%M:%S"),
                scale=alt.Scale(domain=x_domain)),
        y=alt.Y("pack_soc:Q", title="State of Charge (%)",
                scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("soc_series:N",
                        scale=alt.Scale(domain=["State of Charge", "Power"],
                                        range=["#2563eb", "#d28500"]),
                        legend=alt.Legend(title="Legend:")),
        tooltip=[
            alt.Tooltip("timestamp:T", title="Time", format="%H:%M:%S.%L"),
            alt.Tooltip("pack_soc:Q", title="SoC (%)", format=".1f"),
        ],
    )

    base1 = alt.Chart(df_soc).mark_line(strokeWidth=2).encode(
        x=alt.X("timestamp:T", title="Time",
                axis=alt.Axis(format="%H:%M:%S"),
                scale=alt.Scale(domain=x_domain)),
        y=alt.Y("watts:Q", title="Power (W)",
                scale=alt.Scale(domain=[-4500, 10000])),
        color=alt.Color("watts_series:N",
                        scale=alt.Scale(domain=["State of Charge", "Power"],
                                        range=["#2563eb", "#d28500"]),
                        legend=alt.Legend(title="Legend:")),
        tooltip=[
            alt.Tooltip("timestamp:T", title="Time", format="%H:%M:%S.%L"),
            alt.Tooltip("watts:Q", title="Power (W)", format=".1f"),
        ],
    )

    chart = (
        alt.layer(base, base1)
        .resolve_scale(y="independent")
        .resolve_legend(color="shared")
        .configure_legend(orient="bottom", direction="horizontal", titleOrient="left")
    )
    st.altair_chart(chart.properties(height=400).interactive(), width="stretch")

@st.fragment(run_every=5)
def temp_chart():
    df_temp = temp_update_data()
    if df_temp.empty:
        st.info("Waiting for temperature data...")
        return

    x_domain = [
        df_temp["timestamp"].iloc[-1] - pd.Timedelta(minutes=1),
        df_temp["timestamp"].iloc[-1],
    ]

    base = alt.Chart(df_temp).encode(
        x=alt.X("timestamp:T", title="Time",
                axis=alt.Axis(format="%H:%M:%S"),
                scale=alt.Scale(domain=x_domain)),
        y=alt.Y("temperature:Q", title="Temperature (°C)",
                scale=alt.Scale(domain=[0, 65])),
        color=alt.Color("series:N", title="Legend:", legend=alt.Legend(
            labelExpr="datum.label == 'high_temp' ? 'High' : datum.label == 'low_temp' ? 'Low' : 'Avg'"
        )),
        tooltip=[
            alt.Tooltip("timestamp:T", title="Time", format="%H:%M:%S.%L"),
            alt.Tooltip("series:N", title="Series"),
            alt.Tooltip("temperature:Q", title="Temp (°C)", format=".1f"),
        ],
    )

    chart = base.mark_line(strokeWidth=2).configure_legend(
        orient="bottom", direction="horizontal", titleOrient="left"
    )
    st.altair_chart(chart.properties(height=400).interactive(), width="stretch")

@st.fragment(run_every=1)
def table():
    # Re-query DB so the table always shows the freshest data
    st.session_state.data = load_data()
    df = st.session_state.data.sort_values("timestamp", ascending=False).reset_index(drop=True)
    st.dataframe(df[[
        "timestamp", "pack_current", "pack_inst_voltage", "pack_soc", "relay_state",
        "pack_dcl", "pack_ccl", "BMS_high_temp", "BMS_low_temp",
        "high_cell_voltage", "high_cell_voltage_id", "low_cell_voltage", "low_cell_voltage_id",
        "cell_high_temp", "high_thermistor_id", "cell_low_temp", "low_thermistor_id",
        "avg_temp", "internal_temp",
        "pack_health", "adaptive_total_capacity", "input_supply_voltage",
        "cell_id", "instant_voltage", "internal_resistance", "open_voltage",
    ]])

@st.fragment(run_every=5)
def text_status():
    for msg in fault_detection().apply(describe_faults, axis=1):
        st.write(msg)

@st.fragment(run_every=2)
def text_power():
    st.write("Net Wh: ", compute_battery_energy())

@st.fragment(run_every=1)
def text_con_status():
    last_time = latest_received_at()
    if last_time is None:
        st.write("Connection: None")
        return
    delta = (datetime.now() - last_time).total_seconds()
    if delta > 5:
        st.write("Connection: Disconnected")
    elif delta > 2:
        st.write("Connection: Unstable")
    else:
        st.write("Connection: Good")

# Layout
st.set_page_config(layout="wide")

# Initialise session state from DB on first load
if "data" not in st.session_state:
    st.session_state.data = load_data()

header1, header2, header3, header4, header5, header6, header7 = st.columns(7, vertical_alignment="center")

with header1:
    if st.button("Home"):
        st.switch_page("pages/home_page.py")
with header2:
    st.write(DB_PATH)
with header3:
    text_con_status()
with header4:
    st.write("Mode: Live")
with header5:
    text_power()
with header6:
    new_time()
with header7:
    # Export: flatten the current in-memory DataFrame back to CSV for download
    export_csv = st.session_state.data.to_csv(index=False)
    st.download_button("Export", export_csv, "solar_car_data.csv")

col1, col2 = st.columns([3, 2])
with col1:
    soc_chart()
    temp_chart()
with col2:
    table()
    text_status()