-- ============================================================================
-- Seattle Public Transit Analytics Database Schema
-- ============================================================================

-- Drop existing tables (in reverse dependency order)
DROP TABLE IF EXISTS actual_stop_event CASCADE;
DROP TABLE IF EXISTS actual_trip CASCADE;
DROP TABLE IF EXISTS stop_time CASCADE;
DROP TABLE IF EXISTS trip CASCADE;
DROP TABLE IF EXISTS calendar_exception CASCADE;
DROP TABLE IF EXISTS service_calendar CASCADE;
DROP TABLE IF EXISTS stop CASCADE;
DROP TABLE IF EXISTS route CASCADE;
DROP TABLE IF EXISTS agency CASCADE;

-- ============================================================================
-- STRONG ENTITIES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- AGENCY: Transit agencies operating the service
-- ----------------------------------------------------------------------------
CREATE TABLE agency (
    agency_id INTEGER PRIMARY KEY,
    agency_name VARCHAR(255) NOT NULL
);

-- ----------------------------------------------------------------------------
-- ROUTE: Transit routes/lines
-- ----------------------------------------------------------------------------
CREATE TABLE route (
    route_id INTEGER PRIMARY KEY,
    agency_id INTEGER NOT NULL REFERENCES agency(agency_id),
    route_short_name VARCHAR(50),
    route_long_name VARCHAR(255),
    route_type INTEGER NOT NULL
);

-- ----------------------------------------------------------------------------
-- SERVICE: Service calendar patterns (weekday, weekend, etc.)
-- ----------------------------------------------------------------------------
CREATE TABLE service_calendar (
    service_id INTEGER PRIMARY KEY,
    monday BOOLEAN NOT NULL,
    tuesday BOOLEAN NOT NULL,
    wednesday BOOLEAN NOT NULL,
    thursday BOOLEAN NOT NULL,
    friday BOOLEAN NOT NULL,
    saturday BOOLEAN NOT NULL,
    sunday BOOLEAN NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    CHECK (start_date <= end_date)
);

-- ----------------------------------------------------------------------------
-- STOP: Physical locations where vehicles pick up/drop off passengers
-- ----------------------------------------------------------------------------
CREATE TABLE stop (
    stop_id INTEGER PRIMARY KEY,
    stop_name VARCHAR(255) NOT NULL,
    stop_lat DECIMAL(10, 6) NOT NULL,
    stop_lon DECIMAL(10, 6) NOT NULL,
    location_type INTEGER DEFAULT 0,
    parent_station INTEGER REFERENCES stop(stop_id),
    wheelchair_boarding INTEGER DEFAULT 0,

    CHECK (stop_lat BETWEEN -90 AND 90),
    CHECK (stop_lon BETWEEN -180 AND 180)
);

-- ----------------------------------------------------------------------------
-- TRIP: A specific scheduled journey of a vehicle along a route
-- ----------------------------------------------------------------------------
CREATE TABLE trip (
    trip_id INTEGER PRIMARY KEY,
    route_id INTEGER NOT NULL REFERENCES route(route_id),
    service_id INTEGER NOT NULL REFERENCES service_calendar(service_id),
    trip_headsign VARCHAR(255),
    direction_id INTEGER,
    wheelchair_accessible INTEGER DEFAULT 0
);

-- ----------------------------------------------------------------------------
-- ACTUAL_TRIP: User-recorded actual transit journeys
-- ----------------------------------------------------------------------------
CREATE TABLE actual_trip (
    actual_trip_id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES trip(trip_id),
    observation_date DATE NOT NULL,
    weather_condition VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- WEAK ENTITIES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- CALENDAR_EXCEPTION: Date-specific exceptions to service patterns
-- Weak entity - depends on SERVICE
-- ----------------------------------------------------------------------------
CREATE TABLE calendar_exception (
    service_id INTEGER NOT NULL REFERENCES service_calendar(service_id),
    date DATE NOT NULL,
    exception_type INTEGER NOT NULL,

    PRIMARY KEY (service_id, date)
);

-- ----------------------------------------------------------------------------
-- STOP_TIME: Scheduled arrival/departure times for trips at stops
-- Weak entity - depends on TRIP
-- ----------------------------------------------------------------------------
CREATE TABLE stop_time (
    trip_id INTEGER NOT NULL REFERENCES trip(trip_id),
    stop_id INTEGER NOT NULL REFERENCES stop(stop_id),
    stop_sequence INTEGER NOT NULL,
    arrival_time TIME NOT NULL,
    departure_time TIME NOT NULL,

    PRIMARY KEY (trip_id, stop_sequence),
    CHECK (stop_sequence > 0)
);

-- ----------------------------------------------------------------------------
-- ACTUAL_STOP_EVENT: Actual observed arrival/departure at stops
-- Weak entity - depends on ACTUAL_TRIP
-- ----------------------------------------------------------------------------
CREATE TABLE actual_stop_event (
    actual_trip_id INTEGER NOT NULL REFERENCES actual_trip(actual_trip_id),
    stop_id INTEGER NOT NULL REFERENCES stop(stop_id),
    sequence_number INTEGER NOT NULL,
    actual_arrival_time TIME NOT NULL,
    actual_departure_time TIME NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    crowding_level INTEGER,
    vehicle_number VARCHAR(50),

    PRIMARY KEY (actual_trip_id, sequence_number),
    CHECK (sequence_number > 0),
    CHECK (crowding_level IS NULL OR crowding_level BETWEEN 1 AND 5),
    CHECK (event_type IN ('boarding', 'alighting', 'passthrough'))
);

