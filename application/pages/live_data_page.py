from datetime import datetime
import streamlit as st
import numpy as np
import pandas as pd
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])


@st.fragment(run_every=1)
def new_time():
    st.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@st.fragment(run_every=2)
def soc_chart():
    st.line_chart(df)

@st.fragment(run_every=2)
def speed_chart():
    st.line_chart(df)

@st.fragment(run_every=2)
def table():
    st.dataframe(df)

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
    speed_chart()
with col2:
    table()
    text_status()