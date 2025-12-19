"""
Load mockup actual trip data into PostgreSQL database.
This script loads sample actual_trip and actual_stop_event data for demonstration.
"""

import psycopg2
import csv
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST')
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


def clear_existing_data(cursor):
    """Clear existing actual trip data before loading mockup data"""
    print("Clearing existing actual trip data...")
    cursor.execute("DELETE FROM actual_stop_event")
    cursor.execute("DELETE FROM actual_trip")
    # Reset the sequence for actual_trip_id
    cursor.execute("ALTER SEQUENCE actual_trip_actual_trip_id_seq RESTART WITH 1")
    print("  Existing data cleared")


def load_actual_trips(cursor):
    """Load actual trip records from mockup file"""
    filepath = os.path.join(DATA_DIR, 'actual_trip_mockup.txt')
    print("Loading actual_trip_mockup.txt...")

    trip_id_mapping = {}  # Maps CSV row order to database actual_trip_id
    count = 0

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                """INSERT INTO actual_trip (trip_id, observation_date, weather_condition)
                   VALUES (%s, %s, %s)
                   RETURNING actual_trip_id""",
                (row['trip_id'], row['observation_date'],
                 row['weather_condition'] if row['weather_condition'] else None)
            )
            # Get the auto-generated actual_trip_id
            actual_trip_id = cursor.fetchone()[0]
            # Map CSV row number to database ID (count+1 because we start at 1)
            trip_id_mapping[count + 1] = actual_trip_id
            count += 1

    print(f"  Loaded {count} actual trips")
    return trip_id_mapping


def load_actual_stop_events(cursor, trip_id_mapping):
    """Load actual stop event records from mockup file"""
    filepath = os.path.join(DATA_DIR, 'actual_stop_event_mockup.txt')
    print("Loading actual_stop_event_mockup.txt...")

    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Map the CSV actual_trip_id to the real database actual_trip_id
            csv_trip_id = int(row['actual_trip_id'])
            db_trip_id = trip_id_mapping.get(csv_trip_id)

            if db_trip_id is None:
                print(f"  Warning: Skipping event with invalid actual_trip_id: {csv_trip_id}")
                continue

            cursor.execute(
                """INSERT INTO actual_stop_event
                   (actual_trip_id, stop_id, sequence_number, actual_arrival_time,
                    actual_departure_time, event_type, crowding_level, vehicle_number)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (db_trip_id, row['stop_id'], row['sequence_number'],
                 row['actual_arrival_time'], row['actual_departure_time'],
                 row['event_type'],
                 row['crowding_level'] if row['crowding_level'] else None,
                 row['vehicle_number'] if row['vehicle_number'] else None)
            )
            count += 1

    print(f"  Loaded {count} actual stop events")


def main():
    cn = None
    cursor = None

    try:
        print("="*60)
        print("Actual Trip Mockup Data Loading")
        print("="*60)
        print("Loading sample data for demonstration purposes\n")

        print("Connecting to database...")
        cn = psycopg2.connect(**DB_CONFIG)
        cursor = cn.cursor()
        print("Connected.\n")

        # Clear existing data
        clear_existing_data(cursor)

        # Load mockup data
        trip_id_mapping = load_actual_trips(cursor)
        load_actual_stop_events(cursor, trip_id_mapping)

        cn.commit()
        print("\n" + "="*60)
        print("Mockup data loading complete!")
        print("="*60)

        print("\nDatabase Summary:")
        cursor.execute("SELECT COUNT(*) FROM actual_trip")
        print(f"  Actual Trips: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM actual_stop_event")
        print(f"  Actual Stop Events: {cursor.fetchone()[0]}")

        cursor.execute("""
            SELECT
                r.route_short_name,
                COUNT(DISTINCT at.actual_trip_id) as trip_count
            FROM actual_trip at
            JOIN trip t ON at.trip_id = t.trip_id
            JOIN route r ON t.route_id = r.route_id
            GROUP BY r.route_short_name
            ORDER BY trip_count DESC
        """)
        print("\n  Trips by Route:")
        for row in cursor.fetchall():
            print(f"    Route {row[0]}: {row[1]} trips")

        cursor.execute("""
            SELECT weather_condition, COUNT(*) as count
            FROM actual_trip
            WHERE weather_condition IS NOT NULL
            GROUP BY weather_condition
            ORDER BY count DESC
        """)
        print("\n  Weather Conditions:")
        for row in cursor.fetchall():
            print(f"    {row[0]}: {row[1]} trips")

        cursor.execute("""
            SELECT
                MIN(observation_date) as earliest,
                MAX(observation_date) as latest
            FROM actual_trip
        """)
        date_range = cursor.fetchone()
        print(f"\n  Date Range: {date_range[0]} to {date_range[1]}")

        print("\n⚠️  Note: This is MOCKUP DATA for demonstration purposes only.")
        print("    Use the 'Record Trip' feature to add real observations.")

    except psycopg2.Error as e:
        print(f"\nDatabase error: {e}")
        if cn:
            cn.rollback()
    except FileNotFoundError as e:
        print(f"\nFile not found: {e}")
        print("Make sure actual_trip_mockup.txt and actual_stop_event_mockup.txt")
        print("exist in the data/ directory.")
    except Exception as e:
        print(f"\nError: {e}")
        if cn:
            cn.rollback()
    finally:
        if cursor:
            cursor.close()
        if cn:
            cn.close()


if __name__ == '__main__':
    main()
