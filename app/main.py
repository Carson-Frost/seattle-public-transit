"""Seattle Public Transit Analytics - Main application entry point."""

import streamlit as st

from tabs import render_performance, render_schedules, render_actual_trips

# Page configuration
st.set_page_config(
    page_title="Seattle GTFS Analytics",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Reduce top padding
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("Seattle GTFS Data Analysis")

# Create tabs
tab1, tab2, tab3 = st.tabs(["Performance", "Schedules", "Actual Trips"])

with tab1:
    render_performance()

with tab2:
    render_schedules()

with tab3:
    render_actual_trips()
