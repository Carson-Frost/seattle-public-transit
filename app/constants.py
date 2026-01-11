"""Constants and configuration values for Seattle Transit app."""

# Time filter options for schedule queries
TIME_OPTIONS = {
    "5:00 AM": ("5:00 AM", "05:00:00"),
    "6:00 AM": ("6:00 AM", "06:00:00"),
    "7:00 AM": ("7:00 AM", "07:00:00"),
    "8:00 AM": ("8:00 AM", "08:00:00"),
    "9:00 AM": ("9:00 AM", "09:00:00"),
    "10:00 AM": ("10:00 AM", "10:00:00"),
    "12:00 PM": ("12:00 PM", "12:00:00"),
    "3:00 PM": ("3:00 PM", "15:00:00"),
    "6:00 PM": ("6:00 PM", "18:00:00"),
}

# GTFS route type mappings
ROUTE_TYPES = {
    0: "Streetcar",
    1: "Subway",
    2: "Rail",
    3: "Bus",
    4: "Ferry",
    5: "Cable Tram",
    6: "Aerial Lift",
    7: "Funicular",
    11: "Trolleybus",
    12: "Monorail",
}

# Performance thresholds (in minutes)
DELAY_THRESHOLDS = {
    "early": -1,
    "late": 1,
}

# Days of week column mapping
DOW_COLUMNS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Event types for actual trip recording
EVENT_TYPES = ["boarding", "passthrough", "alighting"]

# Crowding level range
CROWDING_RANGE = (1, 5)

# Weather options
WEATHER_OPTIONS = ["Clear", "Cloudy", "Rainy", "Foggy"]
