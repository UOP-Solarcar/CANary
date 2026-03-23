from datetime import datetime
import streamlit as st
import altair as alt
import pandas as pd
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
TRIP_I_HI_dA  =  1000    # +100.0 A  (units: 0.1 A)
TRIP_I_LO_dA  = -425     # -42.5 A
TRIP_V_HI_dV  =  950     # 95.0 V    (units: 0.1 V)
TRIP_V_LO_dV  =  780     # 78.0 V
TRIP_T_HI_C   =  45      # 45 °C
CELL_V_HI_ct  =  42000   # 4.2000 V  (units: 0.0001 V)
CELL_V_LO_ct  =  25000   # 2.5000 V
num_faults = 0

if "data" not in st.session_state:
    st.session_state.data = pd.read_csv("data.csv")

def soc_update_data() -> pd.DataFrame:
    df_raw = st.session_state.data

    df = df_raw[["timestamp", "pack_soc"]].copy()
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



st.set_page_config(layout="wide")
header1, header2, header3, header4, header5, header6, header7 = st.columns(7, vertical_alignment="center")
with header1:
    if st.button("Home"):
        st.switch_page("pages/home_page.py")
with header2:
    st.write("Session Name")
with header3:
    st.write("Connection Status")
with header4:
    st.write("Mode: Live")
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