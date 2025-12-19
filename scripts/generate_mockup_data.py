"""
Generate realistic mockup data based on actual trips and their stops in the database
"""

import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import random

load_dotenv()

cn = psycopg2.connect(
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST')
)
cursor = cn.cursor()

# Get 15 trips with their scheduled stops
cursor.execute("""
    SELECT DISTINCT t.trip_id
    FROM trip t
    JOIN stop_time st ON t.trip_id = st.trip_id
    ORDER BY t.trip_id
    LIMIT 15
""")

trip_ids = [row[0] for row in cursor.fetchall()]

print(f"Found {len(trip_ids)} trips")

# Generate actual_trip mockup data
weather_conditions = ['Clear', 'Rainy', 'Cloudy', 'Foggy', '', '']  # Empty strings for None
observation_date = '2025-12-12'  # All observations on same date

actual_trip_data = []
for i, trip_id in enumerate(trip_ids):
    weather = random.choice(weather_conditions)
    actual_trip_data.append(f"{trip_id},{observation_date},{weather}")

# Write actual_trip_mockup.txt
with open('./data/actual_trip_mockup.txt', 'w') as f:
    f.write("trip_id,observation_date,weather_condition\n")
    f.write("\n".join(actual_trip_data))

print(f"Generated {len(actual_trip_data)} actual trips")

# Generate actual_stop_event mockup data
actual_stop_event_data = []
vehicle_numbers = ['5421', '5433', '5412', '5488', '5502', '5394', '5445', '5523', '5380', '5428', '5467', '5451', '', '']

for actual_trip_id, trip_id in enumerate(trip_ids, start=1):
    # Get the scheduled stops for this trip
    cursor.execute("""
        SELECT st.stop_id, st.stop_sequence, st.arrival_time, st.departure_time
        FROM stop_time st
        WHERE st.trip_id = %s
        ORDER BY st.stop_sequence
        LIMIT 5
    """, (trip_id,))

    stops = cursor.fetchall()

    if not stops:
        continue

    vehicle = random.choice(vehicle_numbers)

    # Generate events for 3-5 stops
    num_stops = min(random.randint(3, 5), len(stops))
    selected_stops = stops[:num_stops]

    for seq_num, (stop_id, stop_sequence, arrival_time, departure_time) in enumerate(selected_stops, start=1):
        delay_minutes = random.randint(-2, 4)

        # Convert time to datetime for calculation
        arrival_dt = datetime.strptime(str(arrival_time), '%H:%M:%S')
        departure_dt = datetime.strptime(str(departure_time), '%H:%M:%S')

        actual_arrival = (arrival_dt + timedelta(minutes=delay_minutes)).strftime('%H:%M:%S')
        actual_departure = (departure_dt + timedelta(minutes=delay_minutes)).strftime('%H:%M:%S')

        # Event types: first is boarding, last is alighting, middle is passthrough
        if seq_num == 1:
            event_type = 'boarding'
        elif seq_num == num_stops:
            event_type = 'alighting'
        else:
            event_type = 'passthrough'

        # Crowding level
        crowding = random.choice(['', '', '2', '3', '4', '5'])

        actual_stop_event_data.append(
            f"{actual_trip_id},{stop_id},{seq_num},{actual_arrival},{actual_departure},{event_type},{crowding},{vehicle}"
        )

# Write actual_stop_event_mockup.txt
with open('./data/actual_stop_event_mockup.txt', 'w') as f:
    f.write("actual_trip_id,stop_id,sequence_number,actual_arrival_time,actual_departure_time,event_type,crowding_level,vehicle_number\n")
    f.write("\n".join(actual_stop_event_data))

print(f"Generated {len(actual_stop_event_data)} actual stop events")

cursor.close()
cn.close()

print("\nMockup data files generated successfully!")
print("Run: python scripts/load_actual_trip_mockup.py")
