DROP VIEW IF EXISTS accessibility_metrics CASCADE;
DROP VIEW IF EXISTS service_coverage_by_day CASCADE;
DROP VIEW IF EXISTS transfer_opportunities CASCADE;
DROP VIEW IF EXISTS route_time_performance CASCADE;
DROP VIEW IF EXISTS stop_service_frequency CASCADE;
DROP VIEW IF EXISTS active_routes_summary CASCADE;

-- Route-level statistics for all active routes
-- Shows trip counts, service variations, and unique stops served
CREATE VIEW active_routes_summary AS
SELECT
    r.route_id,
    r.route_short_name,
    r.route_long_name,
    r.route_type,
    a.agency_name,
    COUNT(DISTINCT t.trip_id) AS total_trips,
    COUNT(DISTINCT t.service_id) AS service_variations,
    COUNT(DISTINCT st.stop_id) AS unique_stops
FROM routes r
JOIN agencies a ON r.agency_id = a.agency_id
JOIN trips t ON r.route_id = t.route_id
JOIN stop_times st ON t.trip_id = st.trip_id
GROUP BY r.route_id, r.route_short_name, r.route_long_name, r.route_type, a.agency_name;

-- Daily service frequency for each stop
-- Calculates average trips per day for weekday service
CREATE VIEW stop_service_frequency AS
WITH weekday_trips AS (
    SELECT
        st.stop_id,
        t.trip_id,
        sc.monday, sc.tuesday, sc.wednesday, sc.thursday, sc.friday
    FROM stop_times st
    JOIN trips t ON st.trip_id = t.trip_id
    JOIN service_calendars sc ON t.service_id = sc.service_id
)
SELECT
    s.stop_id,
    s.stop_name,
    s.stop_lat,
    s.stop_lon,
    COUNT(DISTINCT wt.trip_id) AS avg_daily_trips,
    ROUND(COUNT(DISTINCT wt.trip_id)::NUMERIC / 5, 2) AS avg_weekday_frequency
FROM stops s
LEFT JOIN weekday_trips wt ON s.stop_id = wt.stop_id
WHERE wt.monday = 1 OR wt.tuesday = 1 OR wt.wednesday = 1
      OR wt.thursday = 1 OR wt.friday = 1
GROUP BY s.stop_id, s.stop_name, s.stop_lat, s.stop_lon;

-- Route timing characteristics
-- Analyzes average, minimum, and maximum trip duration for each route
CREATE VIEW route_time_performance AS
SELECT
    r.route_id,
    r.route_short_name,
    r.route_long_name,
    AVG(trip_duration_minutes) AS avg_trip_duration,
    MIN(trip_duration_minutes) AS min_trip_duration,
    MAX(trip_duration_minutes) AS max_trip_duration,
    COUNT(DISTINCT trip_id) AS sample_size
FROM routes r
JOIN (
    SELECT
        t.trip_id,
        t.route_id,
        EXTRACT(EPOCH FROM (MAX(st.arrival_time) - MIN(st.departure_time))) / 60.0 AS trip_duration_minutes
    FROM trips t
    JOIN stop_times st ON t.trip_id = st.trip_id
    GROUP BY t.trip_id, t.route_id
) trip_durations ON r.route_id = trip_durations.route_id
GROUP BY r.route_id, r.route_short_name, r.route_long_name;

-- Stops served by multiple routes (transfer hubs)
-- Identifies transfer opportunities where passengers can switch between routes
CREATE VIEW transfer_opportunities AS
SELECT
    s.stop_id,
    s.stop_name,
    s.stop_lat,
    s.stop_lon,
    COUNT(DISTINCT r.route_id) AS route_count,
    COUNT(DISTINCT r.agency_id) AS agency_count,
    STRING_AGG(DISTINCT r.route_short_name, ', ' ORDER BY r.route_short_name) AS routes_available
FROM stops s
JOIN stop_times st ON s.stop_id = st.stop_id
JOIN trips t ON st.trip_id = t.trip_id
JOIN routes r ON t.route_id = r.route_id
GROUP BY s.stop_id, s.stop_name, s.stop_lat, s.stop_lon
HAVING COUNT(DISTINCT r.route_id) > 1;

-- Service availability by day of week
-- Shows total trips and active routes for each day
CREATE VIEW service_coverage_by_day AS
SELECT
    'Monday' AS day_of_week,
    COUNT(DISTINCT t.trip_id) AS total_trips,
    COUNT(DISTINCT t.route_id) AS active_routes
FROM trips t
JOIN service_calendars sc ON t.service_id = sc.service_id
WHERE sc.monday = 1
UNION ALL
SELECT 'Tuesday', COUNT(DISTINCT t.trip_id), COUNT(DISTINCT t.route_id)
FROM trips t JOIN service_calendars sc ON t.service_id = sc.service_id
WHERE sc.tuesday = 1
UNION ALL
SELECT 'Wednesday', COUNT(DISTINCT t.trip_id), COUNT(DISTINCT t.route_id)
FROM trips t JOIN service_calendars sc ON t.service_id = sc.service_id
WHERE sc.wednesday = 1
UNION ALL
SELECT 'Thursday', COUNT(DISTINCT t.trip_id), COUNT(DISTINCT t.route_id)
FROM trips t JOIN service_calendars sc ON t.service_id = sc.service_id
WHERE sc.thursday = 1
UNION ALL
SELECT 'Friday', COUNT(DISTINCT t.trip_id), COUNT(DISTINCT t.route_id)
FROM trips t JOIN service_calendars sc ON t.service_id = sc.service_id
WHERE sc.friday = 1
UNION ALL
SELECT 'Saturday', COUNT(DISTINCT t.trip_id), COUNT(DISTINCT t.route_id)
FROM trips t JOIN service_calendars sc ON t.service_id = sc.service_id
WHERE sc.saturday = 1
UNION ALL
SELECT 'Sunday', COUNT(DISTINCT t.trip_id), COUNT(DISTINCT t.route_id)
FROM trips t JOIN service_calendars sc ON t.service_id = sc.service_id
WHERE sc.sunday = 1;

-- Wheelchair accessibility metrics by route
-- Calculates percentage of accessible trips for each route
CREATE VIEW accessibility_metrics AS
SELECT
    r.route_id,
    r.route_short_name,
    a.agency_name,
    COUNT(DISTINCT t.trip_id) AS total_trips,
    SUM(CASE WHEN t.wheelchair_accessible = 1 THEN 1 ELSE 0 END) AS accessible_trips,
    ROUND(100.0 * SUM(CASE WHEN t.wheelchair_accessible = 1 THEN 1 ELSE 0 END) /
          NULLIF(COUNT(t.trip_id), 0), 2) AS accessibility_percentage
FROM routes r
JOIN agencies a ON r.agency_id = a.agency_id
JOIN trips t ON r.route_id = t.route_id
GROUP BY r.route_id, r.route_short_name, a.agency_name;
