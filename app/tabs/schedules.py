"""Schedules tab - browse and manage scheduled trips."""

import re
import streamlit as st
import pandas as pd
from datetime import date

from database import run_query, test_connection
from constants import ROUTE_TYPES, DOW_COLUMNS
from utils import sort_route_key, get_routes, normalize_time


def render():
    """Render the Schedules tab."""
    st.header("Schedules")

    if not test_connection():
        st.error("Database connection failed. Please check your configuration.")
        st.stop()

    # Initialize session state
    if 'show_trip_form' not in st.session_state:
        st.session_state.show_trip_form = False
    if 'editing_trip_id' not in st.session_state:
        st.session_state.editing_trip_id = None

    if st.session_state.show_trip_form:
        _render_trip_form()
    else:
        _render_schedule_browser()


def _render_trip_form():
    """Render the add/edit trip form."""
    editing = st.session_state.editing_trip_id is not None

    # Load existing data if editing
    if editing:
        trip = run_query("""
            SELECT t.trip_id, t.route_id, t.service_id, t.trip_headsign,
                   t.direction_id, t.wheelchair_accessible
            FROM trip t WHERE t.trip_id = %s
        """, params=(st.session_state.editing_trip_id,))

        stop_times = run_query("""
            SELECT st.stop_id, st.stop_sequence, st.arrival_time, st.departure_time, s.stop_name
            FROM stop_time st
            JOIN stop s ON st.stop_id = s.stop_id
            WHERE st.trip_id = %s
            ORDER BY st.stop_sequence
        """, params=(st.session_state.editing_trip_id,))

    # Header with back and delete buttons
    if editing:
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("Back to Schedules", type="secondary"):
                _clear_form_state()
                st.rerun()
        with col2:
            if st.button("Delete Trip", type="secondary", use_container_width=True):
                run_query("DELETE FROM stop_time WHERE trip_id = %s",
                         params=(st.session_state.editing_trip_id,))
                run_query("DELETE FROM trip WHERE trip_id = %s",
                         params=(st.session_state.editing_trip_id,))
                st.success(f"Trip {st.session_state.editing_trip_id} deleted!")
                _clear_form_state()
                st.rerun()
    else:
        if st.button("Back to Schedules", type="secondary"):
            _clear_form_state()
            st.rerun()

    st.divider()
    st.subheader("Edit Scheduled Trip" if editing else "Add Scheduled Trip")

    # Pre-fill defaults if editing
    defaults = {}
    if editing and not trip.empty:
        row = trip.iloc[0]
        defaults = {
            'route_id': int(row['route_id']),
            'service_id': int(row['service_id']),
            'headsign': row['trip_headsign'],
            'direction': int(row['direction_id']) if pd.notna(row['direction_id']) else 0,
            'wheelchair': int(row['wheelchair_accessible']) if pd.notna(row['wheelchair_accessible']) else 0
        }

        # Load existing stop times into session state
        if 'stop_times' not in st.session_state or not st.session_state.stop_times:
            st.session_state.stop_times = [
                {
                    'stop_id': int(st_row['stop_id']),
                    'stop_name': st_row['stop_name'],
                    'arrival_time': str(st_row['arrival_time']),
                    'departure_time': str(st_row['departure_time'])
                }
                for _, st_row in stop_times.iterrows()
            ]

    # Trip details form
    col1, col2, col3 = st.columns(3)

    with col1:
        routes_df, route_options, _ = get_routes()
        if routes_df.empty:
            st.warning("No routes found")
            st.stop()

        default_idx = 0
        if 'route_id' in defaults:
            for i, row in routes_df.iterrows():
                if int(row['route_id']) == defaults['route_id']:
                    default_idx = i
                    break

        route_idx = st.selectbox("Route", range(len(route_options)),
                                 format_func=lambda x: route_options[x],
                                 index=default_idx, key="trip_route")
        route_id = int(routes_df.iloc[route_idx]['route_id'])

    with col2:
        services_df = run_query("""
            SELECT service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday
            FROM service_calendar ORDER BY service_id
        """)

        if not services_df.empty:
            service_options = []
            for _, row in services_df.iterrows():
                days = [d[:3].title() for d in DOW_COLUMNS if row[d]]
                label = f"Service {row['service_id']}"
                if days:
                    label += f": {', '.join(days)}"
                service_options.append(label)

            default_idx = 0
            if 'service_id' in defaults:
                for i, row in services_df.iterrows():
                    if int(row['service_id']) == defaults['service_id']:
                        default_idx = i
                        break

            service_idx = st.selectbox("Service Calendar", range(len(service_options)),
                                       format_func=lambda x: service_options[x],
                                       index=default_idx, key="trip_service")
            service_id = int(services_df.iloc[service_idx]['service_id'])

    with col3:
        direction = st.selectbox("Direction", ["Outbound", "Inbound"],
                                 index=defaults.get('direction', 0), key="trip_direction")
        direction_id = 0 if direction == "Outbound" else 1

    col1, col2, _ = st.columns(3)

    with col1:
        headsign = st.text_input("Trip Headsign", value=defaults.get('headsign', ''),
                                 key="trip_headsign")

    with col2:
        wheelchair_opts = ["Unknown", "Accessible", "Not Accessible"]
        wheelchair = st.selectbox("Wheelchair Accessible", wheelchair_opts,
                                  index=defaults.get('wheelchair', 0), key="trip_wheelchair")
        wheelchair_id = wheelchair_opts.index(wheelchair)

    st.divider()
    st.subheader("Stop Times")

    # Get stops for this route
    route_stops = run_query("""
        SELECT DISTINCT s.stop_id, s.stop_name
        FROM stop s
        JOIN stop_time st ON s.stop_id = st.stop_id
        JOIN trip t ON st.trip_id = t.trip_id
        WHERE t.route_id = %s
        ORDER BY s.stop_name
    """, params=(route_id,))

    # Get other stops
    if not route_stops.empty:
        route_stop_ids = tuple(route_stops['stop_id'].tolist())
        if len(route_stop_ids) == 1:
            other_stops = run_query("""
                SELECT stop_id, stop_name FROM stop
                WHERE stop_id != %s ORDER BY stop_name
            """, params=(route_stop_ids[0],))
        else:
            other_stops = run_query("""
                SELECT stop_id, stop_name FROM stop
                WHERE stop_id NOT IN %s ORDER BY stop_name
            """, params=(route_stop_ids,))
    else:
        other_stops = run_query("SELECT stop_id, stop_name FROM stop ORDER BY stop_name")

    if 'stop_times' not in st.session_state:
        st.session_state.stop_times = []

    # Add stop form
    with st.form("add_stop_time"):
        st.write("Add a stop:")
        col1, col2, col3 = st.columns(3)

        with col1:
            stop_options = [""]
            stop_data = []

            for _, row in route_stops.iterrows():
                stop_options.append(f"{row['stop_name']} (used in route)")
                stop_data.append({'stop_id': row['stop_id'], 'stop_name': row['stop_name']})

            for _, row in other_stops.iterrows():
                stop_options.append(row['stop_name'])
                stop_data.append({'stop_id': row['stop_id'], 'stop_name': row['stop_name']})

            stop_sel = st.selectbox("Stop", range(len(stop_options)),
                                    format_func=lambda x: stop_options[x] if stop_options[x] else "Select a stop...",
                                    index=0, key="scheduled_stop")
            stop_idx = stop_sel - 1 if stop_sel > 0 else None

        with col2:
            arrival = st.text_input("Arrival time (HH:MM)", placeholder="08:00", key="scheduled_arrival")

        with col3:
            departure = st.text_input("Departure time (HH:MM)", placeholder="08:01", key="scheduled_departure")

        if st.form_submit_button("Add Stop"):
            time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

            if stop_idx is None:
                st.error("Please select a stop")
            elif not arrival or not time_pattern.match(arrival):
                st.error("Please enter arrival time in HH:MM format")
            elif not departure or not time_pattern.match(departure):
                st.error("Please enter departure time in HH:MM format")
            else:
                stop = stop_data[stop_idx]
                st.session_state.stop_times.append({
                    'stop_id': int(stop['stop_id']),
                    'stop_name': stop['stop_name'],
                    'arrival_time': normalize_time(arrival),
                    'departure_time': normalize_time(departure)
                })
                st.success(f"Added stop: {stop['stop_name']}")
                st.rerun()

    # Display added stops
    if st.session_state.stop_times:
        st.write(f"Stops added ({len(st.session_state.stop_times)}):")

        for idx, stop in enumerate(st.session_state.stop_times):
            with st.container():
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"**Stop {idx + 1}: {stop['stop_name']}**")
                with col2:
                    if st.button("Delete", key=f"delete_stop_{idx}", type="secondary", use_container_width=True):
                        st.session_state.stop_times.pop(idx)
                        st.rerun()

                col1, col2 = st.columns(2)
                with col1:
                    new_arrival = st.text_input("Arrival time (HH:MM)",
                                               value=stop['arrival_time'][:5],
                                               key=f"stop_arrival_{idx}")
                    stop['arrival_time'] = normalize_time(new_arrival)
                with col2:
                    new_departure = st.text_input("Departure time (HH:MM)",
                                                 value=stop['departure_time'][:5],
                                                 key=f"stop_departure_{idx}")
                    stop['departure_time'] = normalize_time(new_departure)

                st.divider()

        # Save button
        col1, col2 = st.columns([5, 1])
        with col2:
            label = "Update Trip" if editing else "Save Trip"
            if st.button(label, type="secondary", use_container_width=True):
                _save_trip(editing, route_id, service_id, headsign, direction_id, wheelchair_id)
    else:
        st.info("No stops added yet. Add stops above to create the trip.")


def _save_trip(editing, route_id, service_id, headsign, direction_id, wheelchair_id):
    """Save or update a trip."""
    if editing:
        trip_id = st.session_state.editing_trip_id

        run_query("""
            UPDATE trip SET route_id = %s, service_id = %s, trip_headsign = %s,
                   direction_id = %s, wheelchair_accessible = %s
            WHERE trip_id = %s
        """, params=(route_id, service_id, headsign, direction_id, wheelchair_id, trip_id))

        run_query("DELETE FROM stop_time WHERE trip_id = %s", params=(trip_id,))

        for idx, stop in enumerate(st.session_state.stop_times, start=1):
            run_query("""
                INSERT INTO stop_time (trip_id, stop_id, stop_sequence, arrival_time, departure_time)
                VALUES (%s, %s, %s, %s, %s)
            """, params=(trip_id, stop['stop_id'], idx, stop['arrival_time'], stop['departure_time']))

        st.success(f"Trip {trip_id} updated!")
    else:
        max_trip = run_query("SELECT MAX(trip_id) as max_id FROM trip")
        trip_id = int(max_trip.iloc[0]['max_id']) + 1 if not max_trip.empty and pd.notna(max_trip.iloc[0]['max_id']) else 1

        run_query("""
            INSERT INTO trip (trip_id, route_id, service_id, trip_headsign, direction_id, wheelchair_accessible)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, params=(trip_id, route_id, service_id, headsign, direction_id, wheelchair_id))

        for idx, stop in enumerate(st.session_state.stop_times, start=1):
            run_query("""
                INSERT INTO stop_time (trip_id, stop_id, stop_sequence, arrival_time, departure_time)
                VALUES (%s, %s, %s, %s, %s)
            """, params=(trip_id, stop['stop_id'], idx, stop['arrival_time'], stop['departure_time']))

        st.success(f"Trip {trip_id} created successfully!")

    _clear_form_state()
    st.rerun()


def _clear_form_state():
    """Clear form session state."""
    st.session_state.show_trip_form = False
    st.session_state.editing_trip_id = None
    if 'stop_times' in st.session_state:
        st.session_state.stop_times = []


def _render_schedule_browser():
    """Render the schedule browsing view."""
    st.write("Browse scheduled trips and stop times")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        routes_df, route_options, _ = get_routes()
        if routes_df.empty:
            st.warning("No routes found in database")
            st.stop()

        route_idx = st.selectbox("Route", range(len(route_options)),
                                 format_func=lambda x: route_options[x])
        route_id = int(routes_df.iloc[route_idx]['route_id'])
        route_type = int(routes_df.iloc[route_idx]['route_type'])
        route_short = routes_df.iloc[route_idx]['route_short_name']
        route_long = routes_df.iloc[route_idx]['route_long_name'] or ""

    with col2:
        direction = st.selectbox("Direction", ["Outbound & Inbound", "Outbound", "Inbound"])
        direction_filter = None if direction == "Outbound & Inbound" else (0 if direction == "Outbound" else 1)

    with col3:
        selected_date = st.date_input("Date", value=date(2025, 12, 12), key="schedules_date")

    with col4:
        time_opts = [
            ("07:00 AM", "07:00"), ("07:15 AM", "07:15"), ("07:30 AM", "07:30"), ("07:45 AM", "07:45"),
            ("08:00 AM", "08:00"), ("08:15 AM", "08:15"), ("08:30 AM", "08:30"), ("08:45 AM", "08:45"),
            ("09:00 AM", "09:00")
        ]
        time_col1, time_col2 = st.columns(2)
        with time_col1:
            start_idx = st.selectbox("Start", range(len(time_opts)), index=0,
                                     format_func=lambda x: time_opts[x][0])
        with time_col2:
            end_idx = st.selectbox("End", range(len(time_opts)), index=8,
                                   format_func=lambda x: time_opts[x][0])

        start_time = f"{time_opts[start_idx][1]}:00"
        end_time = f"{time_opts[end_idx][1]}:00"

    # Query trips
    dow_column = DOW_COLUMNS[selected_date.weekday()]

    base_query = f"""
        SELECT DISTINCT t.trip_id, t.trip_headsign, t.direction_id,
               MIN(st.departure_time) as start_time
        FROM trip t
        JOIN stop_time st ON t.trip_id = st.trip_id
        JOIN service_calendar sc ON t.service_id = sc.service_id
        LEFT JOIN calendar_exception ce ON t.service_id = ce.service_id AND ce.date = %s
        WHERE t.route_id = %s AND st.stop_sequence = 1
          AND %s BETWEEN sc.start_date AND sc.end_date
          AND ((sc.{dow_column} AND (ce.exception_type IS NULL OR ce.exception_type != 2))
               OR ce.exception_type = 1)
    """

    if direction_filter is not None:
        base_query += " AND t.direction_id = %s"
        params = (selected_date, route_id, selected_date, direction_filter, start_time, end_time)
    else:
        params = (selected_date, route_id, selected_date, start_time, end_time)

    base_query += """
        GROUP BY t.trip_id, t.trip_headsign, t.direction_id
        HAVING MIN(st.departure_time) >= %s AND MIN(st.departure_time) < %s
        ORDER BY start_time
    """

    trips_df = run_query(base_query, params=params)

    if trips_df.empty:
        st.warning("No trips found for this route")
        st.stop()

    # Route info
    route_type_name = ROUTE_TYPES.get(route_type, "Transit")
    date_text = selected_date.strftime("%B %d (%Y)")
    st.info(f"**Route {route_short}: {route_long} ({route_type_name})**, {direction}, {date_text}, {time_opts[start_idx][0]} - {time_opts[end_idx][0]}")

    st.subheader(f"Trips ({len(trips_df)} found)")

    trips_df['display'] = trips_df.apply(
        lambda row: f"{row['start_time']} - {row['trip_headsign']} ({'Outbound' if row['direction_id'] == 0 else 'Inbound'})",
        axis=1
    )

    # Trip selection with edit/add buttons
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        trip_idx = st.selectbox("Select a trip to view stop times", range(len(trips_df)),
                                format_func=lambda x: trips_df.iloc[x]['display'])
        trip_id = int(trips_df.iloc[trip_idx]['trip_id'])
    with col2:
        if st.button("Edit Trip", type="secondary", use_container_width=True):
            st.session_state.show_trip_form = True
            st.session_state.editing_trip_id = trip_id
            st.rerun()
    with col3:
        if st.button("Add New Trip", type="secondary", use_container_width=True):
            st.session_state.show_trip_form = True
            st.session_state.editing_trip_id = None
            if 'stop_times' in st.session_state:
                st.session_state.stop_times = []
            st.rerun()

    st.subheader("Stop Times")

    stop_times_df = run_query("""
        SELECT st.stop_sequence, s.stop_name, st.arrival_time, st.departure_time,
               s.stop_lat, s.stop_lon
        FROM stop_time st
        JOIN stop s ON st.stop_id = s.stop_id
        WHERE st.trip_id = %s
        ORDER BY st.stop_sequence
    """, params=(trip_id,))

    if not stop_times_df.empty:
        display_df = stop_times_df[['stop_sequence', 'stop_name', 'arrival_time']].rename(
            columns={'stop_sequence': 'Stop Sequence', 'stop_name': 'Stop Name', 'arrival_time': 'Time'}
        )
        st.dataframe(display_df, hide_index=True,
                     column_config={"Stop Sequence": st.column_config.NumberColumn(width="small")})

        st.subheader("Route Map")
        map_df = stop_times_df[['stop_lat', 'stop_lon']].rename(
            columns={'stop_lat': 'lat', 'stop_lon': 'lon'}
        )
        st.map(map_df)
    else:
        st.warning("No stop times found for this trip")
