DROP TABLE IF EXISTS fare_rules CASCADE;
DROP TABLE IF EXISTS stop_times CASCADE;
DROP TABLE IF EXISTS trips CASCADE;
DROP TABLE IF EXISTS fare_types CASCADE;
DROP TABLE IF EXISTS shapes CASCADE;
DROP TABLE IF EXISTS calendar_exceptions CASCADE;
DROP TABLE IF EXISTS service_calendars CASCADE;
DROP TABLE IF EXISTS stops CASCADE;
DROP TABLE IF EXISTS routes CASCADE;
DROP TABLE IF EXISTS agencies CASCADE;

-- Transit agencies operating routes in the system
-- Primary Key: agency_id
CREATE TABLE agencies (
    agency_id INTEGER PRIMARY KEY,
    agency_name VARCHAR(100) NOT NULL,
    agency_url VARCHAR(255),
    agency_timezone VARCHAR(50) NOT NULL,
    agency_lang CHAR(2),
    agency_phone VARCHAR(20),
    agency_fare_url VARCHAR(255)
);

-- Transit routes operated by agencies
-- Primary Key: route_id
-- Foreign Key: agency_id references agencies
CREATE TABLE routes (
    route_id INTEGER PRIMARY KEY,
    agency_id INTEGER NOT NULL,
    route_short_name VARCHAR(50),
    route_long_name VARCHAR(200),
    route_desc TEXT,
    route_type INTEGER NOT NULL,
    route_url VARCHAR(255),
    route_color CHAR(6),
    route_text_color CHAR(6),
    FOREIGN KEY (agency_id) REFERENCES agencies(agency_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- Physical locations where vehicles pick up or drop off passengers
-- Primary Key: stop_id
-- Foreign Key: parent_station references stops (self-referencing for hierarchical relationships)
CREATE TABLE stops (
    stop_id INTEGER PRIMARY KEY,
    stop_code VARCHAR(20),
    stop_name VARCHAR(200) NOT NULL,
    stop_desc TEXT,
    stop_lat DECIMAL(10, 8) NOT NULL,
    stop_lon DECIMAL(11, 8) NOT NULL,
    zone_id INTEGER,
    location_type INTEGER DEFAULT 0,
    parent_station INTEGER,
    wheelchair_boarding INTEGER DEFAULT 0,
    FOREIGN KEY (parent_station) REFERENCES stops(stop_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    CHECK (location_type IN (0, 1, 2)),
    CHECK (wheelchair_boarding IN (0, 1, 2)),
    CHECK (stop_lat BETWEEN -90 AND 90),
    CHECK (stop_lon BETWEEN -180 AND 180)
);

-- Service schedules defining which days of the week routes operate
-- Primary Key: service_id
CREATE TABLE service_calendars (
    service_id INTEGER PRIMARY KEY,
    monday SMALLINT NOT NULL CHECK (monday IN (0, 1)),
    tuesday SMALLINT NOT NULL CHECK (tuesday IN (0, 1)),
    wednesday SMALLINT NOT NULL CHECK (wednesday IN (0, 1)),
    thursday SMALLINT NOT NULL CHECK (thursday IN (0, 1)),
    friday SMALLINT NOT NULL CHECK (friday IN (0, 1)),
    saturday SMALLINT NOT NULL CHECK (saturday IN (0, 1)),
    sunday SMALLINT NOT NULL CHECK (sunday IN (0, 1)),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    CHECK (end_date >= start_date)
);

-- Exceptions to regular service calendars (holidays, special events)
-- Primary Key: exception_id
-- Foreign Key: service_id references service_calendars
CREATE TABLE calendar_exceptions (
    exception_id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL,
    exception_date DATE NOT NULL,
    exception_type SMALLINT NOT NULL CHECK (exception_type IN (1, 2)),
    UNIQUE(service_id, exception_date),
    FOREIGN KEY (service_id) REFERENCES service_calendars(service_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- Geographic paths of routes as sequences of latitude/longitude points
-- Composite Primary Key: (shape_id, shape_pt_sequence)
CREATE TABLE shapes (
    shape_id INTEGER NOT NULL,
    shape_pt_sequence INTEGER NOT NULL,
    shape_pt_lat DECIMAL(10, 8) NOT NULL,
    shape_pt_lon DECIMAL(11, 8) NOT NULL,
    shape_dist_traveled DECIMAL(10, 2),
    PRIMARY KEY (shape_id, shape_pt_sequence),
    CHECK (shape_pt_lat BETWEEN -90 AND 90),
    CHECK (shape_pt_lon BETWEEN -180 AND 180),
    CHECK (shape_pt_sequence >= 0),
    CHECK (shape_dist_traveled IS NULL OR shape_dist_traveled >= 0)
);

-- Fare products and pricing information
-- Primary Key: fare_id
-- Foreign Key: agency_id references agencies
CREATE TABLE fare_types (
    fare_id INTEGER PRIMARY KEY,
    agency_id INTEGER NOT NULL,
    fare_period_id INTEGER,
    price DECIMAL(5, 2) NOT NULL,
    description VARCHAR(100),
    currency_type CHAR(3) DEFAULT 'USD',
    payment_method SMALLINT CHECK (payment_method IN (0, 1)),
    transfers INTEGER,
    transfer_duration INTEGER,
    FOREIGN KEY (agency_id) REFERENCES agencies(agency_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CHECK (price >= 0)
);

-- Individual journey instances of routes with specific schedules
-- Primary Key: trip_id
-- Foreign Keys: route_id references routes, service_id references service_calendars
CREATE TABLE trips (
    trip_id BIGINT PRIMARY KEY,
    route_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    trip_headsign VARCHAR(200),
    direction_id SMALLINT CHECK (direction_id IN (0, 1)),
    block_id INTEGER,
    shape_id INTEGER,
    wheelchair_accessible SMALLINT DEFAULT 0 CHECK (wheelchair_accessible IN (0, 1, 2)),
    bikes_allowed SMALLINT DEFAULT 0 CHECK (bikes_allowed IN (0, 1, 2)),
    FOREIGN KEY (route_id) REFERENCES routes(route_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    FOREIGN KEY (service_id) REFERENCES service_calendars(service_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- Schedule of stops for each trip with arrival/departure times
-- Many-to-many relationship between trips and stops
-- Primary Key: stop_time_id
-- Foreign Keys: trip_id references trips, stop_id references stops
CREATE TABLE stop_times (
    stop_time_id SERIAL PRIMARY KEY,
    trip_id BIGINT NOT NULL,
    stop_id INTEGER NOT NULL,
    arrival_time TIME NOT NULL,
    departure_time TIME NOT NULL,
    stop_sequence INTEGER NOT NULL,
    stop_headsign VARCHAR(200),
    pickup_type SMALLINT DEFAULT 0 CHECK (pickup_type IN (0, 1, 2, 3)),
    drop_off_type SMALLINT DEFAULT 0 CHECK (drop_off_type IN (0, 1, 2, 3)),
    shape_dist_traveled DECIMAL(10, 2),
    timepoint SMALLINT CHECK (timepoint IS NULL OR timepoint IN (0, 1)),
    UNIQUE(trip_id, stop_sequence),
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    FOREIGN KEY (stop_id) REFERENCES stops(stop_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CHECK (stop_sequence >= 0),
    CHECK (departure_time >= arrival_time)
);

-- Rules for applying fare types to routes and zones
-- Primary Key: fare_rule_id
-- Foreign Keys: fare_id references fare_types, route_id references routes
CREATE TABLE fare_rules (
    fare_rule_id SERIAL PRIMARY KEY,
    fare_id INTEGER NOT NULL,
    route_id INTEGER,
    origin_zone_id INTEGER,
    destination_zone_id INTEGER,
    contains_zone_id INTEGER,
    FOREIGN KEY (fare_id) REFERENCES fare_types(fare_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    FOREIGN KEY (route_id) REFERENCES routes(route_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
