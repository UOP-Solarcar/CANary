from streamlit_elements import elements, mui, html
import streamlit as st
import multiprocessing
import numpy as np
import pandas as pd
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

st.set_page_config(layout="wide")
# Columns
col1, col2 = st.columns([3,2])
with col1:
    st.line_chart(df)
    st.line_chart(df)
with col2:
    st.dataframe(df)
    st.markdown(''':red[Streamlit] :orange[can] :green[write] :blue[text] :violet[in] :gray[pretty] :rainbow[colors] and :blue-background[highlight] text.''')

# Tabs
tab1, tab2 = st.tabs(["Chart", "Data"])

# Expander
with st.expander("See details"):
    st.write("Hidden content")

# Container
with st.container():
    st.write("Grouped content")