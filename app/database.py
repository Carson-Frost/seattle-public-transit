"""Database module - loads GTFS CSV data into in-memory SQLite."""

import sqlite3
import pandas as pd
import streamlit as st
from pathlib import Path


@st.cache_resource
def get_connection():
    """Create in-memory SQLite database from CSV files."""
    try:
        conn = sqlite3.connect(':memory:', check_same_thread=False)
        _load_csvs_to_sqlite(conn)
        return conn
    except Exception as e:
        st.error(f"Data loading error: {e}")
        return None


def _load_csvs_to_sqlite(conn):
    """Load GTFS CSV files into SQLite database."""
    data_dir = Path(__file__).parent.parent / 'data'

    # GTFS file to table mapping
    file_table_map = {
        'agency.txt': 'agency',
        'routes.txt': 'route',
        'stops.txt': 'stop',
        'trips.txt': 'trip',
        'stop_times.txt': 'stop_time',
        'calendar.txt': 'service_calendar',
        'calendar_dates.txt': 'calendar_exception',
        'actual_trip_mockup.txt': 'actual_trip',
        'actual_stop_event_mockup.txt': 'actual_stop_event',
    }

    for filename, table_name in file_table_map.items():
        filepath = data_dir / filename
        if filepath.exists():
            df = pd.read_csv(filepath)
            # Add auto-generated columns for actual_trip table
            if table_name == 'actual_trip':
                if 'actual_trip_id' not in df.columns:
                    df.insert(0, 'actual_trip_id', range(1, len(df) + 1))
                if 'created_at' not in df.columns:
                    df['created_at'] = pd.Timestamp.now().isoformat()
            # Convert YYYYMMDD integer dates to YYYY-MM-DD strings
            for col in ['start_date', 'end_date', 'date']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], format='%Y%m%d').dt.strftime('%Y-%m-%d')
            df.to_sql(table_name, conn, if_exists='replace', index=False)


def _convert_query(query):
    """Convert PostgreSQL-specific SQL syntax to SQLite."""
    import re

    # Convert EXTRACT(EPOCH FROM (time2 - time1))/60 to SQLite
    # Use placeholder to protect %s from parameter conversion
    pattern = r"EXTRACT\s*\(\s*EPOCH\s+FROM\s*\(([^)]+)\s*-\s*([^)]+)\)\s*\)\s*/\s*60"

    def replace_extract(match):
        time1 = match.group(1).strip()
        time2 = match.group(2).strip()
        return f"(strftime('__EPOCH__', {time1}) - strftime('__EPOCH__', {time2})) / 60.0"

    query = re.sub(pattern, replace_extract, query, flags=re.IGNORECASE)

    # Convert INTERVAL syntax
    query = re.sub(r"CURRENT_DATE\s*-\s*INTERVAL\s*'(\d+)\s+days?'",
                   r"date('now', '-\1 days')", query, flags=re.IGNORECASE)

    return query


def _convert_params(query, params):
    """Convert query placeholders and parameters for SQLite."""
    from datetime import date, datetime

    if not params:
        query = query.replace('%s', '?')
        query = query.replace('__EPOCH__', '%s')
        return query, None

    new_params = []
    new_query_parts = []
    params_list = list(params) if isinstance(params, tuple) else [params]

    # Split query by %s and rebuild with proper placeholders
    parts = query.split('%s')
    param_index = 0

    for i, part in enumerate(parts[:-1]):
        new_query_parts.append(part)
        if param_index < len(params_list):
            p = params_list[param_index]
            if isinstance(p, (list, tuple)):
                if len(p) == 0:
                    # Empty list - use impossible condition
                    new_query_parts.append('(NULL)')
                else:
                    # Expand IN clause: IN %s -> IN (?, ?, ...)
                    placeholders = ', '.join(['?'] * len(p))
                    new_query_parts.append(f'({placeholders})')
                    for item in p:
                        if isinstance(item, (date, datetime)):
                            new_params.append(item.strftime('%Y-%m-%d'))
                        else:
                            new_params.append(item)
            else:
                new_query_parts.append('?')
                if isinstance(p, (date, datetime)):
                    new_params.append(p.strftime('%Y-%m-%d'))
                else:
                    new_params.append(p)
            param_index += 1

    new_query_parts.append(parts[-1])
    result = ''.join(new_query_parts)
    # Restore strftime %s
    result = result.replace('__EPOCH__', '%s')
    return result, tuple(new_params) if new_params else None


def run_query(query, params=None):
    """Execute a SQL query and return results as a pandas DataFrame."""
    conn = get_connection()
    if conn is None:
        return pd.DataFrame()

    try:
        query = _convert_query(query)
        query, params = _convert_params(query, params)
        return pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        st.error(f"Query error: {e}")
        return pd.DataFrame()


def test_connection():
    """Test connection and return success status."""
    conn = get_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        return True
    except:
        return False
