"""Actual Trips tab - record and view actual trip observations."""

import re
import streamlit as st
import pandas as pd
from datetime import date

from database import run_query, test_connection
from constants import WEATHER_OPTIONS
from utils import sort_route_key, get_routes, normalize_time


def render():
    """Render the Actual Trips tab."""
    if not test_connection():
        st.error("Database connection failed. Please check your configuration.")
        st.stop()

    # Initialize session state
    if 'show_record_form' not in st.session_state:
        st.session_state.show_record_form = False
    if 'editing_actual_trip_id' not in st.session_state:
        st.session_state.editing_actual_trip_id = None

    if st.session_state.show_record_form:
        _render_record_form()
    else:
        _render_trips_table()


def _render_record_form():
    """Render the record/edit trip form."""
    st.header("Actual Trips")

    editing = st.session_state.editing_actual_trip_id is not None

    # Load existing data if editing
    if editing:
        trip = run_query("""
            SELECT at.trip_id, at.observation_date, at.weather_condition,
                   r.route_id, t.direction_id
            FROM actual_trip at
            JOIN trip t ON at.trip_id = t.trip_id
            JOIN route r ON t.route_id = r.route_id
            WHERE at.actual_trip_id = %s
        """, params=(st.session_state.editing_actual_trip_id,))

        events = run_query("""
            SELECT ase.stop_id, ase.sequence_number, ase.actual_arrival_time,
                   ase.actual_departure_time, ase.event_type, ase.crowding_level,
                   ase.vehicle_number, s.stop_name
            FROM actual_stop_event ase
            JOIN stop s ON ase.stop_id = s.stop_id
            WHERE ase.actual_trip_id = %s
            ORDER BY ase.sequence_number
        """, params=(st.session_state.editing_actual_trip_id,))

    # Header with back and delete buttons
    if editing:
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("Back to Actual Trips Table", type="secondary"):
                _clear_form_state()
                st.rerun()
        with col2:
            if st.button("Delete Trip", type="secondary", use_container_width=True):
                run_query("DELETE FROM actual_stop_event WHERE actual_trip_id = %s",
                         params=(st.session_state.editing_actual_trip_id,))
                run_query("DELETE FROM actual_trip WHERE actual_trip_id = %s",
                         params=(st.session_state.editing_actual_trip_id,))
                st.success(f"Trip {st.session_state.editing_actual_trip_id} deleted successfully!")
                _clear_form_state()
                st.rerun()
    else:
        if st.button("Back to Actual Trips Table", type="secondary"):
            _clear_form_state()
            st.rerun()

    st.divider()
    st.subheader("Edit Trip" if editing else "Step 1: Select Scheduled Trip")

    # Pre-fill defaults if editing
    defaults = {}
    if editing and not trip.empty:
        row = trip.iloc[0]
        defaults = {
            'route_id': int(row['route_id']),
            'direction': int(row['direction_id']),
            'trip_id': int(row['trip_id']),
            'date': row['observation_date'],
            'weather': row['weather_condition']
        }

        # Load existing events into session state
        if 'stop_events' not in st.session_state or not st.session_state.stop_events:
            st.session_state.stop_events = [
                {
                    'stop_sequence': int(ev['sequence_number']),
                    'stop_id': int(ev['stop_id']),
                    'stop_name': ev['stop_name'],
                    'actual_arrival_time': normalize_time(ev['actual_arrival_time']),
                    'actual_departure_time': normalize_time(ev['actual_departure_time']),
                    'event_type': ev['event_type'],
                    'crowding_level': int(ev['crowding_level']) if pd.notna(ev['crowding_level']) else None,
                    'vehicle_number': ev['vehicle_number'] if pd.notna(ev['vehicle_number']) else None
                }
                for _, ev in events.iterrows()
            ]

    col1, col2, col3 = st.columns(3)

    with col1:
        routes_df, route_options, _ = get_routes()
        if routes_df.empty:
            st.warning("No routes found in database")
            st.stop()

        default_idx = 0
        if 'route_id' in defaults:
            for i, row in routes_df.iterrows():
                if int(row['route_id']) == defaults['route_id']:
                    default_idx = i
                    break

        route_idx = st.selectbox("Route", range(len(route_options)),
                                 format_func=lambda x: route_options[x],
                                 index=default_idx, key="record_route",
                                 disabled=editing)
        route_id = int(routes_df.iloc[route_idx]['route_id'])

    with col2:
        direction = st.selectbox("Direction", ["Outbound", "Inbound"],
                                 index=defaults.get('direction', 0),
                                 key="record_direction", disabled=editing)
        direction_filter = 0 if direction == "Outbound" else 1

    with col3:
        time_opts = [
            ("07:00 AM", "07:00"), ("07:15 AM", "07:15"), ("07:30 AM", "07:30"), ("07:45 AM", "07:45"),
            ("08:00 AM", "08:00"), ("08:15 AM", "08:15"), ("08:30 AM", "08:30"), ("08:45 AM", "08:45"),
            ("09:00 AM", "09:00")
        ]
        time_col1, time_col2 = st.columns(2)
        with time_col1:
            start_idx = st.selectbox("Start", range(len(time_opts)), index=0,
                                     format_func=lambda x: time_opts[x][0], key="record_start")
        with time_col2:
            end_idx = st.selectbox("End", range(len(time_opts)), index=8,
                                   format_func=lambda x: time_opts[x][0], key="record_end")

        start_time = f"{time_opts[start_idx][1]}:00"
        end_time = f"{time_opts[end_idx][1]}:00"

    # Query trips
    trips_df = run_query("""
        SELECT t.trip_id, t.trip_headsign, t.direction_id,
               MIN(st.departure_time) as start_time
        FROM trip t
        JOIN stop_time st ON t.trip_id = st.trip_id
        WHERE t.route_id = %s AND t.direction_id = %s AND st.stop_sequence = 1
        GROUP BY t.trip_id, t.trip_headsign, t.direction_id
        HAVING MIN(st.departure_time) >= %s AND MIN(st.departure_time) < %s
        ORDER BY start_time
    """, params=(route_id, direction_filter, start_time, end_time))

    if trips_df.empty:
        st.warning("No trips found for this route and time range")
        st.stop()

    trips_df['display'] = trips_df.apply(
        lambda row: f"{row['start_time']} - {row['trip_headsign']} ({'Outbound' if row['direction_id'] == 0 else 'Inbound'})",
        axis=1
    )

    # Find default trip index if editing
    default_trip_idx = 0
    if 'trip_id' in defaults:
        for i, row in trips_df.iterrows():
            if int(row['trip_id']) == defaults['trip_id']:
                default_trip_idx = i
                break

    trip_idx = st.selectbox("Select the scheduled trip you are on", range(len(trips_df)),
                            format_func=lambda x: trips_df.iloc[x]['display'],
                            index=default_trip_idx, key="record_trip",
                            disabled=editing)
    trip_id = int(trips_df.iloc[trip_idx]['trip_id'])

    # Get scheduled stops
    scheduled_stops = run_query("""
        SELECT st.stop_sequence, s.stop_id, s.stop_name, st.arrival_time, st.departure_time
        FROM stop_time st
        JOIN stop s ON st.stop_id = s.stop_id
        WHERE st.trip_id = %s
        ORDER BY st.stop_sequence
    """, params=(trip_id,))

    st.divider()
    st.subheader("Step 2: Trip Details")

    col1, col2 = st.columns(2)
    with col1:
        default_date = defaults.get('date', date.today())
        observation_date = st.date_input("Date of observation", value=default_date)
    with col2:
        weather_opts = [""] + WEATHER_OPTIONS + ["Snowy"]
        default_weather_idx = 0
        if defaults.get('weather'):
            try:
                default_weather_idx = weather_opts.index(defaults['weather'])
            except ValueError:
                pass
        weather = st.selectbox("Weather condition", weather_opts, index=default_weather_idx)

    st.divider()
    st.subheader("Step 3: Record Stop Events")

    st.write(f"Scheduled stops for this trip ({len(scheduled_stops)} stops):")

    if 'stop_events' not in st.session_state:
        st.session_state.stop_events = []

    # Add stop event form
    with st.form("add_stop_event"):
        st.write("Add a stop event:")

        col1, col2, col3 = st.columns(3)
        with col1:
            stop_options = [""] + [
                f"{scheduled_stops.iloc[x]['stop_sequence']}. {scheduled_stops.iloc[x]['stop_name']} ({scheduled_stops.iloc[x]['arrival_time']})"
                for x in range(len(scheduled_stops))
            ]
            stop_sel = st.selectbox("Stop", range(len(stop_options)),
                                    format_func=lambda x: stop_options[x] if stop_options[x] else "Select a stop...",
                                    index=0)
            stop_idx = stop_sel - 1 if stop_sel > 0 else None
        with col2:
            actual_arrival = st.text_input("Actual arrival time (HH:MM)", placeholder="08:30")
        with col3:
            actual_departure = st.text_input("Actual departure time (HH:MM)", placeholder="08:31")

        col1, col2, col3 = st.columns(3)
        with col1:
            event_display = st.selectbox("Event type", ["Got On", "Got Off", "Passed Through"])
            event_map = {"Got On": "boarding", "Got Off": "alighting", "Passed Through": "passthrough"}
            event_type = event_map[event_display]
        with col2:
            crowding = st.selectbox("Crowding level (1-5, optional)", ["", "1", "2", "3", "4", "5"])
        with col3:
            vehicle_num = st.text_input("Vehicle number (optional)")

        if st.form_submit_button("Add Stop Event"):
            time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

            if stop_idx is None:
                st.error("Please select a stop")
            elif not actual_arrival or not time_pattern.match(actual_arrival):
                st.error("Please enter actual arrival time in HH:MM format (e.g., 08:30)")
            elif not actual_departure or not time_pattern.match(actual_departure):
                st.error("Please enter actual departure time in HH:MM format (e.g., 08:31)")
            else:
                st.session_state.stop_events.append({
                    'stop_sequence': int(scheduled_stops.iloc[stop_idx]['stop_sequence']),
                    'stop_id': int(scheduled_stops.iloc[stop_idx]['stop_id']),
                    'stop_name': scheduled_stops.iloc[stop_idx]['stop_name'],
                    'actual_arrival_time': normalize_time(actual_arrival),
                    'actual_departure_time': normalize_time(actual_departure),
                    'event_type': event_type,
                    'crowding_level': int(crowding) if crowding else None,
                    'vehicle_number': vehicle_num if vehicle_num else None
                })
                st.success(f"Added event at {scheduled_stops.iloc[stop_idx]['stop_name']}")

    if st.session_state.stop_events:
        st.write(f"Recorded events ({len(st.session_state.stop_events)}):")

        for idx, event in enumerate(st.session_state.stop_events):
            with st.container():
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"**Event {idx + 1}: {event['stop_name']}**")
                with col2:
                    if st.button("Delete", key=f"delete_event_{idx}", type="secondary"):
                        st.session_state.stop_events.pop(idx)
                        st.rerun()

                col1, col2, col3 = st.columns(3)
                with col1:
                    new_arrival = st.text_input("Actual arrival (HH:MM)",
                                               value=event['actual_arrival_time'][:5],
                                               key=f"arrival_{idx}")
                    event['actual_arrival_time'] = f"{new_arrival}:00"
                with col2:
                    new_departure = st.text_input("Actual departure (HH:MM)",
                                                 value=event['actual_departure_time'][:5],
                                                 key=f"departure_{idx}")
                    event['actual_departure_time'] = f"{new_departure}:00"
                with col3:
                    event_types = ["boarding", "alighting", "passthrough"]
                    current_idx = event_types.index(event['event_type']) if event['event_type'] in event_types else 0
                    event['event_type'] = st.selectbox("Event type", event_types,
                                                      index=current_idx, key=f"event_type_{idx}")

                col1, col2, _ = st.columns(3)
                with col1:
                    crowding_opts = ["", "1", "2", "3", "4", "5"]
                    current_crowding = str(int(event['crowding_level'])) if event['crowding_level'] else ""
                    crowding_idx = crowding_opts.index(current_crowding) if current_crowding in crowding_opts else 0
                    new_crowding = st.selectbox("Crowding level", crowding_opts,
                                               index=crowding_idx, key=f"crowding_{idx}")
                    event['crowding_level'] = int(new_crowding) if new_crowding else None
                with col2:
                    vehicle_value = event['vehicle_number'] if event['vehicle_number'] else ""
                    new_vehicle = st.text_input("Vehicle number", value=str(vehicle_value),
                                               key=f"vehicle_{idx}")
                    event['vehicle_number'] = new_vehicle if new_vehicle else None

                st.divider()

        # Save button
        col1, col2 = st.columns([5, 1])
        with col2:
            label = "Update Trip" if editing else "Save Trip"
            if st.button(label, type="secondary", use_container_width=True):
                _save_actual_trip(editing, trip_id, observation_date, weather)
    else:
        st.info("No stop events recorded yet. Add events above to record your trip.")


def _save_actual_trip(editing, trip_id, observation_date, weather):
    """Save or update an actual trip."""
    weather_val = weather if weather else None

    if editing:
        actual_trip_id = st.session_state.editing_actual_trip_id

        run_query("""
            UPDATE actual_trip SET observation_date = %s, weather_condition = %s
            WHERE actual_trip_id = %s
        """, params=(observation_date, weather_val, actual_trip_id))

        run_query("DELETE FROM actual_stop_event WHERE actual_trip_id = %s",
                 params=(actual_trip_id,))

        for idx, event in enumerate(st.session_state.stop_events, start=1):
            run_query("""
                INSERT INTO actual_stop_event
                (actual_trip_id, stop_id, sequence_number, actual_arrival_time,
                 actual_departure_time, event_type, crowding_level, vehicle_number)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, params=(
                actual_trip_id, event['stop_id'], idx,
                event['actual_arrival_time'], event['actual_departure_time'],
                event['event_type'], event['crowding_level'], event['vehicle_number']
            ))

        st.success(f"Trip {actual_trip_id} updated successfully!")
    else:
        result = run_query("""
            INSERT INTO actual_trip (trip_id, observation_date, weather_condition)
            VALUES (%s, %s, %s) RETURNING actual_trip_id
        """, params=(trip_id, observation_date, weather_val))

        if not result.empty:
            actual_trip_id = int(result.iloc[0]['actual_trip_id'])

            for idx, event in enumerate(st.session_state.stop_events, start=1):
                run_query("""
                    INSERT INTO actual_stop_event
                    (actual_trip_id, stop_id, sequence_number, actual_arrival_time,
                     actual_departure_time, event_type, crowding_level, vehicle_number)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, params=(
                    actual_trip_id, event['stop_id'], idx,
                    event['actual_arrival_time'], event['actual_departure_time'],
                    event['event_type'], event['crowding_level'], event['vehicle_number']
                ))

            st.success(f"Trip recorded successfully! Actual Trip ID: {actual_trip_id}")
        else:
            st.error("Failed to save trip")
            return

    _clear_form_state()
    st.rerun()


def _clear_form_state():
    """Clear form session state."""
    st.session_state.show_record_form = False
    st.session_state.editing_actual_trip_id = None
    if 'stop_events' in st.session_state:
        st.session_state.stop_events = []


def _render_trips_table():
    """Render the actual trips table view."""
    # Header with Record Trip button
    col1, col2 = st.columns([5, 1])
    with col1:
        st.header("Actual Trips")
    with col2:
        if st.button("Record Trip", type="secondary", use_container_width=True, key="record_trip_top"):
            st.session_state.show_record_form = True
            st.session_state.editing_actual_trip_id = None
            st.rerun()

    st.warning("**MOCKUP DATA** - The data shown below is sample data.")

    # Filters
    st.subheader("Filters")
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
        st.subheader("Actual Stop Events (0 found)")
        st.info("No actual trips recorded yet. Click 'Record Trip' to add your first trip.")


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
        col1, col2 = st.columns([5, 1])
        with col1:
            st.subheader(f"Actual Stop Events ({len(events_df)} found)")
        with col2:
            if selected_trip_id:
                trip_info = actual_trips.iloc[trip_sel - 1]
                label = f"Edit Trip {selected_trip_id}: {trip_info['route_short_name']} - {trip_info['trip_headsign']}"
                if st.button(label, type="secondary", use_container_width=True):
                    st.session_state.show_record_form = True
                    st.session_state.editing_actual_trip_id = selected_trip_id
                    st.rerun()

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
        st.subheader("Actual Stop Events (0 found)")
        st.info("No stop events found for the selected filters.")
