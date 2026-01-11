import pandas as pd
import streamlit as st
import os
import re
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

DATA_SOURCE = os.getenv('DATA_SOURCE', 'database').lower()


def _postgres_to_sqlite(query):
    """Convert PostgreSQL-specific SQL to SQLite."""
    # Convert EXTRACT(EPOCH FROM (time2 - time1))/60 to SQLite
    # Use placeholder to avoid %s replacement issue
    pattern = r"EXTRACT\s*\(\s*EPOCH\s+FROM\s*\(([^)]+)\s*-\s*([^)]+)\)\s*\)\s*/\s*60"

    def replace_extract(match):
        time1 = match.group(1).strip()
        time2 = match.group(2).strip()
        # Use __PCT__s as placeholder, will be converted back after %s replacement
        return f"(strftime('__PCT__s', {time1}) - strftime('__PCT__s', {time2})) / 60.0"

    query = re.sub(pattern, replace_extract, query, flags=re.IGNORECASE)

    # Convert INTERVAL syntax if present
    query = re.sub(r"INTERVAL\s+'(\d+)\s+days?'", r"'\1 days'", query, flags=re.IGNORECASE)
    query = re.sub(r"CURRENT_DATE\s*-\s*INTERVAL\s*'(\d+)\s+days?'",
                   r"date('now', '-\1 days')", query, flags=re.IGNORECASE)

    return query

# PostgreSQL connection (only used if DATA_SOURCE=database)
if DATA_SOURCE == 'database':
    import psycopg2

    DB_CONFIG = {
        'dbname': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'host': os.getenv('DB_HOST')
    }

    @st.cache_resource
    def get_connection():
        """Create and cache database connection."""
        try:
            cn = psycopg2.connect(**DB_CONFIG)
            return cn
        except psycopg2.Error as e:
            st.error(f"Database connection error: {e}")
            return None

# SQLite connection for CSV mode
else:
    import sqlite3

    @st.cache_resource
    def get_connection():
        """Create in-memory SQLite database from CSV files."""
        try:
            cn = sqlite3.connect(':memory:', check_same_thread=False)
            _load_csvs_to_sqlite(cn)
            return cn
        except Exception as e:
            st.error(f"CSV loading error: {e}")
            return None

    def _load_csvs_to_sqlite(cn):
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
            'shapes.txt': 'shape',
            'fare_attributes.txt': 'fare_type',
            'fare_rules.txt': 'fare_rule',
            'actual_trip_mockup.txt': 'actual_trip',
            'actual_stop_event_mockup.txt': 'actual_stop_event',
        }

        for filename, table_name in file_table_map.items():
            filepath = data_dir / filename
            if filepath.exists():
                df = pd.read_csv(filepath)
                # Add missing columns for actual_trip table (auto-generated in database)
                if table_name == 'actual_trip':
                    if 'actual_trip_id' not in df.columns:
                        df.insert(0, 'actual_trip_id', range(1, len(df) + 1))
                    if 'created_at' not in df.columns:
                        df['created_at'] = pd.Timestamp.now().isoformat()
                # Convert YYYYMMDD integer dates to YYYY-MM-DD strings
                for col in ['start_date', 'end_date', 'date']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], format='%Y%m%d').dt.strftime('%Y-%m-%d')
                df.to_sql(table_name, cn, if_exists='replace', index=False)


def run_query(query, params=None):
    """Execute a SQL query and return results as a pandas DataFrame."""
    cn = get_connection()
    if cn is None:
        return pd.DataFrame()

    try:
        if DATA_SOURCE == 'csv':
            # Convert PostgreSQL syntax to SQLite
            query = _postgres_to_sqlite(query)
            # Restore strftime placeholders before parameter handling
            query = query.replace('__PCT__s', '__STRFTIME_S__')

            # Handle parameters and expand IN clauses
            if params:
                from datetime import date, datetime
                new_params = []
                new_query_parts = []
                param_index = 0
                params_list = list(params) if isinstance(params, tuple) else [params]

                # Split query by %s and rebuild with proper placeholders
                parts = query.split('%s')
                for i, part in enumerate(parts[:-1]):
                    new_query_parts.append(part)
                    if param_index < len(params_list):
                        p = params_list[param_index]
                        if isinstance(p, (list, tuple)):
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
                query = ''.join(new_query_parts)
                params = tuple(new_params)
            else:
                query = query.replace('%s', '?')

            # Restore strftime %s
            query = query.replace('__STRFTIME_S__', '%s')
            df = pd.read_sql_query(query, cn, params=params)
            return df
        else:
            # PostgreSQL mode
            query_upper = query.strip().upper()
            if query_upper.startswith('SELECT') or query_upper.startswith('WITH'):
                df = pd.read_sql_query(query, cn, params=params)
                return df
            else:
                cursor = cn.cursor()
                cursor.execute(query, params)
                if cursor.description is not None:
                    columns = [desc[0] for desc in cursor.description]
                    results = cursor.fetchall()
                    df = pd.DataFrame(results, columns=columns)
                else:
                    df = pd.DataFrame()
                cn.commit()
                cursor.close()
                return df
    except Exception as e:
        if DATA_SOURCE == 'database':
            cn.rollback()
        st.error(f"Query error: {e}")
        return pd.DataFrame()


def test_connection():
    """Test connection and return success status."""
    cn = get_connection()
    if cn is None:
        return False

    try:
        cursor = cn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        return True
    except:
        return False
