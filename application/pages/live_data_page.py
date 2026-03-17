from datetime import datetime
import streamlit as st
import altair as alt
import numpy as np
import pandas as pd
from numpy.random import default_rng as rng

df = pd.read_csv("data.csv")

def soc_update_data(file) -> pd.DataFrame:
    df_raw = pd.read_csv(file, header=0)

    df = df_raw[["timestamp","pack_soc"]].copy()
    df.columns = ["timestamp", "pack_soc"]

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["pack_soc"] = pd.to_numeric(df["pack_soc"], errors="coerce")
    df = df.dropna()
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df

def temp_update_data(file) -> pd.DataFrame:
    df_raw = pd.read_csv(file, header=0)
    st.write(df_raw.iloc[:5, 19:28])
    df = df_raw[["timestamp", "cell_high_temp", "cell_low_temp", "avg_temp"]].copy()
    df.columns = ["timestamp", "high_temp","low_temp","avg_temp"]

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

@st.fragment(run_every=1)
def new_time():
    st.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@st.fragment(run_every=2)
def soc_chart():
    base = alt.Chart(soc_update_data("data.csv")).encode(
        x=alt.X("timestamp:T", title="Time", axis=alt.Axis(format="%H:%M:%S")),
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

@st.fragment(run_every=2)
def temp_chart():
    df_test = temp_update_data("data.csv")
    st.write(df_test.head())  # Add this
    st.write(df_test.dtypes)  # And this
    base = alt.Chart(temp_update_data("data.csv")).encode(
        x=alt.X("timestamp:T", title="Time", axis=alt.Axis(format="%H:%M:%S")),
        y=alt.Y("temperature:Q", title="Temperature (°C)", scale=alt.Scale(domain=[0, 65])),
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
    df = pd.read_csv("data.csv")
    st.dataframe(df[["pack_current","pack_inst_voltage","pack_soc","relay_state","pack_dcl","pack_ccl","BMS_high_temp","BMS_low_temp","high_cell_voltage","high_cell_voltage_id","low_cell_voltage","low_cell_voltage_id","cell_high_temp","high_thermistor_id","cell_low_temp","low_thermistor_id","avg_temp","internal_temp","pack_health","adaptive_total_capacity","input_supply_voltage","cell_id","instant_voltage","internal_resistance","open_voltage"]])

@st.fragment(run_every=5)
def text_status():
    st.markdown(''':red[Streamlit] :orange[can] :green[write] :blue[text] :violet[in] :gray[pretty] :rainbow[colors] and :blue-background[highlight] text.''')



st.session_state.clear()
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
    st.download_button("Export", df.to_csv(), "solar_car_data.csv")

# Columns
col1, col2 = st.columns([3,2])
with col1:
    soc_chart()
    temp_chart()
with col2:
    table()
    text_status()