import streamlit as st
from database import test_connection, run_query

# Page configuration
st.set_page_config(
    page_title="Seattle Public Transit Analysis",
    layout="wide"
)

# Title
st.title("Seattle Public Transit Analysis")
st.markdown("---")

# Test database connection
st.subheader("Database Connection Status")
if test_connection():
    st.success("Successfully connected to PostgreSQL database!")

    # Display basic database statistics
    st.subheader("Database Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        result = run_query("SELECT COUNT(*) as count FROM agencies")
        count = result['count'].iloc[0] if not result.empty else 0
        st.metric("Agencies", count)

    with col2:
        result = run_query("SELECT COUNT(*) as count FROM routes")
        count = result['count'].iloc[0] if not result.empty else 0
        st.metric("Routes", count)

    with col3:
        result = run_query("SELECT COUNT(*) as count FROM stops")
        count = result['count'].iloc[0] if not result.empty else 0
        st.metric("Stops", count)

    with col4:
        result = run_query("SELECT COUNT(*) as count FROM trips")
        count = result['count'].iloc[0] if not result.empty else 0
        st.metric("Trips", count)

    # Show sample data
    st.subheader("Sample Routes")
    routes_df = run_query("SELECT route_id, route_short_name, route_long_name, route_type FROM routes LIMIT 10")
    st.dataframe(routes_df, use_container_width=True)

else:
    st.error("Failed to connect to database. Please check your connection settings in .env file")

# Sidebar
st.sidebar.title("Navigation")
st.sidebar.info("Use the pages above to navigate to different features.")
