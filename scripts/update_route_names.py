"""
Temporary script to update route long_name with descriptions from routes.txt
Run this once to fix existing database records.
"""

import psycopg2
import csv
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

# Path to routes.txt
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
ROUTES_FILE = os.path.join(DATA_DIR, 'routes.txt')

def update_route_names():
    """Update route long_name from route_desc in routes.txt"""
    cn = None
    cursor = None

    try:
        print("="*60)
        print("Update Route Names - Seattle Public Transit")
        print("="*60)

        # Connect to database
        print("\nConnecting to database...")
        cn = psycopg2.connect(**DB_CONFIG)
        cursor = cn.cursor()
        print("Connected.")

        # Read routes from file
        print(f"\nReading routes from {ROUTES_FILE}...")
        route_descriptions = {}

        with open(ROUTES_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                route_id = row['route_id']
                route_desc = row['route_desc']
                if route_desc:
                    route_descriptions[route_id] = route_desc

        print(f"Found {len(route_descriptions)} routes with descriptions")

        # Update each route
        print("\nUpdating routes in database...")
        updated_count = 0

        for route_id, description in route_descriptions.items():
            cursor.execute(
                "UPDATE route SET route_long_name = %s WHERE route_id = %s",
                (description, route_id)
            )
            updated_count += 1

        # Commit changes
        cn.commit()

        print(f"Successfully updated {updated_count} routes")

        # Verify results
        print("\nVerifying updates...")
        cursor.execute("SELECT COUNT(*) FROM route WHERE route_long_name IS NOT NULL AND route_long_name != ''")
        count_with_names = cursor.fetchone()[0]
        print(f"Routes with long names: {count_with_names}")

        # Show some examples
        print("\nExamples of updated routes:")
        cursor.execute("""
            SELECT route_short_name, route_long_name
            FROM route
            WHERE route_long_name IS NOT NULL AND route_long_name != ''
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]} - {row[1]}")

        print("\n" + "="*60)
        print("Update complete!")
        print("="*60)

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
    update_route_names()
