DROP TABLE IF EXISTS fare_rule CASCADE;
DROP TABLE IF EXISTS stop_time CASCADE;
DROP TABLE IF EXISTS trip CASCADE;
DROP TABLE IF EXISTS fare_type CASCADE;
DROP TABLE IF EXISTS shape CASCADE;
DROP TABLE IF EXISTS calendar_exception CASCADE;
DROP TABLE IF EXISTS service_calendar CASCADE;
DROP TABLE IF EXISTS stop CASCADE;
DROP TABLE IF EXISTS route CASCADE;
DROP TABLE IF EXISTS agency CASCADE;

-- Transit agencies operating routes in the system
-- Primary Key: agency_id
CREATE TABLE agency (
    agency_id INTEGER NOT NULL,
    agency_name VARCHAR(100) NOT NULL,
    agency_url VARCHAR(255),
    agency_timezone VARCHAR(50) NOT NULL,
    agency_lang CHAR(2),
    agency_phone VARCHAR(20),
    agency_fare_url VARCHAR(255),
    PRIMARY KEY (agency_id)
);

-- Transit routes operated by agencies
-- Primary Key: route_id
-- Foreign Key: agency_id references agency
CREATE TABLE route (
    route_id INTEGER NOT NULL,
    agency_id INTEGER NOT NULL,
    route_short_name VARCHAR(50),
    route_long_name VARCHAR(200),
    route_desc TEXT,
    route_type INTEGER NOT NULL,
    route_url VARCHAR(255),
    route_color CHAR(6),
    route_text_color CHAR(6),
    PRIMARY KEY (route_id),
    FOREIGN KEY (agency_id) REFERENCES agency(agency_id)
);

-- Physical locations where vehicles pick up or drop off passengers
-- Primary Key: stop_id
-- Foreign Key: parent_station references stop (self-referencing for hierarchical relationships)
CREATE TABLE stop (
    stop_id INTEGER NOT NULL,
    stop_code VARCHAR(20),
    stop_name VARCHAR(200) NOT NULL,
    tts_stop_name VARCHAR(200),
    stop_desc TEXT,
    stop_lat DECIMAL(10, 8) NOT NULL,
    stop_lon DECIMAL(11, 8) NOT NULL,
    zone_id INTEGER,
    stop_url VARCHAR(255),
    location_type INTEGER DEFAULT 0,
    parent_station INTEGER,
    stop_timezone VARCHAR(50),
    wheelchair_boarding INTEGER DEFAULT 0,
    PRIMARY KEY (stop_id),
    FOREIGN KEY (parent_station) REFERENCES stop(stop_id),
    CONSTRAINT valid_location_type CHECK (location_type IN (0, 1, 2)),
    CONSTRAINT valid_wheelchair_boarding CHECK (wheelchair_boarding IN (0, 1, 2)),
    CONSTRAINT valid_stop_lat CHECK (stop_lat BETWEEN -90 AND 90),
    CONSTRAINT valid_stop_lon CHECK (stop_lon BETWEEN -180 AND 180)
);

-- Service schedules defining which days of the week routes operate
-- Primary Key: service_id
CREATE TABLE service_calendar (
    service_id INTEGER NOT NULL,
    monday SMALLINT NOT NULL,
    tuesday SMALLINT NOT NULL,
    wednesday SMALLINT NOT NULL,
    thursday SMALLINT NOT NULL,
    friday SMALLINT NOT NULL,
    saturday SMALLINT NOT NULL,
    sunday SMALLINT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    PRIMARY KEY (service_id),
    CONSTRAINT valid_monday CHECK (monday IN (0, 1)),
    CONSTRAINT valid_tuesday CHECK (tuesday IN (0, 1)),
    CONSTRAINT valid_wednesday CHECK (wednesday IN (0, 1)),
    CONSTRAINT valid_thursday CHECK (thursday IN (0, 1)),
    CONSTRAINT valid_friday CHECK (friday IN (0, 1)),
    CONSTRAINT valid_saturday CHECK (saturday IN (0, 1)),
    CONSTRAINT valid_sunday CHECK (sunday IN (0, 1)),
    CONSTRAINT valid_date_range CHECK (end_date >= start_date)
);

-- Exceptions to regular service calendars (holidays, special events)
-- Primary Key: (service_id, date)
-- Foreign Key: service_id references service_calendar
CREATE TABLE calendar_exception (
    service_id INTEGER NOT NULL,
    date DATE NOT NULL,
    exception_type SMALLINT NOT NULL,
    PRIMARY KEY (service_id, date),
    FOREIGN KEY (service_id) REFERENCES service_calendar(service_id),
    CONSTRAINT valid_exception_type CHECK (exception_type IN (1, 2))
);

-- Geographic paths of routes as sequences of latitude/longitude points
-- Composite Primary Key: (shape_id, shape_pt_sequence)
CREATE TABLE shape (
    shape_id INTEGER NOT NULL,
    shape_pt_sequence INTEGER NOT NULL,
    shape_pt_lat DECIMAL(10, 8) NOT NULL,
    shape_pt_lon DECIMAL(11, 8) NOT NULL,
    shape_dist_traveled DECIMAL(10, 2),
    PRIMARY KEY (shape_id, shape_pt_sequence),
    CONSTRAINT valid_shape_pt_lat CHECK (shape_pt_lat BETWEEN -90 AND 90),
    CONSTRAINT valid_shape_pt_lon CHECK (shape_pt_lon BETWEEN -180 AND 180),
    CONSTRAINT valid_shape_pt_sequence CHECK (shape_pt_sequence >= 0),
    CONSTRAINT valid_shape_dist_traveled CHECK (shape_dist_traveled IS NULL OR shape_dist_traveled >= 0)
);

-- Fare products and pricing information
-- Primary Key: fare_id
-- Foreign Key: agency_id references agency
CREATE TABLE fare_type (
    fare_id INTEGER NOT NULL,
    agency_id INTEGER NOT NULL,
    fare_period_id INTEGER,
    price DECIMAL(5, 2) NOT NULL,
    descriptions VARCHAR(100),
    currency_type CHAR(3) DEFAULT 'USD',
    payment_method SMALLINT,
    transfers INTEGER,
    transfer_duration INTEGER,
    PRIMARY KEY (fare_id),
    FOREIGN KEY (agency_id) REFERENCES agency(agency_id),
    CONSTRAINT valid_payment_method CHECK (payment_method IN (0, 1)),
    CONSTRAINT valid_price CHECK (price >= 0)
);

-- Individual journey instances of routes with specific schedules
-- Primary Key: trip_id
-- Foreign Keys: route_id references route, service_id references service_calendar
CREATE TABLE trip (
    route_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    trip_id BIGINT NOT NULL,
    trip_headsign VARCHAR(200),
    trip_short_name VARCHAR(50),
    direction_id SMALLINT,
    block_id INTEGER,
    shape_id INTEGER,
    peak_flag SMALLINT,
    fare_id INTEGER,
    wheelchair_accessible SMALLINT DEFAULT 0,
    bikes_allowed SMALLINT DEFAULT 0,
    PRIMARY KEY (trip_id),
    FOREIGN KEY (route_id) REFERENCES route(route_id),
    FOREIGN KEY (service_id) REFERENCES service_calendar(service_id),
    CONSTRAINT valid_direction_id CHECK (direction_id IN (0, 1)),
    CONSTRAINT valid_wheelchair_accessible CHECK (wheelchair_accessible IN (0, 1, 2)),
    CONSTRAINT valid_bikes_allowed CHECK (bikes_allowed IN (0, 1, 2))
);

-- Schedule of stops for each trip with arrival/departure times
-- Many-to-many relationship between trips and stops
-- Primary Key: (trip_id, stop_sequence)
-- Foreign Keys: trip_id references trip, stop_id references stop
CREATE TABLE stop_time (
    trip_id BIGINT NOT NULL,
    arrival_time VARCHAR(8) NOT NULL,
    departure_time VARCHAR(8) NOT NULL,
    stop_id INTEGER NOT NULL,
    stop_sequence INTEGER NOT NULL,
    stop_headsign VARCHAR(200),
    pickup_type SMALLINT DEFAULT 0,
    drop_off_type SMALLINT DEFAULT 0,
    shape_dist_traveled DECIMAL(10, 2),
    timepoint SMALLINT,
    PRIMARY KEY (trip_id, stop_sequence),
    FOREIGN KEY (trip_id) REFERENCES trip(trip_id),
    FOREIGN KEY (stop_id) REFERENCES stop(stop_id),
    CONSTRAINT valid_pickup_type CHECK (pickup_type IN (0, 1, 2, 3)),
    CONSTRAINT valid_drop_off_type CHECK (drop_off_type IN (0, 1, 2, 3)),
    CONSTRAINT valid_stop_sequence CHECK (stop_sequence >= 0),
    CONSTRAINT valid_timepoint CHECK (timepoint IS NULL OR timepoint IN (0, 1))
);

-- Rules for applying fare types to routes and zones
-- Primary Key: fare_rule_id
-- Foreign Keys: fare_id references fare_type, route_id references route
CREATE TABLE fare_rule (
    fare_rule_id SERIAL NOT NULL,
    fare_id INTEGER NOT NULL,
    route_id INTEGER,
    origin_id VARCHAR(50),
    destination_id VARCHAR(50),
    contains_id VARCHAR(50),
    PRIMARY KEY (fare_rule_id),
    FOREIGN KEY (fare_id) REFERENCES fare_type(fare_id),
    FOREIGN KEY (route_id) REFERENCES route(route_id)
);
