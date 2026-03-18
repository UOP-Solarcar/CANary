import streamlit as st

pg = st.navigation([
    st.Page("pages/home_page.py", title="Home Page"),
    st.Page("pages/live_data_page.py", title="Live Data Page"),
    st.Page("pages/static_data_page.py", title="Static Data Page")
])

pg.run()