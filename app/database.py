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
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT')
}

@st.cache_resource
def get_connection():
    """Create and cache database connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        st.error(f"Database connection error: {e}")
        return None

def run_query(query, params=None):
    """Execute a SQL query and return results as a pandas DataFrame."""
    conn = get_connection()
    if conn is None:
        return pd.DataFrame()

    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Query error: {e}")
        return pd.DataFrame()

def test_connection():
    """Test database connection and return success status."""
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
