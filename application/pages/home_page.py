import streamlit as st

st.set_page_config(layout="wide")
st.title("Home")

if st.button("Live Data"):
    st.switch_page("pages/live_data_page.py")
if st.button("Load Data"):
    st.switch_page("pages/static_data_page.py")