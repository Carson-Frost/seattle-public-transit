"""Shared utility functions for Seattle Transit app."""

import pandas as pd
from datetime import time as dt_time
from database import run_query


def sort_route_key(name):
    """Sort key for route names - numeric routes first, then alphabetic."""
    try:
        return (0, int(name))
    except (ValueError, TypeError):
        return (1, str(name))


def get_routes():
    """Fetch all routes sorted by route number.

    Returns:
        tuple: (DataFrame, list of option strings, default index)
    """
    df = run_query("""
        SELECT DISTINCT route_id, route_short_name, route_long_name, route_type
        FROM route
    """)

    if df.empty:
        return df, [], 0

    df['_sort'] = df['route_short_name'].apply(sort_route_key)
    df = df.sort_values('_sort').drop('_sort', axis=1).reset_index(drop=True)

    options = []
    for _, row in df.iterrows():
        name = row['route_long_name'] or ""
        if name:
            options.append(f"{row['route_short_name']}: {name}")
        else:
            options.append(str(row['route_short_name']))

    return df, options, 0


def get_trips(route_id, date, dow_column, start_time, end_time, direction=None):
    """Fetch trips for a route with optional direction filter.

    Args:
        route_id: Route ID to query
        date: Date object for service calendar lookup
        dow_column: Day of week column name (e.g., 'monday')
        start_time: Start time string (HH:MM:SS)
        end_time: End time string (HH:MM:SS)
        direction: Optional direction (0=outbound, 1=inbound, None=both)

    Returns:
        DataFrame with trip_id, trip_headsign, direction_id, start_time
    """
    query = f"""
        SELECT DISTINCT t.trip_id, t.trip_headsign, t.direction_id,
               MIN(st.departure_time) as start_time
        FROM trip t
        JOIN stop_time st ON t.trip_id = st.trip_id
        JOIN service_calendar sc ON t.service_id = sc.service_id
        LEFT JOIN calendar_exception ce ON t.service_id = ce.service_id AND ce.date = %s
        WHERE t.route_id = %s
          AND st.stop_sequence = 1
          AND %s BETWEEN sc.start_date AND sc.end_date
          AND (
            (sc.{dow_column} = 1 AND (ce.exception_type IS NULL OR ce.exception_type != 2))
            OR ce.exception_type = 1
          )
    """

    if direction is not None:
        query += " AND t.direction_id = %s"
        params = (date, route_id, date, direction, start_time, end_time)
    else:
        params = (date, route_id, date, start_time, end_time)

    query += """
        GROUP BY t.trip_id, t.trip_headsign, t.direction_id
        HAVING MIN(st.departure_time) >= %s AND MIN(st.departure_time) < %s
        ORDER BY start_time
    """

    return run_query(query, params)


def get_stop_times(trip_id):
    """Fetch stop times for a specific trip.

    Args:
        trip_id: Trip ID to query

    Returns:
        DataFrame with stop details and times
    """
    return run_query("""
        SELECT st.stop_id, s.stop_name, st.arrival_time, st.departure_time,
               st.stop_sequence, s.stop_lat, s.stop_lon
        FROM stop_time st
        JOIN stop s ON st.stop_id = s.stop_id
        WHERE st.trip_id = %s
        ORDER BY st.stop_sequence
    """, (trip_id,))


def get_stops_for_route(route_id):
    """Fetch all unique stops served by a route.

    Args:
        route_id: Route ID to query

    Returns:
        DataFrame with stop_id and stop_name
    """
    return run_query("""
        SELECT DISTINCT s.stop_id, s.stop_name
        FROM stop s
        JOIN stop_time st ON s.stop_id = st.stop_id
        JOIN trip t ON st.trip_id = t.trip_id
        WHERE t.route_id = %s
        ORDER BY s.stop_name
    """, (route_id,))


def calc_delay_pct(df, column, threshold_low, threshold_high):
    """Calculate percentage of values within a threshold range.

    Args:
        df: DataFrame containing the column
        column: Column name to analyze
        threshold_low: Lower bound (inclusive)
        threshold_high: Upper bound (inclusive)

    Returns:
        float: Percentage of values in range
    """
    if df.empty:
        return 0.0
    count = len(df[df[column].between(threshold_low, threshold_high)])
    return (count / len(df)) * 100


def format_time_12h(time_str):
    """Convert HH:MM:SS to 12-hour format.

    Args:
        time_str: Time string in HH:MM:SS format

    Returns:
        str: Time in 12-hour format (e.g., "8:30 AM")
    """
    if not time_str or pd.isna(time_str):
        return ""
    parts = str(time_str).split(":")
    if len(parts) < 2:
        return time_str
    hour = int(parts[0])
    minute = parts[1]
    period = "AM" if hour < 12 else "PM"
    if hour == 0:
        hour = 12
    elif hour > 12:
        hour -= 12
    return f"{hour}:{minute} {period}"


def normalize_time(t):
    """Normalize time input to HH:MM:SS format.

    Args:
        t: Time value (datetime.time object or string)

    Returns:
        str: Time in HH:MM:SS format, or None if input is None
    """
    if t is None:
        return None

    if isinstance(t, dt_time):
        return t.strftime("%H:%M:%S")

    t = str(t).strip()
    if len(t) == 5:  # HH:MM → HH:MM:SS
        return f"{t}:00"

    return t
