"""Seattle Public Transit Analytics - Main application entry point."""

import streamlit as st

from tabs import render_performance, render_schedules, render_actual_trips

# Page configuration
st.set_page_config(
    page_title="Seattle GTFS Analytics",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom styling
st.markdown("""
    <style>
        /* Add space for navbar */
        .block-container { padding-top: 3.5rem; }

        /* Put title in the navbar */
        [data-testid="stHeader"] {
            display: flex;
            align-items: center;
            padding-left: 5rem;
        }
        [data-testid="stHeader"]::before {
            content: "Seattle GTFS Data Analysis";
            font-size: 2rem;
            font-weight: 700;
            white-space: nowrap;
        }
    </style>
    """, unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3 = st.tabs(["Performance", "Schedules", "Actual Trips"])

with tab1:
    render_performance()

with tab2:
    render_schedules()

with tab3:
    render_actual_trips()
