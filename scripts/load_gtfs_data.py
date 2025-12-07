import psycopg2
import csv
import os

# Database connection parameters
DB_CONFIG = {
    'dbname': 'seattle_transit',
    'user': 'postgres',
    'password': 'your_password',  # Update this
    'host': 'localhost',
    'port': 5432
}

# Path to GTFS data files
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

# Mapping of GTFS files to database tables
FILE_TABLE_MAPPING = {
    'agency.txt': 'agency',
    'routes.txt': 'route',
    'stops.txt': 'stop',
    'calendar.txt': 'service_calendar',
    'calendar_dates.txt': 'calendar_exception',
    'shapes.txt': 'shape',
    'fare_attributes.txt': 'fare_type',
    'trips.txt': 'trip',
    'stop_times.txt': 'stop_time',
    'fare_rules.txt': 'fare_rule'
}

def load_gtfs_file(cursor, filename, table_name):
    """Load a GTFS CSV file into the corresponding database table."""
    filepath = os.path.join(DATA_DIR, filename)

    if not os.path.exists(filepath):
        print(f"Warning: {filename} not found, skipping...")
        return

    print(f"Loading {filename} into {table_name}...")

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        if not rows:
            print(f"  No data found in {filename}")
            return

        # Get column names from CSV
        columns = rows[0].keys()

        # Create INSERT statement
        placeholders = ', '.join(['%s'] * len(columns))
        column_names = ', '.join(columns)
        insert_sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"

        # Insert rows
        for row in rows:
            values = [row[col] if row[col] != '' else None for col in columns]
            cursor.execute(insert_sql, values)

        print(f"  Loaded {len(rows)} rows into {table_name}")

def main():
    """Main function to load all GTFS data into PostgreSQL."""
    try:
        # Connect to database
        print("Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Load each GTFS file in order (respecting foreign key dependencies)
        load_order = [
            ('agency.txt', 'agency'),
            ('routes.txt', 'route'),
            ('stops.txt', 'stop'),
            ('calendar.txt', 'service_calendar'),
            ('calendar_dates.txt', 'calendar_exception'),
            ('shapes.txt', 'shape'),
            ('fare_attributes.txt', 'fare_type'),
            ('trips.txt', 'trip'),
            ('stop_times.txt', 'stop_time'),
            ('fare_rules.txt', 'fare_rule')
        ]

        for filename, table_name in load_order:
            load_gtfs_file(cursor, filename, table_name)

        # Commit changes
        conn.commit()
        print("\nData loading complete!")

        # Print summary statistics
        print("\nDatabase Summary:")
        cursor.execute("SELECT COUNT(*) FROM agency")
        print(f"  Agencies: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM route")
        print(f"  Routes: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM stop")
        print(f"  Stops: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM trip")
        print(f"  Trips: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM stop_time")
        print(f"  Stop Times: {cursor.fetchone()[0]}")

        cursor.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    main()
