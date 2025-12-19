import psycopg2
import pandas as pd
import streamlit as st
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection parameters
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

def run_query(query, params=None):
    """Execute a SQL query and return results as a pandas DataFrame."""
    cn = get_connection()
    if cn is None:
        return pd.DataFrame()

    try:
        # Check if it's a SELECT query (returns data) or a modification query (INSERT/UPDATE/DELETE)
        query_upper = query.strip().upper()
        if query_upper.startswith('SELECT') or query_upper.startswith('WITH'):
            # SELECT query - use pandas to read results
            df = pd.read_sql_query(query, cn, params=params)
            return df
        else:
            # INSERT/UPDATE/DELETE query - execute and commit
            cursor = cn.cursor()
            cursor.execute(query, params)

            # Check if there are results to fetch (e.g., RETURNING clause)
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
        cn.rollback()
        st.error(f"Query error: {e}")
        return pd.DataFrame()

def test_connection():
    """Test database connection and return success status."""
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
