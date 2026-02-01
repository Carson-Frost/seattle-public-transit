"""Actual Trips tab - view recorded trip observations."""

import streamlit as st

from database import run_query, test_connection
from constants import WEATHER_OPTIONS
from utils import sort_route_key


def render():
    """Render the Actual Trips tab."""
    st.header("Actual Trips", anchor=False)

    if not test_connection():
        st.error("Database connection failed. Please check your configuration.")
        st.stop()

    st.warning("**Sample Data** - Actual trip data is sample data for demonstration.")

    # Filters
    st.subheader("Filters", anchor=False)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        routes_df = run_query("""
            SELECT DISTINCT r.route_id, r.route_short_name, r.route_long_name
            FROM route r ORDER BY r.route_short_name
        """)

        if not routes_df.empty:
            route_filter_opts = ["All Routes"] + [
                f"{row['route_short_name']}: {row['route_long_name']}" if row['route_long_name']
                else row['route_short_name']
                for _, row in routes_df.iterrows()
            ]
            route_filter = st.selectbox("Route", route_filter_opts, key="actual_trips_route")

    with col2:
        date_filter_opts = ["All Dates", "Last 7 Days", "Last 30 Days"]
        date_filter = st.selectbox("Date Range", date_filter_opts, key="actual_trips_date")

    with col3:
        weather_filter_opts = ["All Weather"] + WEATHER_OPTIONS + ["Snowy"]
        weather_filter = st.selectbox("Weather", weather_filter_opts, key="actual_trips_weather")

    # Build query
    query = """
        SELECT at.actual_trip_id, at.trip_id, r.route_short_name, r.route_long_name,
               t.trip_headsign, t.direction_id, at.observation_date, at.weather_condition,
               COUNT(ase.sequence_number) as stop_events
        FROM actual_trip at
        JOIN trip t ON at.trip_id = t.trip_id
        JOIN route r ON t.route_id = r.route_id
        LEFT JOIN actual_stop_event ase ON at.actual_trip_id = ase.actual_trip_id
    """

    conditions = []
    params = []

    if route_filter != "All Routes":
        route_short = route_filter.split(":")[0].strip()
        conditions.append("r.route_short_name = %s")
        params.append(route_short)

    if date_filter == "Last 7 Days":
        conditions.append("at.observation_date >= CURRENT_DATE - INTERVAL '7 days'")
    elif date_filter == "Last 30 Days":
        conditions.append("at.observation_date >= CURRENT_DATE - INTERVAL '30 days'")

    if weather_filter != "All Weather":
        conditions.append("at.weather_condition = %s")
        params.append(weather_filter)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += """
        GROUP BY at.actual_trip_id, at.trip_id, r.route_short_name, r.route_long_name,
                 t.trip_headsign, t.direction_id, at.observation_date, at.weather_condition, at.created_at
        ORDER BY at.created_at DESC
    """

    actual_trips = run_query(query, params=tuple(params) if params else None)

    with col4:
        if not actual_trips.empty:
            trip_opts = ["All"] + [
                f"({row['observation_date']}) - {row['route_short_name']}: {row['route_long_name']}"
                for _, row in actual_trips.iterrows()
            ]
            trip_sel = st.selectbox("Actual Trip", range(len(trip_opts)),
                                    format_func=lambda x: trip_opts[x],
                                    key="actual_trip_select")
            selected_trip_id = None if trip_sel == 0 else int(actual_trips.iloc[trip_sel - 1]['actual_trip_id'])
        else:
            st.selectbox("Actual Trip", ["No trips found"], key="actual_trip_select", disabled=True)
            selected_trip_id = None

    st.divider()

    if not actual_trips.empty:
        _display_stop_events(actual_trips, selected_trip_id, trip_sel if not actual_trips.empty else 0)
    else:
        st.subheader("Actual Stop Events (0 found)", anchor=False)
        st.info("No actual trips found for the selected filters.")


def _display_stop_events(actual_trips, selected_trip_id, trip_sel):
    """Display stop events for selected or all trips."""
    if selected_trip_id:
        events_query = """
            SELECT ase.actual_trip_id, r.route_short_name, at.observation_date,
                   ase.sequence_number, ase.stop_id, s.stop_name,
                   st.arrival_time as scheduled_arrival, ase.actual_arrival_time,
                   st.departure_time as scheduled_departure, ase.actual_departure_time,
                   ase.event_type, ase.crowding_level, ase.vehicle_number,
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
        events_df = run_query(events_query, params=(selected_trip_id,))
    else:
        trip_ids = tuple(actual_trips['actual_trip_id'].tolist())
        if len(trip_ids) == 1:
            events_query = """
                SELECT ase.actual_trip_id, r.route_short_name, at.observation_date,
                       ase.sequence_number, ase.stop_id, s.stop_name,
                       st.arrival_time as scheduled_arrival, ase.actual_arrival_time,
                       st.departure_time as scheduled_departure, ase.actual_departure_time,
                       ase.event_type, ase.crowding_level, ase.vehicle_number,
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
                SELECT ase.actual_trip_id, r.route_short_name, at.observation_date,
                       ase.sequence_number, ase.stop_id, s.stop_name,
                       st.arrival_time as scheduled_arrival, ase.actual_arrival_time,
                       st.departure_time as scheduled_departure, ase.actual_departure_time,
                       ase.event_type, ase.crowding_level, ase.vehicle_number,
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
        st.subheader(f"Actual Stop Events ({len(events_df)} found)", anchor=False)

        display_df = events_df.copy()

        display_df['Difference'] = display_df['arrival_diff_minutes'].apply(
            lambda x: "N/A" if x is None else (f"+{int(x)} min" if x > 0 else f"{int(x)} min")
        )
        display_df['Event'] = display_df['event_type'].apply(lambda x: x.capitalize() if x else "")

        if selected_trip_id:
            final_df = display_df[[
                'sequence_number', 'stop_name', 'scheduled_arrival', 'actual_arrival_time',
                'Difference', 'Event', 'crowding_level', 'vehicle_number'
            ]].rename(columns={
                'sequence_number': 'Seq', 'stop_name': 'Stop Name',
                'scheduled_arrival': 'Scheduled', 'actual_arrival_time': 'Actual',
                'crowding_level': 'Crowding', 'vehicle_number': 'Vehicle'
            })
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
            final_df = display_df[[
                'actual_trip_id', 'route_short_name', 'observation_date', 'sequence_number',
                'stop_name', 'scheduled_arrival', 'actual_arrival_time',
                'Difference', 'Event', 'crowding_level', 'vehicle_number'
            ]].rename(columns={
                'actual_trip_id': 'Trip ID', 'route_short_name': 'Route',
                'observation_date': 'Date', 'sequence_number': 'Seq',
                'stop_name': 'Stop Name', 'scheduled_arrival': 'Scheduled',
                'actual_arrival_time': 'Actual', 'crowding_level': 'Crowding',
                'vehicle_number': 'Vehicle'
            })
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

        final_df['Crowding'] = final_df['Crowding'].fillna('').astype(str).replace('', '-')
        final_df['Vehicle'] = final_df['Vehicle'].fillna('-')

        st.dataframe(final_df, hide_index=True, column_config=column_config, use_container_width=True)
    else:
        st.subheader("Actual Stop Events (0 found)", anchor=False)
        st.info("No stop events found for the selected filters.")
