from datetime import datetime
import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
from multiprocessing import Process
#import serialRcv

#def start_serial_process():
#    p = Process(target=serialRcv.serialRcv)
#    p.daemon = True
#    p.start()
#    return p

#if "serial_process" not in st.session_state:
#    st.session_state.serial_process = start_serial_process()

#Fault Thresholds
TRIP_I_HI_dA  =  100.0    # +100.0 A  (units: 0.1 A)
TRIP_I_LO_dA  = -42.5     # -42.5 A
TRIP_V_HI_dV  =  95.0     # 95.0 V    (units: 0.1 V)
TRIP_V_LO_dV  =  78.0     # 78.0 V
TRIP_T_HI_C   =  45      # 45 °C
CELL_V_HI_ct  =  4.2000   # 4.2000 V  (units: 0.0001 V)
CELL_V_LO_ct  =  2.5000   # 2.5000 V
num_faults = 0

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

# Pack configuration
CELLS_IN_SERIES = 23

# Precompute pack-level OCV curve
_PACK_OCV_POINTS = _OCV_POINTS * CELLS_IN_SERIES

if "data" not in st.session_state:
    st.session_state.data = pd.read_csv("data.csv")


def pack_voltage_to_soc(pack_voltage: float, clamp: bool = True) -> float:
    v_min = _PACK_OCV_POINTS[0]   # 60.0 V
    v_max = _PACK_OCV_POINTS[-1]  # 100.8 V

    if not clamp and not (v_min <= pack_voltage <= v_max):
        raise ValueError(
            f"pack_voltage {pack_voltage:.2f} V is outside valid range "
            f"[{v_min:.1f} V, {v_max:.1f} V]."
        )

    # np.interp clamps naturally, which matches clamp=True behavior
    soc_fraction = np.interp(pack_voltage, _PACK_OCV_POINTS, _SOC_POINTS)
    return round(float(soc_fraction * 100), 2)


def cell_voltage_to_soc(cell_voltage: float, clamp: bool = True) -> float:
    return pack_voltage_to_soc(cell_voltage * CELLS_IN_SERIES, clamp=clamp)

def soc_update_data() -> pd.DataFrame:
    df_raw = st.session_state.data

    df = df_raw[["timestamp", "pack_soc", "pack_inst_voltage"]].copy()
    for i in df.index:
        df.loc[i, "pack_soc"] = pack_voltage_to_soc(df.loc[i, "pack_inst_voltage"])
    df.columns = ["timestamp", "pack_soc", "pack_inst_voltage"]
    df = df.drop(columns = "pack_inst_voltage")
    df.columns = ["timestamp", "pack_soc"]

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["pack_soc"] = pd.to_numeric(df["pack_soc"], errors="coerce")
    df = df.dropna()
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df

def temp_update_data() -> pd.DataFrame:
    df_raw = st.session_state.data
    df = df_raw[["timestamp", "cell_high_temp", "cell_low_temp", "avg_temp"]].copy()
    df.columns = ["timestamp", "high_temp", "low_temp", "avg_temp"]

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["high_temp"] = pd.to_numeric(df["high_temp"], errors="coerce")
    df["low_temp"] = pd.to_numeric(df["low_temp"], errors="coerce")
    df["avg_temp"] = pd.to_numeric(df["avg_temp"], errors="coerce")
    df = df.dropna()
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df.melt(
        id_vars="timestamp",
        value_vars=["high_temp", "low_temp", "avg_temp"],
        var_name="series",
        value_name="temperature",
    )

def compute_battery_energy():
    df_wh = st.session_state.data


    df_wh['timestamp'] = pd.to_datetime(df_wh['timestamp'])
    df_wh = df_wh.sort_values('timestamp').reset_index(drop=True)
    df_wh['dt'] = df_wh['timestamp'].diff().dt.total_seconds()
    df_wh = df_wh.dropna(subset=['dt'])

    # Compute power (W)
    df_wh['power'] = -df_wh['pack_current'] * df_wh['pack_inst_voltage']

    # Compute incremental energy (Wh)
    df_wh['energy_Wh'] = df_wh['power'] * df_wh['dt'] / 3600.0

    total_energy = df_wh['energy_Wh'].sum()

    return int(total_energy)
    

def fault_detection():
    df = st.session_state.data.sort_values("timestamp", ascending=False).reset_index(drop=True)[:1000]
    fault_mask = (
        (df["BMS_high_temp"]      >= TRIP_T_HI_C)   |
        (df["pack_current"]        > TRIP_I_HI_dA)   |
        (df["pack_current"]        < TRIP_I_LO_dA)   |
        (df["pack_inst_voltage"]   > TRIP_V_HI_dV)   |
        (df["pack_inst_voltage"]   < TRIP_V_LO_dV)   |
        (df["high_cell_voltage"]  >= CELL_V_HI_ct)   |
        (df["low_cell_voltage"]   <= CELL_V_LO_ct)
    )
    
    faults = df[fault_mask].copy()
    num_faults = len(df[fault_mask].copy())
    st.write("Faults (" + str(num_faults) + ")")
    return faults

def describe_faults(row) -> str:
    messages = []
    t = datetime.now() - pd.to_datetime(row["timestamp"])
    
    if row["BMS_high_temp"] >= TRIP_T_HI_C:
        messages.append(f"Over-temp: {row['BMS_high_temp']} °C at {pd.to_datetime(row["timestamp"]).strftime("%H:%M:%S")}\n")
    if row["pack_current"] > TRIP_I_HI_dA:
        messages.append(f"Over-current: {row['pack_current'] / 10:.1f} A at {pd.to_datetime(row["timestamp"]).strftime("%H:%M:%S")}\n")
    if row["pack_current"] < TRIP_I_LO_dA:
        messages.append(f"Charge over-current: {row['pack_current'] / 10:.1f} A at {pd.to_datetime(row["timestamp"]).strftime("%H:%M:%S")}\n")
    if row["pack_inst_voltage"] > TRIP_V_HI_dV:
        messages.append(f"Pack over-voltage: {row['pack_inst_voltage'] / 10:.1f} V at {pd.to_datetime(row["timestamp"]).strftime("%H:%M:%S")}\n")
    if row["pack_inst_voltage"] < TRIP_V_LO_dV:
        messages.append(f"Pack under-voltage: {row['pack_inst_voltage'] / 10:.1f} V at {pd.to_datetime(row["timestamp"]).strftime("%H:%M:%S")}\n")
    if row["high_cell_voltage"] >= CELL_V_HI_ct:
        messages.append(f"Cell over-voltage: {row['high_cell_voltage'] * 0.0001:.4f} V (cell {row['high_cell_voltage_id']:.0f}) at {pd.to_datetime(row["timestamp"]).strftime("%H:%M:%S")}\n")
    if row["low_cell_voltage"] <= CELL_V_LO_ct:
        messages.append(f"Cell under-voltage: {row['low_cell_voltage'] * 0.0001:.4f} V (cell {row['low_cell_voltage_id']:.0f}) at {pd.to_datetime(row["timestamp"]).strftime("%H:%M:%S")}\n")

    return " | ".join(messages) if messages else "No fault"

@st.fragment(run_every=1)
def new_time():
    st.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@st.fragment(run_every=5)
def soc_chart():
    df_soc = soc_update_data()
    if df_soc.empty:
        st.info("Waiting for SOC data...")
        return
    
    base = alt.Chart(df_soc).encode(
        x=alt.X(
            "timestamp:T", 
            title="Time", 
            axis=alt.Axis(format="%H:%M:%S"), 
            scale=alt.Scale(domain=[df_soc["timestamp"].iloc[-1] - pd.Timedelta(minutes=1), df_soc["timestamp"].iloc[-1]])
        ),
        y=alt.Y(
            "pack_soc:Q",
            title="State of Charge (%)",
            scale=alt.Scale(domain=[0, 100]),
        ),
        tooltip=[
            alt.Tooltip("timestamp:T", title="Time", format="%H:%M:%S.%L"),
            alt.Tooltip("pack_soc:Q", title="SoC (%)", format=".1f"),
        ],
    )

    chart = base.mark_line(color="#2563eb", strokeWidth=2)
    st.altair_chart(chart.properties(height=400).interactive(), width='stretch')

@st.fragment(run_every=5)
def temp_chart():
    df_temp = temp_update_data()
    if df_temp.empty:
        st.info("Waiting for temperature data...")
        return
    
    base = alt.Chart(df_temp).encode(
        x=alt.X(
            "timestamp:T", 
            title="Time", 
            axis=alt.Axis(format="%H:%M:%S"),
            scale=alt.Scale(domain=[df_temp["timestamp"].iloc[-1] - pd.Timedelta(minutes=1), df_temp["timestamp"].iloc[-1]])
        ),
        y=alt.Y(
            "temperature:Q", 
            title="Temperature (°C)", 
            scale=alt.Scale(domain=[0, 65])
        ),
        color=alt.Color("series:N", title="Metric", legend=alt.Legend(
            labelExpr="datum.label == 'high_temp' ? 'High' : datum.label == 'low_temp' ? 'Low' : 'Avg'"
        )),
        tooltip=[
            alt.Tooltip("timestamp:T", title="Time", format="%H:%M:%S.%L"),
            alt.Tooltip("series:N", title="Series"),
            alt.Tooltip("temperature:Q", title="Temp (°C)", format=".1f"),
        ],
    )

    chart = base.mark_line(strokeWidth=2)
    st.altair_chart(chart.properties(height=400).interactive(), width='stretch')

@st.fragment(run_every=1)
def table():
    st.session_state.data = pd.read_csv("data.csv")
    df = st.session_state.data.sort_values("timestamp", ascending=False).reset_index(drop=True)
    st.dataframe(df[["timestamp","pack_current","pack_inst_voltage","pack_soc","relay_state","pack_dcl","pack_ccl","BMS_high_temp","BMS_low_temp","high_cell_voltage","high_cell_voltage_id","low_cell_voltage","low_cell_voltage_id","cell_high_temp","high_thermistor_id","cell_low_temp","low_thermistor_id","avg_temp","internal_temp","pack_health","adaptive_total_capacity","input_supply_voltage","cell_id","instant_voltage","internal_resistance","open_voltage"]])

@st.fragment(run_every=5)
def text_status():
    for i in fault_detection().apply(describe_faults, axis=1):
        st.write(i)
    #st.markdown(''':red[Streamlit] :orange[can] :green[write] :blue[text] :violet[in] :gray[pretty] :rainbow[colors] and :blue-background[highlight] text.''')

@st.fragment(run_every=5)
def text_power():
    st.write("Net Wh: ", compute_battery_energy())

st.set_page_config(layout="wide")
header1, header2, header3, header4, header5, header6, header7 = st.columns(7, vertical_alignment="center")
with header1:
    if st.button("Home"):
        st.switch_page("pages/home_page.py")
with header2:
    st.write("data.csv")
with header3:
    st.write("Connection Status")
with header4:
    st.write("Mode: Live")
with header5:
    text_power()
with header6:
    new_time()
with header7:
    st.download_button("Export", pd.read_csv("data.csv").to_csv(), "solar_car_data.csv")

# Columns
col1, col2 = st.columns([3,2])
with col1:
    soc_chart()
    temp_chart()
with col2:
    table()
    text_status()