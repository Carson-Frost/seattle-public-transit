"""
Seattle Public Transit Analytics
Main application with three tabs: Performance Analysis, Schedules, Record Trip
"""

import streamlit as st

st.set_page_config(
    page_title="Seattle GTFS Analytics",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)

st.title("Seattle GTFS Data Analysis")

tab1, tab2, tab3 = st.tabs(["Performance Analysis", "Schedules", "Actual Trips"])

# Tab 1: Performance Analysis
with tab1:
    st.header("Performance Analysis")
    st.write("Compare actual vs scheduled performance")

    from database import run_query, test_connection
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    if not test_connection():
        st.error("Database connection failed. Please check your configuration.")
        st.stop()

    # Filters section
    st.subheader("Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Weather filter
        weather_df = run_query("""
            SELECT DISTINCT weather_condition
            FROM actual_trip
            WHERE weather_condition IS NOT NULL
            ORDER BY weather_condition
        """)

        weather_options = ["All"] + weather_df['weather_condition'].tolist() if not weather_df.empty else ["All"]
        selected_weather = st.selectbox("Weather", weather_options, index=0)

    with col2:
        # Crowding level filter
        crowding_options = ["All", "1", "2", "3", "4", "5"]
        selected_crowding = st.selectbox("Crowding Level", crowding_options, index=0)

    with col3:
        # Agency filter
        agency_df = run_query("""
            SELECT DISTINCT a.agency_id, a.agency_name
            FROM agency a
            JOIN route r ON a.agency_id = r.agency_id
            JOIN trip t ON r.route_id = t.route_id
            JOIN actual_trip at ON t.trip_id = at.trip_id
            ORDER BY a.agency_name
        """)

        if not agency_df.empty:
            agency_options = [row['agency_name'] for _, row in agency_df.iterrows()]
            selected_agencies = st.multiselect("Agencies", agency_options, default=agency_options)

    st.divider()

    # Build query with filters
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

    # Weather filter
    if selected_weather and selected_weather != "All":
        conditions.append(f"at.weather_condition = %s")
        params.append(selected_weather)

    # Crowding filter
    if selected_crowding and selected_crowding != "All":
        conditions.append(f"ase.crowding_level = %s")
        params.append(int(selected_crowding))

    # Agency filter
    if selected_agencies:
        placeholders = ', '.join(['%s'] * len(selected_agencies))
        conditions.append(f"a.agency_name IN ({placeholders})")
        params.extend(selected_agencies)

    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += " ORDER BY at.observation_date, ase.actual_trip_id, ase.sequence_number"

    performance_df = run_query(query, params=tuple(params) if params else None)

    if not performance_df.empty:
        # Summary statistics
        st.subheader("Summary")

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            total_events = len(performance_df)
            st.metric("Total Stop Events", f"{total_events:,}")

        with col2:
            avg_delay = performance_df['arrival_diff_minutes'].mean()
            st.metric("Avg Arrival Delay", f"{avg_delay:.1f} min")

        with col3:
            on_time_count = len(performance_df[performance_df['arrival_diff_minutes'].between(-1, 1)])
            on_time_pct = (on_time_count / total_events * 100) if total_events > 0 else 0
            st.metric("On-Time Rate", f"{on_time_pct:.1f}%")

        with col4:
            late_count = len(performance_df[performance_df['arrival_diff_minutes'] > 1])
            late_pct = (late_count / total_events * 100) if total_events > 0 else 0
            st.metric("Late Events", f"{late_pct:.1f}%")

        with col5:
            early_count = len(performance_df[performance_df['arrival_diff_minutes'] < -1])
            early_pct = (early_count / total_events * 100) if total_events > 0 else 0
            st.metric("Early Events", f"{early_pct:.1f}%")

        st.divider()

        # Main visualization
        st.subheader("Actual vs Scheduled Performance")

        # Create scatter plot with time differences
        fig = go.Figure()

        # Add a horizontal line at y=0 (on-time)
        fig.add_hline(y=0, line_dash="dash", line_color="gray",
                     annotation_text="On-Time", annotation_position="right")

        # Add scatter plot for each route
        for route in performance_df['route_short_name'].unique():
            route_data = performance_df[performance_df['route_short_name'] == route]

            fig.add_trace(go.Scatter(
                x=list(range(len(route_data))),
                y=route_data['arrival_diff_minutes'],
                mode='markers+lines',
                name=route,
                marker=dict(size=6),
                line=dict(width=1.5),
                hovertemplate='<b>%{customdata[0]}</b><br>' +
                             'Stop: %{customdata[1]}<br>' +
                             'Date: %{customdata[2]}<br>' +
                             'Delay: %{y:.1f} min<br>' +
                             'Weather: %{customdata[3]}<br>' +
                             'Crowding: %{customdata[4]}<extra></extra>',
                customdata=route_data[['route_short_name', 'stop_name', 'observation_date',
                                      'weather_condition', 'crowding_level']].values
            ))

        # Determine y-axis range based on data
        max_delay = performance_df['arrival_diff_minutes'].max()
        min_delay = performance_df['arrival_diff_minutes'].min()
        y_range = max(abs(max_delay), abs(min_delay))
        y_limit = min(15, max(10, y_range + 2))  # At least 10, at most 15, or data range + 2

        fig.update_layout(
            xaxis_title="Stop Sequence Index",
            yaxis_title="Delay (minutes)",
            hovermode='closest',
            height=500,
            showlegend=True,
            legend=dict(
                yanchor="bottom",
                y=0.01,
                xanchor="left",
                x=0.05,
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="gray",
                borderwidth=1
            ),
            yaxis=dict(
                range=[-y_limit, y_limit],
                dtick=1  # Show every minute
            ),
            xaxis=dict(
                showgrid=True,
                gridwidth=0.5
            )
        )

        # Add shaded regions for early/on-time/late
        fig.add_hrect(y0=-y_limit, y1=-1, fillcolor="lightgreen", opacity=0.1,
                     annotation_text="Early", annotation_position="left")
        fig.add_hrect(y0=-1, y1=1, fillcolor="green", opacity=0.1,
                     annotation_text="On-Time", annotation_position="left")
        fig.add_hrect(y0=1, y1=y_limit, fillcolor="lightcoral", opacity=0.1,
                     annotation_text="Late", annotation_position="left")

        st.plotly_chart(fig, use_container_width=True)

        # Additional breakdown visualizations (filtered by agency only)
        # Query data with agency filter only
        all_data_query = """
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

        agency_conditions = []
        agency_params = []

        # Apply agency filter if present
        if selected_agencies:
            placeholders = ', '.join(['%s'] * len(selected_agencies))
            agency_conditions.append(f"a.agency_name IN ({placeholders})")
            agency_params.extend(selected_agencies)

        if agency_conditions:
            all_data_query += " WHERE " + " AND ".join(agency_conditions)

        all_data_df = run_query(all_data_query, params=tuple(agency_params) if agency_params else None)

        col1, col2 = st.columns(2)

        with col1:
            # Delay distribution by weather (unfiltered)
            if not all_data_df.empty and 'weather_condition' in all_data_df.columns and all_data_df['weather_condition'].notna().any():
                st.subheader("Delay Distribution by Weather")
                weather_delay = all_data_df[all_data_df['weather_condition'].notna()].groupby('weather_condition')['arrival_diff_minutes'].mean().sort_values()
                fig_weather = px.bar(
                    x=weather_delay.values,
                    y=weather_delay.index,
                    orientation='h',
                    labels={'x': 'Average Delay (minutes)', 'y': 'Weather'},
                    color=weather_delay.values,
                    color_continuous_scale=['green', 'yellow', 'red']
                )
                fig_weather.update_layout(showlegend=False, height=400, coloraxis_colorbar_title_text="")
                st.plotly_chart(fig_weather, use_container_width=True)

        with col2:
            # Delay distribution by crowding level (unfiltered)
            if not all_data_df.empty and 'crowding_level' in all_data_df.columns and all_data_df['crowding_level'].notna().any():
                st.subheader("Delay Distribution by Crowd Level")
                crowding_delay = all_data_df[all_data_df['crowding_level'].notna()].groupby('crowding_level')['arrival_diff_minutes'].mean().sort_values()
                # Convert crowding levels to strings for better display
                crowding_delay.index = crowding_delay.index.astype(int).astype(str)
                fig_crowding = px.bar(
                    x=crowding_delay.values,
                    y=crowding_delay.index,
                    orientation='h',
                    labels={'x': 'Average Delay (minutes)', 'y': 'Crowd Level'},
                    color=crowding_delay.values,
                    color_continuous_scale=['green', 'yellow', 'red']
                )
                fig_crowding.update_layout(showlegend=False, height=400, coloraxis_colorbar_title_text="")
                st.plotly_chart(fig_crowding, use_container_width=True)

    else:
        st.info("No performance data available for the selected filters. Try adjusting your filter selections.")

from datetime import time

def normalize_time(t):
    if t is None:
        return None

    # If it's already a datetime.time object, convert to HH:MM:SS
    if isinstance(t, time):
        return t.strftime("%H:%M:%S")

    # Otherwise assume it's a string
    t = str(t).strip()

    # Convert HH:MM → HH:MM:SS
    if len(t) == 5:
        return f"{t}:00"

    return t


# Tab 2: Schedules
with tab2:
    st.header("Schedules")

    from database import run_query, test_connection
    import pandas as pd

    if not test_connection():
        st.error("Database connection failed. Please check your configuration.")
        st.stop()

    from datetime import date

    # Initialize session state for add/edit trip form
    if 'show_trip_form' not in st.session_state:
        st.session_state.show_trip_form = False
    if 'editing_scheduled_trip_id' not in st.session_state:
        st.session_state.editing_scheduled_trip_id = None

    # Show Add/Edit Trip form if button was clicked
    if st.session_state.show_trip_form:
        editing_mode = st.session_state.editing_scheduled_trip_id is not None

        # Load existing trip data if editing
        if editing_mode:
            existing_scheduled_trip = run_query("""
                SELECT t.trip_id, t.route_id, t.service_id, t.trip_headsign,
                       t.direction_id, t.wheelchair_accessible
                FROM trip t
                WHERE t.trip_id = %s
            """, params=(st.session_state.editing_scheduled_trip_id,))

            existing_stop_times = run_query("""
                SELECT st.stop_id, st.stop_sequence, st.arrival_time, st.departure_time,
                       s.stop_name
                FROM stop_time st
                JOIN stop s ON st.stop_id = s.stop_id
                WHERE st.trip_id = %s
                ORDER BY st.stop_sequence
            """, params=(st.session_state.editing_scheduled_trip_id,))

        # Header with back and delete buttons
        if editing_mode:
            col1, col2 = st.columns([3, 1])
            with col1:
                if st.button("Back to Schedules", type="secondary"):
                    st.session_state.show_trip_form = False
                    st.session_state.editing_scheduled_trip_id = None
                    if 'scheduled_stop_times' in st.session_state:
                        st.session_state.scheduled_stop_times = []
                    st.rerun()
            with col2:
                delete_label = f"Delete Trip"
                if st.button(delete_label, type="secondary", use_container_width=True):
                    # Delete stop times first
                    run_query("DELETE FROM stop_time WHERE trip_id = %s",
                             params=(st.session_state.editing_scheduled_trip_id,))
                    # Delete trip
                    run_query("DELETE FROM trip WHERE trip_id = %s",
                             params=(st.session_state.editing_scheduled_trip_id,))
                    st.success(f"Trip {st.session_state.editing_scheduled_trip_id} deleted!")
                    st.session_state.show_trip_form = False
                    st.session_state.editing_scheduled_trip_id = None
                    if 'scheduled_stop_times' in st.session_state:
                        st.session_state.scheduled_stop_times = []
                    st.rerun()
        else:
            if st.button("Back to Schedules", type="secondary"):
                st.session_state.show_trip_form = False
                if 'scheduled_stop_times' in st.session_state:
                    st.session_state.scheduled_stop_times = []
                st.rerun()

        st.divider()
        st.subheader("Add Scheduled Trip" if not editing_mode else "Edit Scheduled Trip")

        # Pre-fill form if editing
        if editing_mode and not existing_scheduled_trip.empty:
            existing_route_id = int(existing_scheduled_trip.iloc[0]['route_id'])
            existing_service_id = int(existing_scheduled_trip.iloc[0]['service_id'])
            existing_headsign = existing_scheduled_trip.iloc[0]['trip_headsign']
            existing_direction = int(existing_scheduled_trip.iloc[0]['direction_id']) if pd.notna(existing_scheduled_trip.iloc[0]['direction_id']) else 0
            existing_wheelchair = int(existing_scheduled_trip.iloc[0]['wheelchair_accessible']) if pd.notna(existing_scheduled_trip.iloc[0]['wheelchair_accessible']) else 0

            # Load existing stop times
            if 'scheduled_stop_times' not in st.session_state or not st.session_state.scheduled_stop_times:
                st.session_state.scheduled_stop_times = []
                for _, stop_time in existing_stop_times.iterrows():
                    st.session_state.scheduled_stop_times.append({
                        'stop_id': int(stop_time['stop_id']),
                        'stop_name': stop_time['stop_name'],
                        'arrival_time': str(stop_time['arrival_time']),
                        'departure_time': str(stop_time['departure_time'])
                    })

        # Trip details form
        col1, col2, col3 = st.columns(3)

        with col1:
            routes_df = run_query("""
                SELECT DISTINCT r.route_id, r.route_short_name, r.route_long_name
                FROM route r
                ORDER BY r.route_short_name
            """)

            if not routes_df.empty:
                route_options = [
                    f"{row['route_short_name']}: {row['route_long_name']}" if row['route_long_name']
                    else row['route_short_name']
                    for _, row in routes_df.iterrows()
                ]

                default_route_idx = 0
                if editing_mode and not existing_scheduled_trip.empty:
                    for i, row in routes_df.iterrows():
                        if int(row['route_id']) == existing_route_id:
                            default_route_idx = i
                            break

                trip_route_idx = st.selectbox("Route", range(len(route_options)),
                                             format_func=lambda x: route_options[x],
                                             index=default_route_idx,
                                             key="trip_route")
                trip_route_id = int(routes_df.iloc[trip_route_idx]['route_id'])

        with col2:
            services_df = run_query("""
                SELECT service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday
                FROM service_calendar
                ORDER BY service_id
            """)

            if not services_df.empty:
                service_options = []
                for _, row in services_df.iterrows():
                    days = []
                    if row['monday']: days.append('Mon')
                    if row['tuesday']: days.append('Tue')
                    if row['wednesday']: days.append('Wed')
                    if row['thursday']: days.append('Thu')
                    if row['friday']: days.append('Fri')
                    if row['saturday']: days.append('Sat')
                    if row['sunday']: days.append('Sun')
                    if days:
                        service_options.append(f"Service {row['service_id']}: {', '.join(days)}")
                    else:
                        service_options.append(f"Service {row['service_id']}")

                default_service_idx = 0
                if editing_mode and not existing_scheduled_trip.empty:
                    for i, row in services_df.iterrows():
                        if int(row['service_id']) == existing_service_id:
                            default_service_idx = i
                            break

                trip_service_idx = st.selectbox("Service Calendar", range(len(service_options)),
                                               format_func=lambda x: service_options[x],
                                               index=default_service_idx,
                                               key="trip_service")
                trip_service_id = int(services_df.iloc[trip_service_idx]['service_id'])

        with col3:
            default_direction_idx = existing_direction if editing_mode and not existing_scheduled_trip.empty else 0
            trip_direction = st.selectbox("Direction", ["Outbound", "Inbound"],
                                         index=default_direction_idx,
                                         key="trip_direction")
            trip_direction_id = 0 if trip_direction == "Outbound" else 1

        col1, col2, col3 = st.columns(3)

        with col1:
            default_headsign = existing_headsign if editing_mode and not existing_scheduled_trip.empty else ""
            trip_headsign = st.text_input("Trip Headsign", value=default_headsign, key="trip_headsign")

        with col2:
            wheelchair_options = ["Unknown", "Accessible", "Not Accessible"]
            default_wheelchair_idx = existing_wheelchair if editing_mode and not existing_scheduled_trip.empty else 0
            trip_wheelchair_display = st.selectbox("Wheelchair Accessible", wheelchair_options,
                                                  index=default_wheelchair_idx,
                                                  key="trip_wheelchair")
            trip_wheelchair = wheelchair_options.index(trip_wheelchair_display)

        with col3:
            st.write("")  # Spacing

        st.divider()
        st.subheader("Stop Times")

        # Get stops used by this route
        route_stops_df = run_query("""
            SELECT DISTINCT s.stop_id, s.stop_name
            FROM stop s
            JOIN stop_time st ON s.stop_id = st.stop_id
            JOIN trip t ON st.trip_id = t.trip_id
            WHERE t.route_id = %s
            ORDER BY s.stop_name
        """, params=(trip_route_id,))

        # Get all other stops
        if not route_stops_df.empty:
            route_stop_ids = tuple(route_stops_df['stop_id'].tolist())
            if len(route_stop_ids) == 1:
                other_stops_df = run_query("""
                    SELECT stop_id, stop_name
                    FROM stop
                    WHERE stop_id != %s
                    ORDER BY stop_name
                """, params=(route_stop_ids[0],))
            else:
                other_stops_df = run_query("""
                    SELECT stop_id, stop_name
                    FROM stop
                    WHERE stop_id NOT IN %s
                    ORDER BY stop_name
                """, params=(route_stop_ids,))
        else:
            other_stops_df = run_query("""
                SELECT stop_id, stop_name
                FROM stop
                ORDER BY stop_name
            """)

        if 'scheduled_stop_times' not in st.session_state:
            st.session_state.scheduled_stop_times = []

        # Add stop time form
        with st.form("add_stop_time"):
            st.write("Add a stop:")

            col1, col2, col3 = st.columns(3)

            with col1:
                # Build stop options with route stops first
                stop_options = [""]
                stop_data = []  # To track actual stop data

                # Add route stops first
                for _, row in route_stops_df.iterrows():
                    stop_options.append(f"{row['stop_name']} (used in route)")
                    stop_data.append({'stop_id': row['stop_id'], 'stop_name': row['stop_name']})

                # Add other stops
                for _, row in other_stops_df.iterrows():
                    stop_options.append(row['stop_name'])
                    stop_data.append({'stop_id': row['stop_id'], 'stop_name': row['stop_name']})

                stop_selection = st.selectbox("Stop", range(len(stop_options)),
                                             format_func=lambda x: stop_options[x] if stop_options[x] else "Select a stop...",
                                             index=0,
                                             key="scheduled_stop")
                selected_stop_idx = stop_selection - 1 if stop_selection > 0 else None

            with col2:
                arrival_time_input = st.text_input("Arrival time (HH:MM)", placeholder="08:00", key="scheduled_arrival")

            with col3:
                departure_time_input = st.text_input("Departure time (HH:MM)", placeholder="08:01", key="scheduled_departure")

            if st.form_submit_button("Add Stop"):
                import re
                time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

                if selected_stop_idx is None:
                    st.error("Please select a stop")
                elif not arrival_time_input or not time_pattern.match(arrival_time_input):
                    st.error("Please enter arrival time in HH:MM format")
                elif not departure_time_input or not time_pattern.match(departure_time_input):
                    st.error("Please enter departure time in HH:MM format")
                else:
                    selected_stop = stop_data[selected_stop_idx]
                    st.session_state.scheduled_stop_times.append({
                        'stop_id': int(selected_stop['stop_id']),
                        'stop_name': selected_stop['stop_name'],
                        'arrival_time': normalize_time(arrival_time_input),
                        'departure_time': normalize_time(departure_time_input)

                    })
                    st.success(f"Added stop: {selected_stop['stop_name']}")
                    st.rerun()

        # Display added stops
        if st.session_state.scheduled_stop_times:
            st.write(f"Stops added ({len(st.session_state.scheduled_stop_times)}):")

            for idx, stop_time in enumerate(st.session_state.scheduled_stop_times):
                with st.container():
                    col_header1, col_header2 = st.columns([5, 1])
                    with col_header1:
                        st.markdown(f"**Stop {idx + 1}: {stop_time['stop_name']}**")
                    with col_header2:
                        if st.button("Delete", key=f"delete_stop_{idx}", type="secondary", use_container_width=True):
                            st.session_state.scheduled_stop_times.pop(idx)
                            st.rerun()

                    col1, col2 = st.columns(2)
                    with col1:
                        new_arrival = st.text_input("Arrival time (HH:MM)",
                                                   value=stop_time['arrival_time'][:5],
                                                   key=f"stop_arrival_{idx}")
                        stop_time['arrival_time'] = normalize_time(new_arrival)
                    with col2:
                        new_departure = st.text_input("Departure time (HH:MM)",
                                                     value=stop_time['departure_time'][:5],
                                                     key=f"stop_departure_{idx}")
                        stop_time['departure_time'] = normalize_time(new_departure)

                    st.divider()

            # Save button
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write("")
            with col2:
                save_label = "Update Trip" if editing_mode else "Save Trip"
                if st.button(save_label, type="secondary", use_container_width=True):
                    if editing_mode:
                        # Update existing trip
                        run_query("""
                            UPDATE trip
                            SET route_id = %s, service_id = %s, trip_headsign = %s,
                                direction_id = %s, wheelchair_accessible = %s
                            WHERE trip_id = %s
                        """, params=(trip_route_id, trip_service_id, trip_headsign,
                                    trip_direction_id, trip_wheelchair,
                                    st.session_state.editing_scheduled_trip_id))

                        # Delete existing stop times
                        run_query("DELETE FROM stop_time WHERE trip_id = %s",
                                 params=(st.session_state.editing_scheduled_trip_id,))

                        # Insert updated stop times
                        for idx, stop_time in enumerate(st.session_state.scheduled_stop_times, start=1):
                            run_query("""
                                INSERT INTO stop_time (trip_id, stop_id, stop_sequence, arrival_time, departure_time)
                                VALUES (%s, %s, %s, %s, %s)
                            """, params=(st.session_state.editing_scheduled_trip_id, stop_time['stop_id'],
                                        idx, stop_time['arrival_time'], stop_time['departure_time']))

                        st.success(f"Trip {st.session_state.editing_scheduled_trip_id} updated!")
                        st.session_state.show_trip_form = False
                        st.session_state.editing_scheduled_trip_id = None
                        st.session_state.scheduled_stop_times = []
                        st.rerun()
                    else:
                        # Get next trip_id
                        max_trip = run_query("SELECT MAX(trip_id) as max_id FROM trip")
                        new_trip_id = int(max_trip.iloc[0]['max_id']) + 1 if not max_trip.empty and pd.notna(max_trip.iloc[0]['max_id']) else 1

                        # Insert new trip
                        run_query("""
                            INSERT INTO trip (trip_id, route_id, service_id, trip_headsign, direction_id, wheelchair_accessible)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, params=(new_trip_id, trip_route_id, trip_service_id, trip_headsign,
                                    trip_direction_id, trip_wheelchair))

                        # Insert stop times
                        for idx, stop_time in enumerate(st.session_state.scheduled_stop_times, start=1):
                            run_query("""
                                INSERT INTO stop_time (trip_id, stop_id, stop_sequence, arrival_time, departure_time)
                                VALUES (%s, %s, %s, %s, %s)
                            """, params=(new_trip_id, stop_time['stop_id'], idx,
                                        stop_time['arrival_time'], stop_time['departure_time']))

                        st.success(f"Trip {new_trip_id} created successfully!")
                        st.session_state.show_trip_form = False
                        st.session_state.scheduled_stop_times = []
                        st.rerun()
        else:
            st.info("No stops added yet. Add stops above to create the trip.")

    else:
        # Show normal schedules view
        st.write("Browse scheduled trips and stop times")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            routes_df = run_query("""
                SELECT DISTINCT r.route_id, r.route_short_name, r.route_long_name, r.route_type
                FROM route r
            """)

            if not routes_df.empty:
                # sort numerically instead of alphabetically
                def sort_key(route_name):
                    try:
                        return (0, int(route_name))
                    except ValueError:
                        return (1, route_name)

                routes_df['sort_key'] = routes_df['route_short_name'].apply(sort_key)
                routes_df = routes_df.sort_values('sort_key').drop('sort_key', axis=1).reset_index(drop=True)
                route_options = []
                for _, row in routes_df.iterrows():
                    long_name = row['route_long_name'] if row['route_long_name'] else ""
                    if long_name:
                        route_options.append(f"{row['route_short_name']}: {long_name}")
                    else:
                        route_options.append(f"{row['route_short_name']}")

                selected_route_idx = st.selectbox(
                    "Route",
                    range(len(route_options)),
                    format_func=lambda x: route_options[x]
                )
                selected_route_id = int(routes_df.iloc[selected_route_idx]['route_id'])
                selected_route_type = int(routes_df.iloc[selected_route_idx]['route_type'])
                selected_route_short_name = routes_df.iloc[selected_route_idx]['route_short_name']
                selected_route_long_name = routes_df.iloc[selected_route_idx]['route_long_name'] or ""
            else:
                st.warning("No routes found in database")
                st.stop()

        with col2:
            direction = st.selectbox("Direction", ["Outbound & Inbound", "Outbound", "Inbound"])
            direction_filter = None if direction == "Outbound & Inbound" else int(0 if direction == "Outbound" else 1)

        with col3:
            selected_date = st.date_input(
                "Date",
                value=date(2025, 12, 12),
                key="schedules_date"
            )

        with col4:
            time_options = [
                ("07:00 AM", "07:00"), ("07:15 AM", "07:15"), ("07:30 AM", "07:30"), ("07:45 AM", "07:45"),
                ("08:00 AM", "08:00"), ("08:15 AM", "08:15"), ("08:30 AM", "08:30"), ("08:45 AM", "08:45"),
                ("09:00 AM", "09:00")
            ]
            time_col1, time_col2 = st.columns(2)
            with time_col1:
                start_time_str = st.selectbox("Start", range(len(time_options)), index=0,
                                              format_func=lambda x: time_options[x][0])
            with time_col2:
                end_time_str = st.selectbox("End", range(len(time_options)), index=8,
                                            format_func=lambda x: time_options[x][0])

            start_time = f"{time_options[start_time_str][1]}:00"
            end_time = f"{time_options[end_time_str][1]}:00"

        # Determine day of week for selected date (0=Monday, 6=Sunday)
        selected_dow = selected_date.weekday()
        dow_columns = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        dow_column = dow_columns[selected_dow]

        if direction_filter is not None:
            trips_query = f"""
                SELECT DISTINCT t.trip_id, t.trip_headsign, t.direction_id,
                       MIN(st.departure_time) as start_time
                FROM trip t
                JOIN stop_time st ON t.trip_id = st.trip_id
                JOIN service_calendar sc ON t.service_id = sc.service_id
                LEFT JOIN calendar_exception ce ON t.service_id = ce.service_id
                    AND ce.date = %s
                WHERE t.route_id = %s
                  AND t.direction_id = %s
                  AND st.stop_sequence = 1
                  AND %s BETWEEN sc.start_date AND sc.end_date
                  AND (
                    (sc.{dow_column} AND (ce.exception_type IS NULL OR ce.exception_type != 2))
                    OR ce.exception_type = 1
                  )
                GROUP BY t.trip_id, t.trip_headsign, t.direction_id
                HAVING MIN(st.departure_time) >= %s AND MIN(st.departure_time) < %s
                ORDER BY start_time
            """
            trips_df = run_query(trips_query, params=(selected_date, selected_route_id, direction_filter, selected_date, start_time, end_time))
        else:
            trips_query = f"""
                SELECT DISTINCT t.trip_id, t.trip_headsign, t.direction_id,
                       MIN(st.departure_time) as start_time
                FROM trip t
                JOIN stop_time st ON t.trip_id = st.trip_id
                JOIN service_calendar sc ON t.service_id = sc.service_id
                LEFT JOIN calendar_exception ce ON t.service_id = ce.service_id
                    AND ce.date = %s
                WHERE t.route_id = %s
                  AND st.stop_sequence = 1
                  AND %s BETWEEN sc.start_date AND sc.end_date
                  AND (
                    (sc.{dow_column} AND (ce.exception_type IS NULL OR ce.exception_type != 2))
                    OR ce.exception_type = 1
                  )
                GROUP BY t.trip_id, t.trip_headsign, t.direction_id
                HAVING MIN(st.departure_time) >= %s AND MIN(st.departure_time) < %s
                ORDER BY start_time
            """
            trips_df = run_query(trips_query, params=(selected_date, selected_route_id, selected_date, start_time, end_time))

        if trips_df.empty:
            st.warning("No trips found for this route")
            st.stop()

        # GTFS route types
        route_type_map = {
            0: "Streetcar", 1: "Subway", 2: "Rail", 3: "Bus", 4: "Ferry",
            5: "Cable Tram", 6: "Aerial Lift", 7: "Funicular", 11: "Trolleybus", 12: "Monorail"
        }
        route_type_name = route_type_map.get(selected_route_type, "Transit")

        direction_text = "Outbound & Inbound" if direction_filter is None else ("Outbound" if direction_filter == 0 else "Inbound")
        start_time_12hr = time_options[start_time_str][0]
        end_time_12hr = time_options[end_time_str][0]
        date_text = selected_date.strftime("%B %d (%Y)")

        st.info(f"**Route {selected_route_short_name}: {selected_route_long_name} ({route_type_name})**, {direction_text}, {date_text}, {start_time_12hr} - {end_time_12hr}")

        st.subheader(f"Trips ({len(trips_df)} found)")

        trips_df['display'] = trips_df.apply(
            lambda row: f"{row['start_time']} - {row['trip_headsign']} ({'Outbound' if row['direction_id'] == 0 else 'Inbound'})",
            axis=1
        )

        # Trip dropdown with Add/Edit buttons in line
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            selected_trip_idx = st.selectbox(
                "Select a trip to view stop times",
                range(len(trips_df)),
                format_func=lambda x: trips_df.iloc[x]['display']
            )
            selected_trip_id = int(trips_df.iloc[selected_trip_idx]['trip_id'])
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Edit Trip", type="secondary", use_container_width=True):
                st.session_state.show_trip_form = True
                st.session_state.editing_scheduled_trip_id = selected_trip_id
                st.rerun()
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Add New Trip", type="secondary", use_container_width=True):
                st.session_state.show_trip_form = True
                st.session_state.editing_scheduled_trip_id = None
                if 'scheduled_stop_times' in st.session_state:
                    st.session_state.scheduled_stop_times = []
                st.rerun()

        st.subheader("Stop Times")

        stop_times_query = """
            SELECT st.stop_sequence, s.stop_name, st.arrival_time, st.departure_time,
                   s.stop_lat, s.stop_lon
            FROM stop_time st
            JOIN stop s ON st.stop_id = s.stop_id
            WHERE st.trip_id = %s
            ORDER BY st.stop_sequence
        """
        stop_times_df = run_query(stop_times_query, params=(selected_trip_id,))

        if not stop_times_df.empty:
            display_df = stop_times_df[['stop_sequence', 'stop_name', 'arrival_time']].rename(
                columns={
                    'stop_sequence': 'Stop Sequence',
                    'stop_name': 'Stop Name',
                    'arrival_time': 'Time'
                }
            )
            st.dataframe(
                display_df,
                hide_index=True,
                column_config={
                    "Stop Sequence": st.column_config.NumberColumn(width="small")
                }
            )

            st.subheader("Route Map")
            map_df = stop_times_df[['stop_lat', 'stop_lon']].rename(
                columns={'stop_lat': 'lat', 'stop_lon': 'lon'}
            )
            st.map(map_df)
        else:
            st.warning("No stop times found for this trip")

# Tab 3: Actual Trips
with tab3:
    from database import run_query, test_connection
    import pandas as pd
    from datetime import date

    if not test_connection():
        st.error("Database connection failed. Please check your configuration.")
        st.stop()

    # Initialize session state for showing record form
    if 'show_record_form' not in st.session_state:
        st.session_state.show_record_form = False
    if 'editing_trip_id' not in st.session_state:
        st.session_state.editing_trip_id = None

    # Show Record Trip form if button was clicked
    if st.session_state.show_record_form:
        st.header("Actual Trips")

        # Check if we're in edit mode
        editing_mode = st.session_state.editing_trip_id is not None

        # Load existing trip data if editing
        if editing_mode:
            existing_trip = run_query("""
                SELECT at.trip_id, at.observation_date, at.weather_condition,
                       r.route_id, t.direction_id
                FROM actual_trip at
                JOIN trip t ON at.trip_id = t.trip_id
                JOIN route r ON t.route_id = r.route_id
                WHERE at.actual_trip_id = %s
            """, params=(st.session_state.editing_trip_id,))

            existing_events = run_query("""
                SELECT ase.stop_id, ase.sequence_number, ase.actual_arrival_time,
                       ase.actual_departure_time, ase.event_type, ase.crowding_level,
                       ase.vehicle_number, s.stop_name
                FROM actual_stop_event ase
                JOIN stop s ON ase.stop_id = s.stop_id
                WHERE ase.actual_trip_id = %s
                ORDER BY ase.sequence_number
            """, params=(st.session_state.editing_trip_id,))

        # Header with back button and delete button (if editing)
        if editing_mode:
            col1, col2 = st.columns([3, 1])
            with col1:
                if st.button("Back to Actual Trips Table", type="secondary"):
                    st.session_state.show_record_form = False
                    st.session_state.editing_trip_id = None
                    st.rerun()
            with col2:
                delete_label = f"Delete Trip"
                if st.button(delete_label, type="secondary", use_container_width=True):
                    # Delete all stop events first
                    run_query("DELETE FROM actual_stop_event WHERE actual_trip_id = %s",
                             params=(st.session_state.editing_trip_id,))
                    # Then delete the trip
                    run_query("DELETE FROM actual_trip WHERE actual_trip_id = %s",
                             params=(st.session_state.editing_trip_id,))
                    st.success(f"Trip {st.session_state.editing_trip_id} deleted successfully!")
                    st.session_state.show_record_form = False
                    st.session_state.editing_trip_id = None
                    st.rerun()
        else:
            if st.button("Back to Actual Trips Table", type="secondary"):
                st.session_state.show_record_form = False
                st.rerun()

        st.divider()

        if editing_mode:
            st.subheader("Edit Trip")
        else:
            st.subheader("Step 1: Select Scheduled Trip")

        # Pre-fill form data if editing
        if editing_mode and not existing_trip.empty:
            existing_route_id = int(existing_trip.iloc[0]['route_id'])
            existing_direction = int(existing_trip.iloc[0]['direction_id'])
            existing_trip_id = int(existing_trip.iloc[0]['trip_id'])
            existing_date = existing_trip.iloc[0]['observation_date']
            existing_weather = existing_trip.iloc[0]['weather_condition']

            # Load existing events into session state
            if 'stop_events' not in st.session_state or not st.session_state.stop_events:
                st.session_state.stop_events = []
                for _, event in existing_events.iterrows():
                    st.session_state.stop_events.append({
                        'stop_sequence': int(event['sequence_number']),
                        'stop_id': int(event['stop_id']),
                        'stop_name': event['stop_name'],
                        'actual_arrival_time': normalize_time(event['actual_arrival_time']),
                        'actual_departure_time': normalize_time(event['actual_departure_time']),
                        'event_type': event['event_type'],
                        'crowding_level': int(event['crowding_level']) if pd.notna(event['crowding_level']) else None,
                        'vehicle_number': event['vehicle_number'] if pd.notna(event['vehicle_number']) else None
                    })

        col1, col2, col3 = st.columns(3)

        with col1:
            routes_df = run_query("""
                SELECT DISTINCT r.route_id, r.route_short_name, r.route_long_name
                FROM route r
            """)

            if not routes_df.empty:
                # sort numerically instead of alphabetically
                def sort_key(route_name):
                    try:
                        return (0, int(route_name))
                    except ValueError:
                        return (1, route_name)

                routes_df['sort_key'] = routes_df['route_short_name'].apply(sort_key)
                routes_df = routes_df.sort_values('sort_key').drop('sort_key', axis=1).reset_index(drop=True)
                route_options = []
                for _, row in routes_df.iterrows():
                    long_name = row['route_long_name'] if row['route_long_name'] else ""
                    if long_name:
                        route_options.append(f"{row['route_short_name']}: {long_name}")
                    else:
                        route_options.append(f"{row['route_short_name']}")

                # Find default index if editing
                default_route_idx = 0
                if editing_mode and not existing_trip.empty:
                    for i, row in routes_df.iterrows():
                        if int(row['route_id']) == existing_route_id:
                            default_route_idx = i
                            break

                selected_route_idx = st.selectbox(
                    "Route",
                    range(len(route_options)),
                    format_func=lambda x: route_options[x],
                    index=default_route_idx,
                    key="record_route",
                    disabled=editing_mode
                )
                selected_route_id = int(routes_df.iloc[selected_route_idx]['route_id'])
            else:
                st.warning("No routes found in database")
                st.stop()

        with col2:
            # Determine default direction
            default_direction = 0
            if editing_mode and not existing_trip.empty:
                default_direction = 0 if existing_direction == 0 else 1

            direction = st.selectbox("Direction", ["Outbound", "Inbound"],
                                    index=default_direction,
                                    key="record_direction",
                                    disabled=editing_mode)
            direction_filter = 0 if direction == "Outbound" else 1

        with col3:
            time_options = [
                ("07:00 AM", "07:00"), ("07:15 AM", "07:15"), ("07:30 AM", "07:30"), ("07:45 AM", "07:45"),
                ("08:00 AM", "08:00"), ("08:15 AM", "08:15"), ("08:30 AM", "08:30"), ("08:45 AM", "08:45"),
                ("09:00 AM", "09:00")
            ]
            time_col1, time_col2 = st.columns(2)
            with time_col1:
                start_time_idx = st.selectbox("Start", range(len(time_options)), index=0,
                                              format_func=lambda x: time_options[x][0], key="record_start")
            with time_col2:
                end_time_idx = st.selectbox("End", range(len(time_options)), index=8,
                                            format_func=lambda x: time_options[x][0], key="record_end")

            start_time = f"{time_options[start_time_idx][1]}:00"
            end_time = f"{time_options[end_time_idx][1]}:00"

        trips_query = """
            SELECT t.trip_id, t.trip_headsign, t.direction_id,
                   MIN(st.departure_time) as start_time
            FROM trip t
            JOIN stop_time st ON t.trip_id = st.trip_id
            WHERE t.route_id = %s AND t.direction_id = %s AND st.stop_sequence = 1
            GROUP BY t.trip_id, t.trip_headsign, t.direction_id
            HAVING MIN(st.departure_time) >= %s AND MIN(st.departure_time) < %s
            ORDER BY start_time
        """
        trips_df = run_query(trips_query, params=(selected_route_id, direction_filter, start_time, end_time))

        if trips_df.empty:
            st.warning("No trips found for this route and time range")
            st.stop()

        trips_df['display'] = trips_df.apply(
            lambda row: f"{row['start_time']} - {row['trip_headsign']} ({'Outbound' if row['direction_id'] == 0 else 'Inbound'})",
            axis=1
        )

        # Find default trip index if editing
        default_trip_idx = 0
        if editing_mode and not existing_trip.empty:
            for i, row in trips_df.iterrows():
                if int(row['trip_id']) == existing_trip_id:
                    default_trip_idx = i
                    break

        selected_trip_idx = st.selectbox(
            "Select the scheduled trip you are on",
            range(len(trips_df)),
            format_func=lambda x: trips_df.iloc[x]['display'],
            index=default_trip_idx,
            key="record_trip",
            disabled=editing_mode
        )

        selected_trip_id = int(trips_df.iloc[selected_trip_idx]['trip_id'])

        stop_times_query = """
            SELECT st.stop_sequence, s.stop_id, s.stop_name, st.arrival_time, st.departure_time
            FROM stop_time st
            JOIN stop s ON st.stop_id = s.stop_id
            WHERE st.trip_id = %s
            ORDER BY st.stop_sequence
        """
        scheduled_stops_df = run_query(stop_times_query, params=(selected_trip_id,))

        st.divider()
        st.subheader("Step 2: Trip Details")

        col1, col2 = st.columns(2)
        with col1:
            # Set default date
            default_date = existing_date if editing_mode and not existing_trip.empty else date.today()
            observation_date = st.date_input("Date of observation", value=default_date)
        with col2:
            # Set default weather
            weather_options = ["", "Clear", "Cloudy", "Rainy", "Snowy", "Foggy"]
            default_weather_idx = 0
            if editing_mode and not existing_trip.empty and existing_weather:
                try:
                    default_weather_idx = weather_options.index(existing_weather)
                except ValueError:
                    default_weather_idx = 0

            weather = st.selectbox("Weather condition",
                                  weather_options,
                                  index=default_weather_idx)

        st.divider()
        st.subheader("Step 3: Record Stop Events")

        st.write(f"Scheduled stops for this trip ({len(scheduled_stops_df)} stops):")

        if 'stop_events' not in st.session_state:
            st.session_state.stop_events = []

        with st.form("add_stop_event"):
            st.write("Add a stop event:")

            col1, col2, col3 = st.columns(3)
            with col1:
                # Add blank option at the beginning
                stop_options = [""] + [
                    f"{scheduled_stops_df.iloc[x]['stop_sequence']}. {scheduled_stops_df.iloc[x]['stop_name']} ({scheduled_stops_df.iloc[x]['arrival_time']})"
                    for x in range(len(scheduled_stops_df))
                ]
                stop_selection = st.selectbox("Stop", range(len(stop_options)),
                                             format_func=lambda x: stop_options[x] if stop_options[x] else "Select a stop...",
                                             index=0)
                # Adjust index since we added blank option
                stop_idx = stop_selection - 1 if stop_selection > 0 else None
            with col2:
                actual_arrival = st.text_input("Actual arrival time (HH:MM)", placeholder="08:30")
            with col3:
                actual_departure = st.text_input("Actual departure time (HH:MM)", placeholder="08:31")

            col1, col2, col3 = st.columns(3)
            with col1:
                event_type_display = st.selectbox("Event type", ["Got On", "Got Off", "Passed Through"])
                event_type_map = {"Got On": "boarding", "Got Off": "alighting", "Passed Through": "passthrough"}
                event_type = event_type_map[event_type_display]
            with col2:
                crowding = st.selectbox("Crowding level (1-5, optional)", ["", "1", "2", "3", "4", "5"])
            with col3:
                vehicle_num = st.text_input("Vehicle number (optional)")

            submitted = st.form_submit_button("Add Stop Event")

            if submitted:
                import re
                time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

                if stop_idx is None:
                    st.error("Please select a stop")
                elif not actual_arrival or not time_pattern.match(actual_arrival):
                    st.error("Please enter actual arrival time in HH:MM format (e.g., 08:30)")
                elif not actual_departure or not time_pattern.match(actual_departure):
                    st.error("Please enter actual departure time in HH:MM format (e.g., 08:31)")
                else:
                    stop_event = {
                        'stop_sequence': int(scheduled_stops_df.iloc[stop_idx]['stop_sequence']),
                        'stop_id': int(scheduled_stops_df.iloc[stop_idx]['stop_id']),
                        'stop_name': scheduled_stops_df.iloc[stop_idx]['stop_name'],
                        'actual_arrival_time': normalize_time(actual_arrival),
                        'actual_departure_time': normalize_time(actual_departure),
                        'event_type': event_type,
                        'crowding_level': int(crowding) if crowding else None,
                        'vehicle_number': vehicle_num if vehicle_num else None
                    }
                    st.session_state.stop_events.append(stop_event)
                    st.success(f"Added event at {stop_event['stop_name']}")

        if st.session_state.stop_events:
            st.write(f"Recorded events ({len(st.session_state.stop_events)}):")

            # Display each event as an editable div
            for idx, event in enumerate(st.session_state.stop_events):
                with st.container():
                    # Create header with delete button
                    col_header1, col_header2 = st.columns([5, 1])
                    with col_header1:
                        st.markdown(f"**Event {idx + 1}: {event['stop_name']}**")
                    with col_header2:
                        if st.button("Delete", key=f"delete_event_{idx}", type="secondary"):
                            st.session_state.stop_events.pop(idx)
                            st.rerun()

                    # Editable fields
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        new_arrival = st.text_input(f"Actual arrival (HH:MM)",
                                                   value=event['actual_arrival_time'][:5],
                                                   key=f"arrival_{idx}")
                        event['actual_arrival_time'] = f"{new_arrival}:00"
                    with col2:
                        new_departure = st.text_input(f"Actual departure (HH:MM)",
                                                     value=event['actual_departure_time'][:5],
                                                     key=f"departure_{idx}")
                        event['actual_departure_time'] = f"{new_departure}:00"
                    with col3:
                        event_types = ["boarding", "alighting", "passthrough"]
                        current_event_idx = event_types.index(event['event_type']) if event['event_type'] in event_types else 0
                        event['event_type'] = st.selectbox("Event type", event_types,
                                                          index=current_event_idx,
                                                          key=f"event_type_{idx}")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        crowding_opts = ["", "1", "2", "3", "4", "5"]
                        current_crowding = str(int(event['crowding_level'])) if event['crowding_level'] and event['crowding_level'] is not None else ""
                        crowding_idx = crowding_opts.index(current_crowding) if current_crowding in crowding_opts else 0
                        new_crowding = st.selectbox("Crowding level", crowding_opts,
                                                   index=crowding_idx,
                                                   key=f"crowding_{idx}")
                        event['crowding_level'] = int(new_crowding) if new_crowding else None
                    with col2:
                        vehicle_value = event['vehicle_number'] if event['vehicle_number'] and event['vehicle_number'] is not None else ""
                        new_vehicle = st.text_input("Vehicle number",
                                                   value=str(vehicle_value),
                                                   key=f"vehicle_{idx}")
                        event['vehicle_number'] = new_vehicle if new_vehicle else None
                    with col3:
                        st.write("")  # Spacing

                    st.divider()

            # Save button on the right
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write("")  # Spacing
            with col2:
                save_button_label = "Update Trip" if editing_mode else "Save Trip"
                if st.button(save_button_label, type="secondary", use_container_width=True):
                    weather_val = weather if weather else None

                    if editing_mode:
                        # Update existing trip
                        update_trip_query = """
                            UPDATE actual_trip
                            SET observation_date = %s, weather_condition = %s
                            WHERE actual_trip_id = %s
                        """
                        run_query(update_trip_query, params=(observation_date, weather_val, st.session_state.editing_trip_id))

                        # Delete existing stop events
                        run_query("DELETE FROM actual_stop_event WHERE actual_trip_id = %s",
                                 params=(st.session_state.editing_trip_id,))

                        # Insert updated stop events
                        for idx, event in enumerate(st.session_state.stop_events, start=1):
                            insert_event_query = """
                                INSERT INTO actual_stop_event
                                (actual_trip_id, stop_id, sequence_number, actual_arrival_time,
                                 actual_departure_time, event_type, crowding_level, vehicle_number)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            run_query(insert_event_query, params=(
                                st.session_state.editing_trip_id,
                                event['stop_id'],
                                idx,
                                event['actual_arrival_time'],
                                event['actual_departure_time'],
                                event['event_type'],
                                event['crowding_level'],
                                event['vehicle_number']
                            ))

                        st.success(f"Trip {st.session_state.editing_trip_id} updated successfully!")
                        st.session_state.stop_events = []
                        st.session_state.show_record_form = False
                        st.session_state.editing_trip_id = None
                        st.rerun()
                    else:
                        # Insert new trip
                        insert_trip_query = """
                            INSERT INTO actual_trip (trip_id, observation_date, weather_condition)
                            VALUES (%s, %s, %s)
                            RETURNING actual_trip_id
                        """
                        result = run_query(insert_trip_query, params=(selected_trip_id, observation_date, weather_val))

                        if not result.empty:
                            actual_trip_id = int(result.iloc[0]['actual_trip_id'])

                            for idx, event in enumerate(st.session_state.stop_events, start=1):
                                insert_event_query = """
                                    INSERT INTO actual_stop_event
                                    (actual_trip_id, stop_id, sequence_number, actual_arrival_time,
                                     actual_departure_time, event_type, crowding_level, vehicle_number)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """
                                run_query(insert_event_query, params=(
                                    actual_trip_id,
                                    event['stop_id'],
                                    idx,
                                    event['actual_arrival_time'],
                                    event['actual_departure_time'],
                                    event['event_type'],
                                    event['crowding_level'],
                                    event['vehicle_number']
                                ))

                            st.success(f"Trip recorded successfully! Actual Trip ID: {actual_trip_id}")
                            st.session_state.stop_events = []
                        else:
                            st.error("Failed to save trip")
        else:
            st.info("No stop events recorded yet. Add events above to record your trip.")

    else:
        # Show the Actual Trips table view

        # Header with Record Trip button
        col1, col2 = st.columns([5, 1])
        with col1:
            st.header("Actual Trips")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Record Trip", type="secondary", use_container_width=True, key="record_trip_top"):
                st.session_state.show_record_form = True
                st.session_state.editing_trip_id = None
                st.rerun()

        st.warning("**MOCKUP DATA** - The data shown below is sample data.")

        # Filters section
        st.subheader("Filters")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            # Route filter
            routes_df = run_query("""
                SELECT DISTINCT r.route_id, r.route_short_name, r.route_long_name
                FROM route r
                ORDER BY r.route_short_name
            """)

            if not routes_df.empty:
                route_filter_options = ["All Routes"] + [
                    f"{row['route_short_name']}: {row['route_long_name']}" if row['route_long_name']
                    else row['route_short_name']
                    for _, row in routes_df.iterrows()
                ]
                selected_route_filter = st.selectbox("Route", route_filter_options, key="actual_trips_route")

        with col2:
            # Date filter
            date_filter_options = ["All Dates", "Last 7 Days", "Last 30 Days"]
            selected_date_filter = st.selectbox("Date Range", date_filter_options, key="actual_trips_date")

        with col3:
            # Weather filter
            weather_filter_options = ["All Weather", "Clear", "Cloudy", "Rainy", "Snowy", "Foggy"]
            selected_weather_filter = st.selectbox("Weather", weather_filter_options, key="actual_trips_weather")

        # Query actual trips based on first three filters
        trips_query = """
            SELECT
                at.actual_trip_id,
                at.trip_id,
                r.route_short_name,
                r.route_long_name,
                t.trip_headsign,
                t.direction_id,
                at.observation_date,
                at.weather_condition,
                COUNT(ase.sequence_number) as stop_events
            FROM actual_trip at
            JOIN trip t ON at.trip_id = t.trip_id
            JOIN route r ON t.route_id = r.route_id
            LEFT JOIN actual_stop_event ase ON at.actual_trip_id = ase.actual_trip_id
        """

        conditions = []
        params = []

        if selected_route_filter != "All Routes":
            route_short_name = selected_route_filter.split(":")[0].strip()
            conditions.append("r.route_short_name = %s")
            params.append(route_short_name)

        if selected_date_filter == "Last 7 Days":
            conditions.append("at.observation_date >= CURRENT_DATE - INTERVAL '7 days'")
        elif selected_date_filter == "Last 30 Days":
            conditions.append("at.observation_date >= CURRENT_DATE - INTERVAL '30 days'")

        if selected_weather_filter != "All Weather":
            conditions.append("at.weather_condition = %s")
            params.append(selected_weather_filter)

        if conditions:
            trips_query += " WHERE " + " AND ".join(conditions)

        trips_query += """
            GROUP BY at.actual_trip_id, at.trip_id, r.route_short_name, r.route_long_name,
                     t.trip_headsign, t.direction_id, at.observation_date, at.weather_condition, at.created_at
            ORDER BY at.created_at DESC
        """

        actual_trips_df = run_query(trips_query, params=tuple(params) if params else None)

        with col4:
            # Actual Trip filter (dropdown based on filtered trips)
            if not actual_trips_df.empty:
                trip_options = ["All"] + [
                    f"({row['observation_date']}) - {row['route_short_name']}: {row['route_long_name']}"
                    for _, row in actual_trips_df.iterrows()
                ]
                selected_trip_idx = st.selectbox("Actual Trip", range(len(trip_options)),
                                                 format_func=lambda x: trip_options[x],
                                                 key="actual_trip_select")
                if selected_trip_idx == 0:  # "All" selected
                    selected_actual_trip_id = None
                else:
                    selected_actual_trip_id = int(actual_trips_df.iloc[selected_trip_idx - 1]['actual_trip_id'])
            else:
                st.selectbox("Actual Trip", ["No trips found"], key="actual_trip_select", disabled=True)
                selected_actual_trip_id = None

        st.divider()

        if not actual_trips_df.empty:
            if selected_actual_trip_id:
                # Query actual stop events for a specific trip
                events_query = """
                    SELECT
                        ase.actual_trip_id,
                        r.route_short_name,
                        at.observation_date,
                        ase.sequence_number,
                        ase.stop_id,
                        s.stop_name,
                        st.arrival_time as scheduled_arrival,
                        ase.actual_arrival_time,
                        st.departure_time as scheduled_departure,
                        ase.actual_departure_time,
                        ase.event_type,
                        ase.crowding_level,
                        ase.vehicle_number,
                        EXTRACT(EPOCH FROM (ase.actual_arrival_time - st.arrival_time))/60 as arrival_diff_minutes
                    FROM actual_stop_event ase
                    JOIN stop s ON ase.stop_id = s.stop_id
                    JOIN actual_trip at ON ase.actual_trip_id = at.actual_trip_id
                    JOIN trip t ON at.trip_id = t.trip_id
                    JOIN route r ON t.route_id = r.route_id
                    LEFT JOIN stop_time st ON at.trip_id = st.trip_id AND ase.stop_id = st.stop_id
                    WHERE ase.actual_trip_id = %s
                    ORDER BY ase.sequence_number
                """
                events_df = run_query(events_query, params=(selected_actual_trip_id,))
            else:
                # Query actual stop events for all filtered trips
                trip_ids = tuple(actual_trips_df['actual_trip_id'].tolist())
                if len(trip_ids) == 1:
                    events_query = """
                        SELECT
                            ase.actual_trip_id,
                            r.route_short_name,
                            at.observation_date,
                            ase.sequence_number,
                            ase.stop_id,
                            s.stop_name,
                            st.arrival_time as scheduled_arrival,
                            ase.actual_arrival_time,
                            st.departure_time as scheduled_departure,
                            ase.actual_departure_time,
                            ase.event_type,
                            ase.crowding_level,
                            ase.vehicle_number,
                            EXTRACT(EPOCH FROM (ase.actual_arrival_time - st.arrival_time))/60 as arrival_diff_minutes
                        FROM actual_stop_event ase
                        JOIN stop s ON ase.stop_id = s.stop_id
                        JOIN actual_trip at ON ase.actual_trip_id = at.actual_trip_id
                        JOIN trip t ON at.trip_id = t.trip_id
                        JOIN route r ON t.route_id = r.route_id
                        LEFT JOIN stop_time st ON at.trip_id = st.trip_id AND ase.stop_id = st.stop_id
                        WHERE ase.actual_trip_id = %s
                        ORDER BY at.observation_date, ase.actual_trip_id, ase.sequence_number
                    """
                    events_df = run_query(events_query, params=(trip_ids[0],))
                else:
                    events_query = """
                        SELECT
                            ase.actual_trip_id,
                            r.route_short_name,
                            at.observation_date,
                            ase.sequence_number,
                            ase.stop_id,
                            s.stop_name,
                            st.arrival_time as scheduled_arrival,
                            ase.actual_arrival_time,
                            st.departure_time as scheduled_departure,
                            ase.actual_departure_time,
                            ase.event_type,
                            ase.crowding_level,
                            ase.vehicle_number,
                            EXTRACT(EPOCH FROM (ase.actual_arrival_time - st.arrival_time))/60 as arrival_diff_minutes
                        FROM actual_stop_event ase
                        JOIN stop s ON ase.stop_id = s.stop_id
                        JOIN actual_trip at ON ase.actual_trip_id = at.actual_trip_id
                        JOIN trip t ON at.trip_id = t.trip_id
                        JOIN route r ON t.route_id = r.route_id
                        LEFT JOIN stop_time st ON at.trip_id = st.trip_id AND ase.stop_id = st.stop_id
                        WHERE ase.actual_trip_id IN %s
                        ORDER BY at.observation_date, ase.actual_trip_id, ase.sequence_number
                    """
                    events_df = run_query(events_query, params=(trip_ids,))

            if not events_df.empty:
                # Header with count and Edit Trip button
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.subheader(f"Actual Stop Events ({len(events_df)} found)")
                with col2:
                    if selected_actual_trip_id:
                        # Get trip info for button label
                        trip_info = actual_trips_df.iloc[selected_trip_idx - 1]
                        edit_label = f"Edit Trip {selected_actual_trip_id}: {trip_info['route_short_name']} - {trip_info['trip_headsign']}"
                        if st.button(edit_label, type="secondary", use_container_width=True):
                            st.session_state.show_record_form = True
                            st.session_state.editing_trip_id = selected_actual_trip_id
                            st.rerun()

                # Format the display
                display_df = events_df.copy()

                # Format difference column (positive = late, negative = early)
                display_df['Difference'] = display_df['arrival_diff_minutes'].apply(
                    lambda x: "N/A" if x is None else (f"+{int(x)} min" if x > 0 else f"{int(x)} min")
                )

                # Format event type
                display_df['Event'] = display_df['event_type'].apply(
                    lambda x: x.capitalize() if x else ""
                )

                # Select and rename columns based on whether showing all trips or single trip
                if selected_actual_trip_id:
                    # Single trip - don't show trip info
                    final_display_df = display_df[[
                        'sequence_number', 'stop_name', 'scheduled_arrival', 'actual_arrival_time',
                        'Difference', 'Event', 'crowding_level', 'vehicle_number'
                    ]].rename(columns={
                        'sequence_number': 'Seq',
                        'stop_name': 'Stop Name',
                        'scheduled_arrival': 'Scheduled',
                        'actual_arrival_time': 'Actual',
                        'crowding_level': 'Crowding',
                        'vehicle_number': 'Vehicle'
                    })
                else:
                    # All trips - show trip info
                    final_display_df = display_df[[
                        'actual_trip_id', 'route_short_name', 'observation_date', 'sequence_number',
                        'stop_name', 'scheduled_arrival', 'actual_arrival_time',
                        'Difference', 'Event', 'crowding_level', 'vehicle_number'
                    ]].rename(columns={
                        'actual_trip_id': 'Trip ID',
                        'route_short_name': 'Route',
                        'observation_date': 'Date',
                        'sequence_number': 'Seq',
                        'stop_name': 'Stop Name',
                        'scheduled_arrival': 'Scheduled',
                        'actual_arrival_time': 'Actual',
                        'crowding_level': 'Crowding',
                        'vehicle_number': 'Vehicle'
                    })

                # Replace None with empty string for display
                final_display_df['Crowding'] = final_display_df['Crowding'].fillna('').astype(str).replace('', '-')
                final_display_df['Vehicle'] = final_display_df['Vehicle'].fillna('-')

                # Configure columns based on view
                if selected_actual_trip_id:
                    column_config = {
                        "Seq": st.column_config.NumberColumn(width="small"),
                        "Stop Name": st.column_config.TextColumn(width="large"),
                        "Scheduled": st.column_config.TimeColumn(width="small"),
                        "Actual": st.column_config.TimeColumn(width="small"),
                        "Difference": st.column_config.TextColumn(width="small"),
                        "Event": st.column_config.TextColumn(width="small"),
                        "Crowding": st.column_config.TextColumn(width="small"),
                        "Vehicle": st.column_config.TextColumn(width="small")
                    }
                else:
                    column_config = {
                        "Trip ID": st.column_config.NumberColumn(width="small"),
                        "Route": st.column_config.TextColumn(width="small"),
                        "Date": st.column_config.DateColumn(width="small"),
                        "Seq": st.column_config.NumberColumn(width="small"),
                        "Stop Name": st.column_config.TextColumn(width="medium"),
                        "Scheduled": st.column_config.TimeColumn(width="small"),
                        "Actual": st.column_config.TimeColumn(width="small"),
                        "Difference": st.column_config.TextColumn(width="small"),
                        "Event": st.column_config.TextColumn(width="small"),
                        "Crowding": st.column_config.TextColumn(width="small"),
                        "Vehicle": st.column_config.TextColumn(width="small")
                    }

                st.dataframe(
                    final_display_df,
                    hide_index=True,
                    column_config=column_config,
                    use_container_width=True
                )
            else:
                st.subheader("Actual Stop Events (0 found)")
                st.info("No stop events found for the selected filters.")
        else:
            st.subheader("Actual Stop Events (0 found)")
            st.info("No actual trips recorded yet. Click 'Record Trip' to add your first trip.")
