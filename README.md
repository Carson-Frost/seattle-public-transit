# Seattle Public Transit Analytics

A Streamlit dashboard for analyzing Seattle public transit data from [King County Metro](https://kingcounty.gov/en/dept/metro/travel-options/transit-data/open-data).

## Features

- **Performance Analysis**: Compare actual vs scheduled arrival times, view delay distributions by weather and crowding
  <img width="1872" height="822" alt="image" src="https://github.com/user-attachments/assets/fe31ae23-3865-46fe-b7bb-a4c308199f57" />
- **Schedule Browser**: Browse trips by route, direction, date, and time range with stop times and route maps
  <img width="1913" height="941" alt="image" src="https://github.com/user-attachments/assets/2128dea9-c3eb-4d54-90f9-0db6e2f6c4ab" />
- **Actual Trip Viewer**: View recorded trip observations with delay calculations
  <img width="1856" height="501" alt="image" src="https://github.com/user-attachments/assets/0ae49f19-6114-471b-be8b-9b0f3c9f9286" />


## Quick Start

```bash
git clone https://github.com/yourusername/seattle-public-transit.git
cd seattle-public-transit
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/main.py
```

The app loads GTFS data from CSV files in `data/` into an in-memory SQLite database.

## Project Structure

```
seattle-public-transit/
├── app/
│   ├── main.py             # Entry point
│   ├── database.py         # CSV → SQLite data loading
│   ├── constants.py        # App constants
│   ├── utils.py            # Utility functions
│   └── tabs/               # Tab components
│       ├── performance.py
│       ├── schedules.py
│       └── actual_trips.py
├── data/                   # GTFS CSV files
└── requirements.txt
```

## Data Source

GTFS data from King County Metro: https://kingcounty.gov/en/dept/metro/travel-options/transit-data/open-data

*'Actual trip' data is sample data for demonstration purposes.*
