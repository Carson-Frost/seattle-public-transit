import psycopg2
import csv
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Database connection parameters
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST')
}

# Path to GTFS data files
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

# Date and time range for filtering trips and related data
# Only load trips that run during this period to keep database size manageable
FILTER_START_DATE = '20251212'  # Format: YYYYMMDD
FILTER_END_DATE = '20251212'    # Format: YYYYMMDD
FILTER_START_TIME = '07:00:00'  # Format: HH:MM:SS
FILTER_END_TIME = '09:00:00'    # Format: HH:MM:SS

def load_agency(cursor):
    """Load all transit agencies. This is a small table so we load everything."""
    filepath = os.path.join(DATA_DIR, 'agency.txt')
    print("Loading agency.txt...")

    # Count first
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        total = sum(1 for _ in reader)

    print(f"  Found {total} agencies")

    # Then load
    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT INTO agency (agency_id, agency_name, agency_url, agency_timezone,
                                   agency_lang, agency_phone, agency_fare_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                row['agency_id'] or None,
                row['agency_name'],
                row['agency_url'] or None,
                row['agency_timezone'],
                row['agency_lang'] or None,
                row['agency_phone'] or None,
                row['agency_fare_url'] or None
            ))
            count += 1
    print(f"  Loaded {count} agencies")

def load_routes(cursor):
    """Load all routes. This is a small table (143 rows) so we load everything."""
    filepath = os.path.join(DATA_DIR, 'routes.txt')
    print("Loading routes.txt...")

    # Count first
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        total = sum(1 for _ in reader)

    print(f"  Found {total} routes")

    # Then load
    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT INTO route (route_id, agency_id, route_short_name, route_long_name,
                                  route_desc, route_type, route_url, route_color, route_text_color)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['route_id'],
                row['agency_id'],
                row['route_short_name'] or None,
                row['route_long_name'] or None,
                row['route_desc'] or None,
                row['route_type'],
                row['route_url'] or None,
                row['route_color'] or None,
                row['route_text_color'] or None
            ))
            count += 1
    print(f"  Loaded {count} routes")

def load_stops(cursor):
    """Load all stops. We keep all stops to show the complete transit network."""
    filepath = os.path.join(DATA_DIR, 'stops.txt')
    print("Loading stops.txt...")

    # Count first
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        total = sum(1 for _ in reader)

    print(f"  Found {total} stops")

    # Then load
    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT INTO stop (stop_id, stop_code, stop_name, tts_stop_name, stop_desc,
                                 stop_lat, stop_lon, zone_id, stop_url, location_type,
                                 parent_station, stop_timezone, wheelchair_boarding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['stop_id'],
                row['stop_code'] or None,
                row['stop_name'],
                row['tts_stop_name'] or None,
                row['stop_desc'] or None,
                row['stop_lat'],
                row['stop_lon'],
                row['zone_id'] or None,
                row['stop_url'] or None,
                row['location_type'] or 0,
                row['parent_station'] or None,
                row['stop_timezone'] or None,
                row['wheelchair_boarding'] or 0
            ))
            count += 1
    print(f"  Loaded {count} stops")

def load_calendar(cursor):
    """Load service calendar. Defines which days of the week each service runs."""
    filepath = os.path.join(DATA_DIR, 'calendar.txt')
    print("Loading calendar.txt...")

    # Count first
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        total = sum(1 for _ in reader)

    print(f"  Found {total} service calendars")

    # Then load
    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT INTO service_calendar (service_id, monday, tuesday, wednesday, thursday,
                                             friday, saturday, sunday, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['service_id'],
                row['monday'],
                row['tuesday'],
                row['wednesday'],
                row['thursday'],
                row['friday'],
                row['saturday'],
                row['sunday'],
                row['start_date'],
                row['end_date']
            ))
            count += 1
    print(f"  Loaded {count} service calendars")

def load_calendar_dates(cursor):
    """Load calendar exceptions (holidays, special service days)."""
    filepath = os.path.join(DATA_DIR, 'calendar_dates.txt')
    print("Loading calendar_dates.txt...")

    # Count first
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        total = sum(1 for _ in reader)

    print(f"  Found {total} calendar exceptions")

    # Then load
    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT INTO calendar_exception (service_id, date, exception_type)
                VALUES (%s, %s, %s)
            """, (
                row['service_id'],
                row['date'],
                row['exception_type']
            ))
            count += 1
    print(f"  Loaded {count} calendar exceptions")

def load_fare_attributes(cursor):
    """Load fare types and pricing information."""
    filepath = os.path.join(DATA_DIR, 'fare_attributes.txt')
    print("Loading fare_attributes.txt...")

    # Count first
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        total = sum(1 for _ in reader)

    print(f"  Found {total} fare types")

    # Then load
    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT INTO fare_type (fare_id, agency_id, fare_period_id, price, descriptions,
                                      currency_type, payment_method, transfers, transfer_duration)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['fare_id'],
                row['agency_id'],
                row['fare_period_id'] or None,
                row['price'],
                row['descriptions'] or None,
                row['currency_type'] or 'USD',
                row['payment_method'] or None,
                row['transfers'] or None,
                row['transfer_duration'] or None
            ))
            count += 1
    print(f"  Loaded {count} fare types")

def load_fare_rules(cursor):
    """Load fare rules (which fares apply to which routes/zones)."""
    filepath = os.path.join(DATA_DIR, 'fare_rules.txt')
    print("Loading fare_rules.txt...")

    # Count first
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        total = sum(1 for _ in reader)

    print(f"  Found {total} fare rules")

    # Then load
    count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT INTO fare_rule (fare_id, route_id, origin_id, destination_id, contains_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                row['fare_id'],
                row['route_id'] or None,
                row['origin_id'] or None,
                row['destination_id'] or None,
                row['contains_id'] or None
            ))
            count += 1
    print(f"  Loaded {count} fare rules")

def get_trip_start_times():
    """
    Scan stop_times to find the first departure time for each trip.
    Returns a dict of trip_id -> first_departure_time.
    """
    filepath = os.path.join(DATA_DIR, 'stop_times.txt')
    trip_start_times = {}

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = int(row['trip_id'])
            stop_sequence = int(row['stop_sequence'])

            # Only track the first stop for each trip
            if stop_sequence == 1:
                trip_start_times[trip_id] = row['departure_time']

    return trip_start_times

def analyze_filtered_data(cursor):
    """
    Analyze what will be loaded based on filters.
    Returns counts and IDs for filtered data.
    """
    print("Analyzing data to be loaded...")

    # Get active service IDs
    cursor.execute("""
        SELECT service_id
        FROM service_calendar
        WHERE start_date <= %s AND end_date >= %s
    """, (FILTER_END_DATE, FILTER_START_DATE))

    active_service_ids = set(row[0] for row in cursor.fetchall())

    # Get trip start times
    trip_start_times = get_trip_start_times()

    # Scan trips to find which ones match filters
    trips_filepath = os.path.join(DATA_DIR, 'trips.txt')
    filtered_trip_ids = set()
    filtered_shape_ids = set()

    with open(trips_filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = int(row['trip_id'])

            if int(row['service_id']) in active_service_ids:
                start_time = trip_start_times.get(trip_id)

                if start_time and FILTER_START_TIME <= start_time <= FILTER_END_TIME:
                    filtered_trip_ids.add(trip_id)
                    if row['shape_id']:
                        filtered_shape_ids.add(int(row['shape_id']))

    # Count stop_times for filtered trips
    stop_times_filepath = os.path.join(DATA_DIR, 'stop_times.txt')
    stop_time_count = 0
    with open(stop_times_filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['trip_id']) in filtered_trip_ids:
                stop_time_count += 1

    # Count shape points for filtered shapes
    shapes_filepath = os.path.join(DATA_DIR, 'shapes.txt')
    shape_point_count = 0
    with open(shapes_filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['shape_id']) in filtered_shape_ids:
                shape_point_count += 1

    print(f"\nFiltered data summary:")
    print(f"  Trips: {len(filtered_trip_ids)}")
    print(f"  Stop times: {stop_time_count}")
    print(f"  Shapes: {len(filtered_shape_ids)}")
    print(f"  Shape points: {shape_point_count}")
    print()

    return filtered_trip_ids, filtered_shape_ids

def load_trips_filtered(cursor, filtered_trip_ids, filtered_shape_ids):
    """
    Load only trips that were identified during analysis.
    """
    filepath = os.path.join(DATA_DIR, 'trips.txt')
    print(f"Loading trips.txt...")

    trip_count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = int(row['trip_id'])

            if trip_id in filtered_trip_ids:
                cursor.execute("""
                    INSERT INTO trip (route_id, service_id, trip_id, trip_headsign, trip_short_name,
                                     direction_id, block_id, shape_id, peak_flag, fare_id,
                                     wheelchair_accessible, bikes_allowed)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    row['route_id'],
                    row['service_id'],
                    row['trip_id'],
                    row['trip_headsign'] or None,
                    row['trip_short_name'] or None,
                    row['direction_id'] or None,
                    row['block_id'] or None,
                    row['shape_id'] or None,
                    row['peak_flag'] or None,
                    row['fare_id'] or None,
                    row['wheelchair_accessible'] or 0,
                    row['bikes_allowed'] or 0
                ))
                trip_count += 1

    print(f"  Loaded {trip_count} trips")

def load_stop_times_filtered(cursor, filtered_trip_ids):
    """
    Load only stop_times for the trips we loaded.
    """
    filepath = os.path.join(DATA_DIR, 'stop_times.txt')
    print(f"Loading stop_times.txt...")

    stop_time_count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['trip_id']) in filtered_trip_ids:
                cursor.execute("""
                    INSERT INTO stop_time (trip_id, arrival_time, departure_time, stop_id,
                                          stop_sequence, stop_headsign, pickup_type, drop_off_type,
                                          shape_dist_traveled, timepoint)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    row['trip_id'],
                    row['arrival_time'],
                    row['departure_time'],
                    row['stop_id'],
                    row['stop_sequence'],
                    row['stop_headsign'] or None,
                    row['pickup_type'] or 0,
                    row['drop_off_type'] or 0,
                    row['shape_dist_traveled'] or None,
                    row['timepoint'] or None
                ))
                stop_time_count += 1

    print(f"  Loaded {stop_time_count} stop times")

def load_shapes_filtered(cursor, filtered_shape_ids):
    """
    Load only shapes that are used by the trips we loaded.
    """
    filepath = os.path.join(DATA_DIR, 'shapes.txt')
    print(f"Loading shapes.txt...")

    shape_point_count = 0
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['shape_id']) in filtered_shape_ids:
                cursor.execute("""
                    INSERT INTO shape (shape_id, shape_pt_lat, shape_pt_lon, shape_pt_sequence,
                                      shape_dist_traveled)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    row['shape_id'],
                    row['shape_pt_lat'],
                    row['shape_pt_lon'],
                    row['shape_pt_sequence'],
                    row['shape_dist_traveled'] or None
                ))
                shape_point_count += 1

    print(f"  Loaded {shape_point_count} shape points")

def main():
    """
    Main function to load GTFS data into PostgreSQL.

    Loading strategy:
    1. Load all small reference tables (agencies, routes, stops, calendars, fares)
    2. Load filtered trips (only those running during specified date range)
    3. Load only stop_times and shapes related to those filtered trips

    This keeps database size manageable for a class project while maintaining
    data integrity and providing enough data for meaningful analysis.
    """
    cn = None
    cursor = None

    try:
        # Connect to database
        print("Connecting to database...")
        cn = psycopg2.connect(**DB_CONFIG)
        cursor = cn.cursor()
        print("Connected.\n")

        # Load all base reference tables (small, load everything)
        load_agency(cursor)
        load_routes(cursor)
        load_stops(cursor)
        load_calendar(cursor)
        load_calendar_dates(cursor)
        load_fare_attributes(cursor)
        load_fare_rules(cursor)

        # Analyze data to show what will be loaded
        filtered_trip_ids, filtered_shape_ids = analyze_filtered_data(cursor)

        # Load filtered trips and related data
        load_trips_filtered(cursor, filtered_trip_ids, filtered_shape_ids)
        load_stop_times_filtered(cursor, filtered_trip_ids)
        load_shapes_filtered(cursor, filtered_shape_ids)

        # Commit all changes to database
        cn.commit()
        print("\n" + "="*60)
        print("Data loading complete!")
        print("="*60)

        # Print summary statistics
        print("\nDatabase Summary:")
        cursor.execute("SELECT COUNT(*) FROM agency")
        print(f"  Agencies: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM route")
        print(f"  Routes: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM stop")
        print(f"  Stops: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM service_calendar")
        print(f"  Service Calendars: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM calendar_exception")
        print(f"  Calendar Exceptions: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM fare_type")
        print(f"  Fare Types: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM fare_rule")
        print(f"  Fare Rules: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM trip")
        print(f"  Trips: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM stop_time")
        print(f"  Stop Times: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM shape")
        print(f"  Shape Points: {cursor.fetchone()[0]}")

        print(f"\nFilters applied:")
        print(f"  Date: {FILTER_START_DATE}")
        print(f"  Time: {FILTER_START_TIME} to {FILTER_END_TIME}")

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
