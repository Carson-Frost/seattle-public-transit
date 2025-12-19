"""
Load GTFS data into PostgreSQL database.
Only loads essential attributes defined in the ER diagram.
Filters trips by date and time range to keep database size manageable.
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

# filter settings for trip loading
FILTER_START_DATE = '20251212'
FILTER_END_DATE = '20251212'
FILTER_START_TIME = '07:00:00'
FILTER_END_TIME = '09:00:00'


def load_agency(cursor):
    filepath = os.path.join(DATA_DIR, 'agency.txt')
    print("Loading agency.txt...")

    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                "INSERT INTO agency (agency_id, agency_name) VALUES (%s, %s)",
                (row['agency_id'], row['agency_name'])
            )
            count += 1

    print(f"  Loaded {count} agencies")


def load_routes(cursor):
    filepath = os.path.join(DATA_DIR, 'routes.txt')
    print("Loading routes.txt...")

    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # use route_desc for long_name since route_long_name is empty
            cursor.execute(
                """INSERT INTO route (route_id, agency_id, route_short_name,
                   route_long_name, route_type) VALUES (%s, %s, %s, %s, %s)""",
                (row['route_id'], row['agency_id'], row['route_short_name'] or None,
                 row['route_desc'] or None, row['route_type'])
            )
            count += 1

    print(f"  Loaded {count} routes")


def load_service_calendar(cursor):
    filepath = os.path.join(DATA_DIR, 'calendar.txt')
    print("Loading calendar.txt...")

    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                """INSERT INTO service_calendar
                   (service_id, monday, tuesday, wednesday, thursday, friday,
                    saturday, sunday, start_date, end_date)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (row['service_id'], row['monday'], row['tuesday'], row['wednesday'],
                 row['thursday'], row['friday'], row['saturday'], row['sunday'],
                 row['start_date'], row['end_date'])
            )
            count += 1

    print(f"  Loaded {count} service calendars")


def load_calendar_exceptions(cursor):
    filepath = os.path.join(DATA_DIR, 'calendar_dates.txt')
    print("Loading calendar_dates.txt...")

    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                """INSERT INTO calendar_exception (service_id, date, exception_type)
                   VALUES (%s, %s, %s)""",
                (row['service_id'], row['date'], row['exception_type'])
            )
            count += 1

    print(f"  Loaded {count} calendar exceptions")


def load_stops(cursor):
    filepath = os.path.join(DATA_DIR, 'stops.txt')
    print("Loading stops.txt...")

    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                """INSERT INTO stop (stop_id, stop_name, stop_lat, stop_lon,
                   location_type, parent_station, wheelchair_boarding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (row['stop_id'], row['stop_name'], row['stop_lat'], row['stop_lon'],
                 row['location_type'] or 0, row['parent_station'] or None,
                 row['wheelchair_boarding'] or 0)
            )
            count += 1

    print(f"  Loaded {count} stops")


def get_filtered_trip_ids(cursor):
    print("\nAnalyzing trips to filter...")

    cursor.execute(
        """SELECT service_id FROM service_calendar
           WHERE start_date <= %s AND end_date >= %s""",
        (FILTER_END_DATE, FILTER_START_DATE)
    )
    active_service_ids = set(row[0] for row in cursor.fetchall())

    trip_start_times = {}
    stop_times_path = os.path.join(DATA_DIR, 'stop_times.txt')
    with open(stop_times_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = int(row['trip_id'])
            stop_sequence = int(row['stop_sequence'])
            if stop_sequence == 1:
                trip_start_times[trip_id] = row['departure_time']

    filtered_trip_ids = set()
    trips_path = os.path.join(DATA_DIR, 'trips.txt')
    with open(trips_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = int(row['trip_id'])
            service_id = int(row['service_id'])

            if service_id in active_service_ids:
                start_time = trip_start_times.get(trip_id)
                if start_time and FILTER_START_TIME <= start_time <= FILTER_END_TIME:
                    filtered_trip_ids.add(trip_id)

    print(f"  Found {len(filtered_trip_ids)} trips matching filters")
    return filtered_trip_ids


def load_trips(cursor, filtered_trip_ids):
    filepath = os.path.join(DATA_DIR, 'trips.txt')
    print("Loading trips.txt...")

    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = int(row['trip_id'])
            if trip_id in filtered_trip_ids:
                cursor.execute(
                    """INSERT INTO trip (trip_id, route_id, service_id, trip_headsign,
                       direction_id, wheelchair_accessible)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (row['trip_id'], row['route_id'], row['service_id'],
                     row['trip_headsign'] or None, row['direction_id'] or None,
                     row['wheelchair_accessible'] or 0)
                )
                count += 1

    print(f"  Loaded {count} trips")


def load_stop_times(cursor, filtered_trip_ids):
    filepath = os.path.join(DATA_DIR, 'stop_times.txt')
    print("Loading stop_times.txt...")

    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = int(row['trip_id'])
            if trip_id in filtered_trip_ids:
                cursor.execute(
                    """INSERT INTO stop_time (trip_id, stop_id, stop_sequence,
                       arrival_time, departure_time)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (row['trip_id'], row['stop_id'], row['stop_sequence'],
                     row['arrival_time'], row['departure_time'])
                )
                count += 1

    print(f"  Loaded {count} stop times")


def main():
    cn = None
    cursor = None

    try:
        print("="*60)
        print("GTFS Data Loading - Seattle Public Transit")
        print("="*60)
        print(f"Filter: {FILTER_START_DATE} {FILTER_START_TIME} to {FILTER_END_TIME}\n")

        print("Connecting to database...")
        cn = psycopg2.connect(**DB_CONFIG)
        cursor = cn.cursor()
        print("Connected.\n")

        # load reference tables
        load_agency(cursor)
        load_routes(cursor)
        load_service_calendar(cursor)
        load_calendar_exceptions(cursor)
        load_stops(cursor)

        # filter and load trips
        filtered_trip_ids = get_filtered_trip_ids(cursor)
        load_trips(cursor, filtered_trip_ids)
        load_stop_times(cursor, filtered_trip_ids)

        cn.commit()
        print("\n" + "="*60)
        print("Data loading complete!")
        print("="*60)

        print("\nDatabase Summary:")
        cursor.execute("SELECT COUNT(*) FROM agency")
        print(f"  Agencies: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM route")
        print(f"  Routes: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM service_calendar")
        print(f"  Service Calendars: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM calendar_exception")
        print(f"  Calendar Exceptions: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM stop")
        print(f"  Stops: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM trip")
        print(f"  Trips: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM stop_time")
        print(f"  Stop Times: {cursor.fetchone()[0]}")

        print(f"\nFilters applied:")
        print(f"  Date: {FILTER_START_DATE}")
        print(f"  Time: {FILTER_START_TIME} to {FILTER_END_TIME}")
        print("\nNote: actual_trip and actual_stop_event tables are empty.")
        print("      These will be populated through the application UI.")

    except psycopg2.Error as e:
        print(f"\nDatabase error: {e}")
        if cn:
            cn.rollback()
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
