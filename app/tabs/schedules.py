"""Schedules tab - browse scheduled trips and stop times."""

import streamlit as st
from datetime import date

from database import run_query, test_connection
from constants import ROUTE_TYPES, DOW_COLUMNS
from utils import get_routes


def render():
    """Render the Schedules tab."""
    st.header("Schedules", anchor=False)

    if not test_connection():
        st.error("Database connection failed. Please check your configuration.")
        st.stop()

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

    st.subheader(f"Trips ({len(trips_df)} found)", anchor=False)

    trips_df['display'] = trips_df.apply(
        lambda row: f"{row['start_time']} - {row['trip_headsign']} ({'Outbound' if row['direction_id'] == 0 else 'Inbound'})",
        axis=1
    )

    trip_idx = st.selectbox("Select a trip to view stop times", range(len(trips_df)),
                            format_func=lambda x: trips_df.iloc[x]['display'])
    trip_id = int(trips_df.iloc[trip_idx]['trip_id'])

    st.subheader("Stop Times", anchor=False)

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

        st.subheader("Route Map", anchor=False)
        map_df = stop_times_df[['stop_lat', 'stop_lon']].rename(
            columns={'stop_lat': 'lat', 'stop_lon': 'lon'}
        )
        st.map(map_df)
    else:
        st.warning("No stop times found for this trip")
