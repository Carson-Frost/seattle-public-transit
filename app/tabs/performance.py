"""Performance Analysis tab - compare actual vs scheduled performance."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from database import run_query, test_connection
from constants import DELAY_THRESHOLDS
from utils import sort_route_key, calc_delay_pct


def render():
    """Render the Performance tab."""
    st.header("Performance")
    st.write("Compare actual vs scheduled performance · *Actual trip data is sample/mockup data*")

    if not test_connection():
        st.error("Database connection failed. Please check your configuration.")
        st.stop()

    # Filters
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)

    with col1:
        weather_df = run_query("""
            SELECT DISTINCT weather_condition
            FROM actual_trip
            WHERE weather_condition IS NOT NULL
            ORDER BY weather_condition
        """)
        options = ["All"] + (weather_df['weather_condition'].tolist() if not weather_df.empty else [])
        weather = st.selectbox("Weather", options, index=0)

    with col2:
        crowding = st.selectbox("Crowding Level", ["All", "1", "2", "3", "4", "5"], index=0)

    with col3:
        agency_df = run_query("""
            SELECT DISTINCT a.agency_id, a.agency_name
            FROM agency a
            JOIN route r ON a.agency_id = r.agency_id
            JOIN trip t ON r.route_id = t.route_id
            JOIN actual_trip at ON t.trip_id = at.trip_id
            ORDER BY a.agency_name
        """)
        if not agency_df.empty:
            options = agency_df['agency_name'].tolist()
            agencies = st.multiselect("Agencies", options, default=options)
        else:
            agencies = []

    st.divider()

    # Build query
    query = """
        SELECT
            ase.actual_trip_id,
            r.route_short_name,
            r.route_long_name,
            t.trip_headsign,
            at.observation_date,
            at.weather_condition,
            s.stop_name,
            ase.sequence_number,
            st.arrival_time as scheduled_arrival,
            ase.actual_arrival_time,
            st.departure_time as scheduled_departure,
            ase.actual_departure_time,
            ase.event_type,
            ase.crowding_level,
            ase.vehicle_number,
            a.agency_name,
            EXTRACT(EPOCH FROM (ase.actual_arrival_time - st.arrival_time))/60 as arrival_diff_minutes,
            EXTRACT(EPOCH FROM (ase.actual_departure_time - st.departure_time))/60 as departure_diff_minutes
        FROM actual_stop_event ase
        JOIN actual_trip at ON ase.actual_trip_id = at.actual_trip_id
        JOIN trip t ON at.trip_id = t.trip_id
        JOIN route r ON t.route_id = r.route_id
        JOIN agency a ON r.agency_id = a.agency_id
        JOIN stop s ON ase.stop_id = s.stop_id
        LEFT JOIN stop_time st ON at.trip_id = st.trip_id AND ase.stop_id = st.stop_id
        WHERE 1=1
    """

    conditions = []
    params = []

    if weather and weather != "All":
        conditions.append("at.weather_condition = %s")
        params.append(weather)

    if crowding and crowding != "All":
        conditions.append("ase.crowding_level = %s")
        params.append(int(crowding))

    if agencies:
        placeholders = ', '.join(['%s'] * len(agencies))
        conditions.append(f"a.agency_name IN ({placeholders})")
        params.extend(agencies)

    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += " ORDER BY at.observation_date, ase.actual_trip_id, ase.sequence_number"

    df = run_query(query, params=tuple(params) if params else None)

    if df.empty:
        st.info("No performance data available for the selected filters.")
        return

    # Summary metrics
    st.subheader("Summary")
    cols = st.columns(5)

    total = len(df)
    avg_delay = df['arrival_diff_minutes'].mean()
    early = DELAY_THRESHOLDS["early"]
    late = DELAY_THRESHOLDS["late"]

    with cols[0]:
        st.metric("Total Stop Events", f"{total:,}")
    with cols[1]:
        st.metric("Avg Arrival Delay", f"{avg_delay:.1f} min")
    with cols[2]:
        pct = calc_delay_pct(df, 'arrival_diff_minutes', early, late)
        st.metric("On-Time Rate", f"{pct:.1f}%")
    with cols[3]:
        late_count = len(df[df['arrival_diff_minutes'] > late])
        st.metric("Late Events", f"{(late_count / total * 100):.1f}%")
    with cols[4]:
        early_count = len(df[df['arrival_diff_minutes'] < early])
        st.metric("Early Events", f"{(early_count / total * 100):.1f}%")

    st.divider()

    # Main chart
    st.subheader("Actual vs Scheduled Performance")

    routes = sorted(df['route_short_name'].unique(), key=sort_route_key)
    visible = st.multiselect("Routes", options=routes, default=routes, label_visibility="collapsed")

    if not visible:
        st.info("Select at least one route to display.")
    else:
        filtered = df[df['route_short_name'].isin(visible)]
        fig = go.Figure()

        fig.add_hline(y=0, line_dash="dash", line_color="gray",
                      annotation_text="On-Time", annotation_position="right")

        for route in visible:
            data = filtered[filtered['route_short_name'] == route]
            if data.empty:
                continue

            fig.add_trace(go.Scatter(
                x=list(range(len(data))),
                y=data['arrival_diff_minutes'],
                mode='markers+lines',
                name=route,
                marker=dict(size=6),
                line=dict(width=1.5),
                hovertemplate='<b>%{customdata[0]}</b><br>'
                              'Stop: %{customdata[1]}<br>'
                              'Date: %{customdata[2]}<br>'
                              'Delay: %{y:.1f} min<br>'
                              'Weather: %{customdata[3]}<br>'
                              'Crowding: %{customdata[4]}<extra></extra>',
                customdata=data[['route_short_name', 'stop_name', 'observation_date',
                                 'weather_condition', 'crowding_level']].values
            ))

        max_delay = filtered['arrival_diff_minutes'].max()
        min_delay = filtered['arrival_diff_minutes'].min()
        padding = max(1, (max_delay - min_delay) * 0.1)
        y_max = max(max_delay + padding, 3)
        y_min = min(min_delay - padding, -2)

        fig.update_layout(
            xaxis_title="Stop Number",
            yaxis_title="Delay (minutes)",
            hovermode='closest',
            height=500,
            margin=dict(t=20),
            showlegend=True,
            legend=dict(
                title="Route",
                yanchor="top", y=0.99,
                xanchor="right", x=0.99,
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="gray", borderwidth=1
            ),
            yaxis=dict(range=[y_min, y_max]),
            xaxis=dict(showgrid=True, gridwidth=0.5)
        )

        fig.add_hrect(y0=y_min, y1=early, fillcolor="lightgreen", opacity=0.1,
                      annotation_text="Early", annotation_position="left")
        fig.add_hrect(y0=early, y1=late, fillcolor="green", opacity=0.1,
                      annotation_text="On-Time", annotation_position="top left")
        fig.add_hrect(y0=late, y1=y_max, fillcolor="lightcoral", opacity=0.1,
                      annotation_text="Late", annotation_position="left")

        st.plotly_chart(fig, use_container_width=True)

    # Breakdown charts
    breakdown_query = """
        SELECT
            at.weather_condition,
            ase.crowding_level,
            EXTRACT(EPOCH FROM (ase.actual_arrival_time - st.arrival_time))/60 as arrival_diff_minutes
        FROM actual_stop_event ase
        JOIN actual_trip at ON ase.actual_trip_id = at.actual_trip_id
        JOIN trip t ON at.trip_id = t.trip_id
        JOIN route r ON t.route_id = r.route_id
        JOIN agency a ON r.agency_id = a.agency_id
        LEFT JOIN stop_time st ON at.trip_id = st.trip_id AND ase.stop_id = st.stop_id
    """

    if agencies:
        placeholders = ', '.join(['%s'] * len(agencies))
        breakdown_query += f" WHERE a.agency_name IN ({placeholders})"
        breakdown_df = run_query(breakdown_query, params=tuple(agencies))
    else:
        breakdown_df = run_query(breakdown_query)

    col1, col2 = st.columns(2)

    with col1:
        if not breakdown_df.empty and breakdown_df['weather_condition'].notna().any():
            st.subheader("Delay Distribution by Weather")
            weather_delay = breakdown_df[breakdown_df['weather_condition'].notna()].groupby(
                'weather_condition')['arrival_diff_minutes'].mean().sort_values()
            fig = px.bar(
                x=weather_delay.values, y=weather_delay.index,
                orientation='h',
                labels={'x': 'Average Delay (minutes)', 'y': 'Weather'},
                color=weather_delay.values,
                color_continuous_scale=['green', 'yellow', 'red']
            )
            fig.update_layout(showlegend=False, height=400, coloraxis_colorbar_title_text="")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not breakdown_df.empty and breakdown_df['crowding_level'].notna().any():
            st.subheader("Delay Distribution by Crowd Level")
            crowd_delay = breakdown_df[breakdown_df['crowding_level'].notna()].groupby(
                'crowding_level')['arrival_diff_minutes'].mean().sort_values()
            crowd_delay.index = crowd_delay.index.astype(int).astype(str)
            fig = px.bar(
                x=crowd_delay.values, y=crowd_delay.index,
                orientation='h',
                labels={'x': 'Average Delay (minutes)', 'y': 'Crowd Level'},
                color=crowd_delay.values,
                color_continuous_scale=['green', 'yellow', 'red']
            )
            fig.update_layout(showlegend=False, height=400, coloraxis_colorbar_title_text="")
            st.plotly_chart(fig, use_container_width=True)
